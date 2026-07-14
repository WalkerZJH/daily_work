"""Parquet-only production table IO helpers."""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


class ProductionParquetWriteError(RuntimeError):
    """Raised when a production Parquet table cannot be written atomically."""


def write_production_parquet(
    frame: pd.DataFrame,
    output_path: str | Path,
    *,
    schema: pa.Schema | None = None,
    compression: str = "zstd",
    row_group_size: int | None = None,
    write_batch_size: int | None = None,
) -> None:
    """Write a production table as Parquet with validation and atomic replace."""

    path = Path(output_path)
    if path.suffix != ".parquet":
        raise ValueError(f"Production table path must end with .parquet: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    normalized = _normalize_frame_for_arrow(frame)
    try:
        table = pa.Table.from_pandas(normalized, schema=schema, preserve_index=False)
        pq.write_table(
            table,
            temp_path,
            compression=compression,
            row_group_size=row_group_size,
            write_batch_size=write_batch_size,
        )
        metadata = pq.ParquetFile(temp_path).metadata
        if metadata.num_rows != len(frame):
            raise ProductionParquetWriteError(
                f"Parquet row count mismatch for {path}: expected {len(frame)}, got {metadata.num_rows}"
            )
        actual_columns = pq.ParquetFile(temp_path).schema.names
        expected_columns = list(frame.columns)
        if actual_columns != expected_columns:
            raise ProductionParquetWriteError(
                f"Parquet schema mismatch for {path}: expected {expected_columns}, got {actual_columns}"
            )
        os.replace(temp_path, path)
    except Exception as exc:
        try:
            temp_path.unlink(missing_ok=True)
        finally:
            if isinstance(exc, ProductionParquetWriteError):
                raise
            raise ProductionParquetWriteError(
                "Failed to write production Parquet table "
                f"path={path} rows={len(frame)} columns={list(frame.columns)}"
            ) from exc


def _normalize_frame_for_arrow(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy(deep=False)
    for column in out.columns:
        series = out[column]
        if series.dtype != "object":
            continue
        if not _contains_json_like_value(series):
            continue
        out[column] = series.map(_stable_json_or_null)
    return out


def _contains_json_like_value(series: pd.Series) -> bool:
    return any(isinstance(value, (dict, list, tuple)) for value in series.dropna().head(1000))


def _stable_json_or_null(value: Any) -> str | None:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    return json.dumps(_jsonable(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (dt.date, dt.datetime, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, pd.Series):
        return [_jsonable(item) for item in value.tolist()]
    if pd.isna(value):
        return None
    return value
