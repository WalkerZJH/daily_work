from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_BATCH_ROOT = Path("data/project_result_batches")


def batch_dirs(batch_root: str | Path = DEFAULT_BATCH_ROOT) -> list[Path]:
    """Return published monthly batches (legacy public helper)."""
    return monthly_batch_dirs(batch_root)


def monthly_batch_dirs(batch_root: str | Path = DEFAULT_BATCH_ROOT) -> list[Path]:
    root = Path(batch_root)
    return [manifest.parent for manifest in sorted(root.glob("report_month=*/batch_id=*/manifest.json"))]


def detector_batch_dirs(batch_root: str | Path = DEFAULT_BATCH_ROOT) -> list[Path]:
    """Return published aggregate and detector_id component batches."""
    root = Path(batch_root)
    manifests = [
        *root.glob("detector_run_date=*/batch_id=*/manifest.json"),
        *root.glob("detector_run_date=*/detector_id=*/batch_id=*/manifest.json"),
    ]
    return [manifest.parent for manifest in sorted(manifests)]


def read_manifest(batch_dir: str | Path) -> dict[str, Any]:
    return json.loads((Path(batch_dir) / "manifest.json").read_text(encoding="utf-8"))


def read_parquet_table(batch_dir: str | Path, table: str) -> pd.DataFrame:
    path = Path(batch_dir) / f"{table}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Missing production Parquet table: {path}")
    return pd.read_parquet(path)


def require_batch_dir(batch_dir: str | Path) -> Path:
    path = Path(batch_dir)
    if not (path / "manifest.json").exists():
        raise FileNotFoundError(f"Batch manifest not found: {path / 'manifest.json'}")
    return path


def json_dump(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
