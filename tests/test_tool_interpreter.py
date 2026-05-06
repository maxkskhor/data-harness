"""Tests for the sandboxed Python interpreter tool."""

from dataact.cache import SessionCache
from dataact.tools.interpreter import PythonInterpreter


class TestAllowedImports:
    def test_allowed_import_passes(self):
        cache = SessionCache()
        interp = PythonInterpreter(cache=cache)
        result = interp.run(
            code="import pandas as pd\nprint(pd.DataFrame({'x': [1]}).shape[0])"
        )
        assert result.strip() == "1"

    def test_disallowed_import_rejected(self):
        cache = SessionCache()
        interp = PythonInterpreter(cache=cache)
        result = interp.run(code="import os\nprint(os.getcwd())")
        assert (
            "not allowed" in result.lower()
            or "error" in result.lower()
            or "blocked" in result.lower()
        )

    def test_subprocess_import_rejected(self):
        cache = SessionCache()
        interp = PythonInterpreter(cache=cache)
        result = interp.run(code="import subprocess")
        assert (
            "not allowed" in result.lower()
            or "error" in result.lower()
            or "blocked" in result.lower()
        )


class TestForbiddenBuiltins:
    def test_eval_rejected(self):
        cache = SessionCache()
        interp = PythonInterpreter(cache=cache)
        result = interp.run(code="eval('1+1')")
        assert "error" in result.lower() or "not allowed" in result.lower()

    def test_exec_rejected(self):
        cache = SessionCache()
        interp = PythonInterpreter(cache=cache)
        result = interp.run(code="exec('x=1')")
        assert "error" in result.lower() or "not allowed" in result.lower()

    def test_import_builtin_rejected(self):
        cache = SessionCache()
        interp = PythonInterpreter(cache=cache)
        result = interp.run(code="__import__('os')")
        assert "error" in result.lower() or "not allowed" in result.lower()

    def test_open_rejected(self):
        cache = SessionCache()
        interp = PythonInterpreter(cache=cache)
        result = interp.run(code="open('/etc/passwd')")
        assert "error" in result.lower() or "not allowed" in result.lower()

    def test_dunder_access_rejected(self):
        cache = SessionCache()
        interp = PythonInterpreter(cache=cache)
        result = interp.run(code="x = [].__class__.__bases__")
        assert "error" in result.lower() or "not allowed" in result.lower()


class TestStdoutCapture:
    def test_stdout_captured(self):
        cache = SessionCache()
        interp = PythonInterpreter(cache=cache)
        result = interp.run(code="print('hello world')")
        assert "hello world" in result

    def test_multiple_prints(self):
        cache = SessionCache()
        interp = PythonInterpreter(cache=cache)
        result = interp.run(code="print('a')\nprint('b')\nprint('c')")
        assert "a" in result and "b" in result and "c" in result


class TestCacheHandles:
    def test_cache_handle_available_as_local(self):
        cache = SessionCache()
        import pandas as pd

        df = pd.DataFrame({"x": [1, 2, 3]})
        cache.put("market_data", df)
        interp = PythonInterpreter(cache=cache)
        result = interp.run(code="print(len(market_data))")
        assert "3" in result

    def test_save_stores_in_cache(self):
        cache = SessionCache()
        interp = PythonInterpreter(cache=cache)
        result = interp.run(code="save('avg', 42.0)\nprint('saved')")
        assert "saved" in result or "avg" in result
        assert cache.get("avg") == 42.0

    def test_save_collision_auto_suffixed(self):
        cache = SessionCache()
        cache.put("result", "original")
        interp = PythonInterpreter(cache=cache)
        result = interp.run(code="name = save('result', 'new')\nprint(name)")
        assert "result_2" in result

    def test_locals_do_not_persist_between_calls(self):
        cache = SessionCache()
        interp = PythonInterpreter(cache=cache)
        interp.run(code="my_local = 'hello'")
        result = interp.run(code="print(my_local)")
        assert (
            "error" in result.lower()
            or "NameError" in result
            or "my_local" not in result.split("hello")
        )

    def test_cache_object_not_in_locals(self):
        cache = SessionCache()
        interp = PythonInterpreter(cache=cache)
        result = interp.run(code="print('cache' in dir())")
        assert "False" in result or "cache" not in result


class TestErrorHandling:
    def test_exception_in_user_code(self):
        cache = SessionCache()
        interp = PythonInterpreter(cache=cache)
        result = interp.run(code="raise ValueError('oops')")
        assert "oops" in result or "ValueError" in result

    def test_no_harness_crash_on_exception(self):
        cache = SessionCache()
        interp = PythonInterpreter(cache=cache)
        # Should return error string, not raise
        result = interp.run(code="1/0")
        assert isinstance(result, str)
        assert "ZeroDivision" in result or "error" in result.lower()
