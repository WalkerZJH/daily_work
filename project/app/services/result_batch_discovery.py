"""Discover published monthly and Detector batches without conflating their availability."""

from __future__ import annotations

import json
from pathlib import Path


_DETECTOR_TABLES = (
    "detector_catalog",
    "daily_detector_runs",
    "daily_detector_clues",
    "high_risk_detector_evidence",
)


def latest_monthly_batch(root: str | Path) -> Path | None:
    """Return the newest published monthly candidate batch with its core entity table."""

    return _latest(root, _is_monthly_batch)


def latest_detector_batch(root: str | Path) -> Path | None:
    """Return the newest published batch that declares and contains all Detector tables."""

    return _latest(root, _has_detector_tables)


def published_monthly_profile_batches(
    root: str | Path,
    *,
    through_report_month: str | None = None,
    limit: int = 12,
) -> list[Path]:
    """Return at most one published horizon-profile batch per month, oldest first."""

    root_path = Path(root)
    if not root_path.exists() or limit <= 0:
        return []
    selected: dict[str, Path] = {}
    for manifest_path in sorted(root_path.glob("report_month=*/batch_id=*/manifest.json"), reverse=True):
        manifest = _read_manifest(manifest_path)
        report_month = str((manifest or {}).get("report_month") or "")
        if not report_month or (through_report_month and report_month > through_report_month):
            continue
        batch = manifest_path.parent
        if report_month not in selected and _has_monthly_horizon_profiles(batch, manifest):
            selected[report_month] = batch
    months = sorted(selected)[-limit:]
    return [selected[month] for month in months]


def _latest(root: str | Path, predicate) -> Path | None:
    root_path = Path(root)
    if not root_path.exists():
        return None
    candidates = sorted(root_path.glob("report_month=*/batch_id=*/manifest.json"), reverse=True)
    for manifest_path in candidates:
        batch = manifest_path.parent
        manifest = _read_manifest(manifest_path)
        if manifest is not None and predicate(batch, manifest):
            return batch
    return None


def _is_monthly_batch(batch: Path, manifest: dict) -> bool:
    return manifest.get("report_type") == "monthly" and (batch / "risk_entities.parquet").is_file()


def _has_detector_tables(batch: Path, manifest: dict) -> bool:
    declared = manifest.get("detector_tables")
    if not isinstance(declared, dict) or not declared:
        return False
    return all(
        isinstance(declared.get(name), str) and (batch / declared[name]).is_file()
        for name in _DETECTOR_TABLES
    )


def _has_monthly_horizon_profiles(batch: Path, manifest: dict | None) -> bool:
    if not manifest or not _is_monthly_batch(batch, manifest):
        return False
    table = manifest.get("horizon_profile_table")
    path = table.get("path") if isinstance(table, dict) else None
    return isinstance(path, str) and bool(path) and (batch / path).is_file()


def _read_manifest(path: Path) -> dict | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None
