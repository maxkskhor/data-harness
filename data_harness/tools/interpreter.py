from __future__ import annotations

import ast
import builtins
import io
import traceback
from contextlib import redirect_stdout
from typing import Any

from data_harness.cache import SessionCache
from data_harness.types import ToolAnnotations, ToolSpec

_INTERPRETER_ANNOTATIONS = ToolAnnotations(
    title="Python Interpreter",
    read_only=False,
    cache_mutating=True,
    destructive=False,
    open_world=False,
)

_DEFAULT_ALLOWLIST = frozenset(
    {
        "pandas",
        "numpy",
        "json",
        "math",
        "datetime",
        "collections",
        "itertools",
        "pd",
        "np",  # common aliases
    }
)

_FORBIDDEN_NAMES = frozenset({"eval", "exec", "__import__", "open", "compile"})

_EMPTY_OUTPUT_GUIDANCE = (
    "Code ran successfully but produced no stdout. "
    "Use print(...) to inspect values, or save(name, value) to persist results "
    "for later calls."
)

_LOCALS_ERROR = (
    "Error: locals() is not available in python_interpreter. "
    "Use cache handles directly as local variables. "
    "Call list_variables to see available handles."
)

_SENTINEL = object()


class PythonInterpreterError(Exception):
    """Raised by PythonInterpreter.run() on any execution failure."""

    def __repr__(self) -> str:
        return str(self)


class _SecurityVisitor(ast.NodeVisitor):
    """AST visitor that raises ValueError on forbidden patterns."""

    def __init__(self, allowlist: frozenset[str]) -> None:
        self._allowlist = allowlist
        self.errors: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            top = alias.name.split(".")[0]
            if top not in self._allowlist:
                self.errors.append(f"Import not allowed: {alias.name!r}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            top = node.module.split(".")[0]
            if top not in self._allowlist:
                self.errors.append(f"Import not allowed: {node.module!r}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id in _FORBIDDEN_NAMES:
            self.errors.append(f"Call not allowed: {node.func.id!r}")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("__") and node.attr.endswith("__"):
            self.errors.append(f"Dunder attribute access not allowed: {node.attr!r}")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in _FORBIDDEN_NAMES:
            self.errors.append(f"Name not allowed: {node.id!r}")
        self.generic_visit(node)


def _has_locals_call(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "locals"
        ):
            return True
    return False


class PythonInterpreter:
    def __init__(
        self,
        cache: SessionCache,
        allowlist: frozenset[str] | None = None,
    ) -> None:
        self._cache = cache
        self._allowlist = allowlist if allowlist is not None else _DEFAULT_ALLOWLIST

    def run(self, code: str) -> str:
        # AST security check
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            raise PythonInterpreterError(f"SyntaxError: {exc}") from exc

        visitor = _SecurityVisitor(self._allowlist)
        visitor.visit(tree)
        if visitor.errors:
            raise PythonInterpreterError(
                "SecurityError: " + "; ".join(visitor.errors) + " — not allowed"
            )

        if _has_locals_call(tree):
            raise PythonInterpreterError(_LOCALS_ERROR)

        # Build fresh locals for this call
        local_vars: dict[str, Any] = {}

        # Inject cache handles
        for name, value in self._cache.items():
            local_vars[name] = value

        # Inject save() helper
        def save(name: str, value: Any) -> str:
            return self._cache.put(name, value)

        local_vars["save"] = save

        globals_dict: dict[str, Any] = {"__builtins__": _safe_builtins(self._allowlist)}

        # Capture stdout; attempt final-expression capture when the last
        # statement is a bare expression (notebook-like behaviour).
        buf = io.StringIO()
        last_val: object = _SENTINEL

        if tree.body and isinstance(tree.body[-1], ast.Expr):
            body_tree = ast.Module(body=tree.body[:-1], type_ignores=[])
            expr_tree = ast.Expression(body=tree.body[-1].value)
            ast.fix_missing_locations(body_tree)
            ast.fix_missing_locations(expr_tree)
            try:
                with redirect_stdout(buf):
                    exec(  # noqa: S102
                        compile(body_tree, "<code>", "exec"),
                        globals_dict,
                        local_vars,
                    )
                    last_val = eval(  # noqa: S307
                        compile(expr_tree, "<code>", "eval"),
                        globals_dict,
                        local_vars,
                    )
            except Exception:
                raise PythonInterpreterError(
                    f"Error:\n{traceback.format_exc()}"
                ) from None
        else:
            try:
                with redirect_stdout(buf):
                    exec(  # noqa: S102
                        compile(tree, "<code>", "exec"),
                        globals_dict,
                        local_vars,
                    )
            except Exception:
                raise PythonInterpreterError(
                    f"Error:\n{traceback.format_exc()}"
                ) from None

        output = buf.getvalue()
        if output:
            return output

        if last_val is not _SENTINEL and last_val is not None:
            return repr(last_val)

        return _EMPTY_OUTPUT_GUIDANCE

    @staticmethod
    def make_tool_spec(cache: SessionCache) -> ToolSpec:
        interp = PythonInterpreter(cache=cache)
        return ToolSpec(
            name="python_interpreter",
            description=(
                "Run Python code in a sandboxed interpreter with direct access to "
                "cached data handles.\n\n"
                "• Cache handles are available as local variables — use them directly, "
                "e.g. print(fred_unrate.head()). Do NOT use locals() to look up "
                "handles by name.\n"
                "• The interpreter captures printed stdout only. Always use print(...) "
                "to inspect values, e.g. print(df.describe()).\n"
                "• If the last statement is a bare expression (e.g. df.describe()), "
                "its repr is returned automatically when nothing was printed.\n"
                "• Each call starts with fresh local variables. Any variable not saved "
                "with save(name, value) is discarded at the end of the call.\n"
                "• Call save(name, value) to persist computed artefacts for later "
                "calls."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute"},
                },
                "required": ["code"],
            },
            handler=interp.run,
            annotations=_INTERPRETER_ANNOTATIONS,
        )


def _safe_builtins(allowlist: frozenset[str]) -> dict:
    safe = {
        "print": print,
        "len": len,
        "range": range,
        "enumerate": enumerate,
        "zip": zip,
        "map": map,
        "filter": filter,
        "sorted": sorted,
        "reversed": reversed,
        "list": list,
        "dict": dict,
        "set": set,
        "tuple": tuple,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "type": type,
        "isinstance": isinstance,
        "hasattr": hasattr,
        "getattr": getattr,
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sum": sum,
        "any": any,
        "all": all,
        "repr": repr,
        "format": format,
        "vars": vars,
        "dir": dir,
        "None": None,
        "True": True,
        "False": False,
        "__import__": _make_safe_import(allowlist),
    }
    return safe


def _make_safe_import(allowlist: frozenset[str]):
    def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level != 0:
            raise ImportError("relative imports are not allowed")
        top = name.split(".")[0]
        if top not in allowlist:
            raise ImportError(f"Import not allowed: {name!r}")
        return builtins.__import__(name, globals, locals, fromlist, level)

    return safe_import
