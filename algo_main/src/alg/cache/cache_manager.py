"""Safe read/write helpers for parquet artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pandas as pd

from alg.artifacts.metadata import read_metadata, write_metadata


def read_artifact(path: str | Path) -> pd.DataFrame:
    return pd.read_parquet(path)


def is_artifact_valid(path: str | Path, expected_metadata: dict | None = None) -> bool:
    artifact_path = Path(path)
    if not artifact_path.exists():
        return False
    if not expected_metadata:
        return True
    actual = read_metadata(artifact_path)
    return bool(actual) and all(actual.get(key) == value for key, value in expected_metadata.items())


def write_artifact(
    df: pd.DataFrame,
    path: str | Path,
    *,
    metadata: dict,
    overwrite: bool = False,
) -> str:
    artifact_path = Path(path)
    if artifact_path.exists() and not overwrite:
        actual = read_metadata(artifact_path)
        if actual and metadata and all(actual.get(key) == value for key, value in metadata.items() if key in actual):
            return "reused_existing"
        raise FileExistsError(f"Refusing to overwrite existing artifact without overwrite=True: {artifact_path}")
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(artifact_path, index=False)
    write_metadata(artifact_path, metadata)
    return "written"


def load_or_build_artifact(
    path: str | Path,
    *,
    expected_metadata: dict | None,
    builder: Callable[[], pd.DataFrame],
    metadata_builder: Callable[[pd.DataFrame], dict],
    overwrite: bool = False,
) -> tuple[pd.DataFrame, str]:
    artifact_path = Path(path)
    if artifact_path.exists() and not overwrite and is_artifact_valid(artifact_path, expected_metadata):
        return read_artifact(artifact_path), "reused_existing"
    df = builder()
    metadata = metadata_builder(df)
    status = write_artifact(df, artifact_path, metadata=metadata, overwrite=overwrite)
    return df, status
