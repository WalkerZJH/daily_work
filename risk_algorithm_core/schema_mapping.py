"""Schema mapping helpers for raw business tables."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json

import pandas as pd


class SchemaMapping(dict):
    """Table-to-column mapping container."""


def load_schema_mapping(path: str | Path | None) -> SchemaMapping:
    if not path:
        return SchemaMapping()
    p = Path(path)
    if not p.exists():
        return SchemaMapping()
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        try:
            import yaml

            data = yaml.safe_load(text) or {}
        except ImportError:
            data = {}
    return SchemaMapping(data)


def apply_schema_mapping(df: pd.DataFrame, table_name: str, mapping: SchemaMapping) -> pd.DataFrame:
    table_mapping = mapping.get(table_name, {})
    columns = table_mapping.get("columns", table_mapping) if isinstance(table_mapping, dict) else {}
    if not columns:
        return df.copy()
    rename = {str(source): str(target) for source, target in columns.items() if source in df.columns}
    return df.rename(columns=rename).copy()


def ensure_columns(df: pd.DataFrame, required: list[str], table_name: str) -> None:
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"{table_name} missing required columns after schema mapping: {missing}")
