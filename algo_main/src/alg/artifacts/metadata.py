"""Metadata helpers for stable parquet artifacts."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import pandas as pd

from alg.artifacts.hashing import hash_dataframe_schema


def metadata_path(path: str | Path) -> Path:
    return Path(path).with_suffix(".meta.json")


def write_metadata(path: str | Path, metadata: dict[str, Any]) -> None:
    meta_path = metadata_path(path)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def read_metadata(path: str | Path) -> dict[str, Any]:
    meta_path = metadata_path(path)
    if not meta_path.exists():
        return {}
    return json.loads(meta_path.read_text(encoding="utf-8"))


def build_artifact_metadata(
    *,
    artifact_name: str,
    artifact_type: str,
    version: str = "v1",
    df: pd.DataFrame | None = None,
    source_artifacts: list[str] | None = None,
    source_hashes: dict[str, str] | None = None,
    config_hashes: dict[str, str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "artifact_name": artifact_name,
        "artifact_type": artifact_type,
        "version": version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "row_count": int(len(df)) if df is not None else None,
        "columns": list(df.columns) if df is not None else [],
        "schema_hash": hash_dataframe_schema(df) if df is not None else None,
        "source_artifacts": source_artifacts or [],
        "source_hashes": source_hashes or {},
        "config_hashes": config_hashes or {},
    }
    if extra:
        metadata.update(extra)
    return metadata
