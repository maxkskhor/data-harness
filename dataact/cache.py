from __future__ import annotations

import json
import keyword
import re
from typing import Any


_VALID_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _is_valid_identifier(name: str) -> bool:
    return bool(_VALID_IDENTIFIER.match(name)) and not keyword.iskeyword(name)


class SessionCache:
    def __init__(self, sample_size: int = 5) -> None:
        self.sample_size = sample_size
        self._store: dict[str, Any] = {}

    def put(self, name: str, value: Any, overwrite: bool = False) -> str:
        if not _is_valid_identifier(name):
            raise ValueError(f"Invalid handle name: {name!r}. Must be a valid Python identifier.")
        if overwrite or name not in self._store:
            self._store[name] = value
            return name
        # Auto-suffix on collision
        suffix = 2
        while True:
            candidate = f"{name}_{suffix}"
            if candidate not in self._store:
                self._store[candidate] = value
                return candidate
            suffix += 1

    def get(self, name: str) -> Any:
        return self._store[name]

    def snapshot(self, handle: str) -> str:
        value = self._store[handle]
        return self._make_snapshot(value)

    def list_handles(self) -> dict[str, str]:
        return {name: self._make_snapshot(value) for name, value in self._store.items()}

    def _make_snapshot(self, value: Any) -> str:
        try:
            import pandas as pd
            if isinstance(value, pd.DataFrame):
                return self._snapshot_dataframe(value)
        except ImportError:
            pass

        try:
            import numpy as np
            if isinstance(value, np.ndarray):
                return self._snapshot_ndarray(value)
        except ImportError:
            pass

        if isinstance(value, list):
            return self._snapshot_list(value)
        if isinstance(value, dict):
            return self._snapshot_dict(value)
        # Scalar
        return f"value: {value!r}"

    def _snapshot_dataframe(self, df) -> str:
        cols = list(df.columns)
        shape = list(df.shape)
        sample = df.head(self.sample_size).to_dict(orient="records")
        return json.dumps({
            "type": "dataframe",
            "shape": shape,
            "columns": cols,
            "sample": sample,
        })

    def _snapshot_ndarray(self, arr) -> str:
        flat = arr.flat
        sample = [x.item() if hasattr(x, "item") else x for _, x in zip(range(self.sample_size), flat)]
        return json.dumps({
            "type": "ndarray",
            "shape": list(arr.shape),
            "dtype": str(arr.dtype),
            "sample": sample,
        })

    def _snapshot_list(self, lst: list) -> str:
        sample = lst[:self.sample_size]
        try:
            sample_json = json.dumps(sample)
        except Exception:
            sample_json = repr(sample)
        return json.dumps({
            "type": "list",
            "length": len(lst),
            "sample": json.loads(sample_json) if sample_json else [],
        })

    def _snapshot_dict(self, d: dict) -> str:
        keys = list(d.keys())[:self.sample_size]
        sample = {k: d[k] for k in keys}
        try:
            sample_str = json.dumps(sample, default=repr)
        except Exception:
            sample_str = repr(sample)
        return json.dumps({
            "type": "dict",
            "total_keys": len(d),
            "sample_keys": keys,
            "sample": json.loads(sample_str),
        })
