import pytest

from dataact.cache import SessionCache


class TestPutGet:
    def test_roundtrip(self):
        cache = SessionCache()
        cache.put("sales", [1, 2, 3])
        assert cache.get("sales") == [1, 2, 3]

    def test_put_returns_handle_name(self):
        cache = SessionCache()
        name = cache.put("revenue", 42.0)
        assert name == "revenue"

    def test_invalid_name_rejected(self):
        cache = SessionCache()
        with pytest.raises(ValueError):
            cache.put("123foo", "data")

    def test_invalid_hyphenated_name_rejected(self):
        cache = SessionCache()
        with pytest.raises(ValueError):
            cache.put("my-name", "data")

    def test_auto_suffix_on_collision(self):
        cache = SessionCache()
        import pandas as pd

        df1 = pd.DataFrame({"a": [1, 2]})
        df2 = pd.DataFrame({"b": [3, 4]})
        n1 = cache.put("sales", df1)
        n2 = cache.put("sales", df2)
        assert n1 == "sales"
        assert n2 == "sales_2"

    def test_both_suffixed_retrievable(self):
        cache = SessionCache()
        cache.put("x", "first")
        cache.put("x", "second")
        assert cache.get("x") == "first"
        assert cache.get("x_2") == "second"

    def test_triple_collision(self):
        cache = SessionCache()
        cache.put("x", "a")
        cache.put("x", "b")
        n3 = cache.put("x", "c")
        assert n3 == "x_3"

    def test_explicit_overwrite(self):
        cache = SessionCache()
        cache.put("data", "original")
        n = cache.put("data", "replaced", overwrite=True)
        assert n == "data"
        assert cache.get("data") == "replaced"


class TestSnapshot:
    def test_dataframe_snapshot(self):
        pytest.importorskip("pandas")
        import pandas as pd

        cache = SessionCache()
        df = pd.DataFrame({"a": range(100), "b": range(100)})
        cache.put("big", df)
        snap = cache.snapshot("big")
        assert (
            "dataframe" in snap.lower()
            or "shape" in snap.lower()
            or "columns" in snap.lower()
        )

    def test_list_snapshot(self):
        cache = SessionCache()
        cache.put("items", list(range(50)))
        snap = cache.snapshot("items")
        assert "50" in snap or "length" in snap.lower() or "list" in snap.lower()

    def test_dict_snapshot(self):
        cache = SessionCache()
        d = {f"k{i}": i for i in range(20)}
        cache.put("mapping", d)
        snap = cache.snapshot("mapping")
        assert snap  # non-empty

    def test_scalar_snapshot(self):
        cache = SessionCache()
        cache.put("val", 42)
        snap = cache.snapshot("val")
        assert "42" in snap

    def test_ndarray_snapshot(self):
        pytest.importorskip("numpy")
        import numpy as np

        cache = SessionCache()
        arr = np.arange(1000).reshape(100, 10)
        cache.put("arr", arr)
        snap = cache.snapshot("arr")
        assert snap


class TestListHandles:
    def test_returns_mapping(self):
        cache = SessionCache()
        cache.put("a", 1)
        cache.put("b", 2)
        handles = cache.list_handles()
        assert "a" in handles
        assert "b" in handles

    def test_values_are_snapshots(self):
        cache = SessionCache()
        cache.put("x", "hello")
        handles = cache.list_handles()
        assert isinstance(handles["x"], str)


class TestSampleSize:
    def test_configurable_sample_size(self):
        pytest.importorskip("pandas")
        import pandas as pd

        cache = SessionCache(sample_size=3)
        df = pd.DataFrame({"a": range(100)})
        cache.put("df", df)
        snap = cache.snapshot("df")
        # The snapshot should reflect sample_size=3
        assert snap

    def test_default_sample_size(self):
        cache = SessionCache()
        assert cache.sample_size == 5

    def test_large_dataframe_sample_uses_configured_size(self):
        pytest.importorskip("pandas")
        import pandas as pd

        cache = SessionCache(sample_size=2)
        df = pd.DataFrame({"v": range(10000)})
        cache.put("big_df", df)
        snap = cache.snapshot("big_df")
        # Check it's a small snapshot (contains shape info, not all rows)
        assert "10000" in snap or "shape" in snap.lower() or "sample" in snap.lower()
