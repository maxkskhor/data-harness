from __future__ import annotations

import ast
import builtins
import io
import traceback
from contextlib import redirect_stdout
from typing import Any

from dataact.cache import SessionCache
from dataact.types import ToolSpec

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
            return f"SyntaxError: {exc}"

        visitor = _SecurityVisitor(self._allowlist)
        visitor.visit(tree)
        if visitor.errors:
            return "SecurityError: " + "; ".join(visitor.errors) + " — not allowed"

        # Build fresh locals for this call
        local_vars: dict[str, Any] = {}

        # Inject cache handles
        for name, value in self._cache.items():
            local_vars[name] = value

        # Inject save() helper
        def save(name: str, value: Any) -> str:
            return self._cache.put(name, value)

        local_vars["save"] = save

        # Capture stdout
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                exec(
                    compile(tree, "<code>", "exec"),
                    {"__builtins__": _safe_builtins(self._allowlist)},
                    local_vars,
                )  # noqa: S102
        except Exception:
            err = traceback.format_exc()
            return f"Error:\n{err}"

        output = buf.getvalue()
        return output if output else "ran successfully with no output"

    @staticmethod
    def make_tool_spec(cache: SessionCache) -> ToolSpec:
        interp = PythonInterpreter(cache=cache)
        return ToolSpec(
            name="python_interpreter",
            description=(
                "Run Python code over cached data handles. "
                "Cache handles are available as local variables. "
                "Call save(name, value) to store computed artifacts back to cache."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute"},
                },
                "required": ["code"],
            },
            handler=interp.run,
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
