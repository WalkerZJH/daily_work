"""Lightweight hashing helpers for data artifacts and configs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hash_dict(obj: dict[str, Any]) -> str:
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)
    return _sha256_text(payload)


def hash_file(path: str | Path) -> str:
    resolved = Path(path).resolve()
    stat = resolved.stat()
    payload = {
        "path": str(resolved),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }
    return hash_dict(payload)


def hash_config(path: str | Path) -> str:
    return hash_file(path)


def hash_dataframe_schema(df: pd.DataFrame) -> str:
    schema = {
        "columns": list(df.columns),
        "dtypes": {column: str(dtype) for column, dtype in df.dtypes.items()},
    }
    return hash_dict(schema)
