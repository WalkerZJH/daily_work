from __future__ import annotations

import json
from pathlib import Path

from app.services.result_batch_discovery import latest_detector_batch, latest_monthly_batch


def test_monthly_embedded_detector_tables_are_not_published_detector_batches(tmp_path: Path) -> None:
    _batch(tmp_path, "2025-12", "formal-v2", detector_tables=True)
    monthly_batch = _batch(tmp_path, "2025-12", "full-recurring-v2", detector_tables=False)

    assert latest_monthly_batch(tmp_path) == monthly_batch
    assert latest_detector_batch(tmp_path) is None


def test_discovery_finds_published_independent_detector_partition(tmp_path: Path) -> None:
    monthly_batch = _batch(tmp_path, "2025-12", "full-recurring-v3", detector_tables=False)
    detector_batch = _independent_detector_batch(tmp_path, "2026-01-03", "daily-detector-fact-v1")

    assert latest_monthly_batch(tmp_path) == monthly_batch
    assert latest_detector_batch(tmp_path) == detector_batch


def _batch(root: Path, month: str, batch_id: str, *, detector_tables: bool) -> Path:
    batch = root / f"report_month={month}" / f"batch_id={batch_id}"
    batch.mkdir(parents=True)
    (batch / "risk_entities.parquet").touch()
    tables = {}
    if detector_tables:
        for name in ["detector_catalog", "daily_detector_runs", "daily_detector_clues", "high_risk_detector_evidence"]:
            path = f"{name}.parquet"
            (batch / path).touch()
            tables[name] = path
    (batch / "manifest.json").write_text(
        json.dumps({"report_type": "monthly", "detector_tables": tables}), encoding="utf-8"
    )
    return batch


def _independent_detector_batch(root: Path, run_date: str, batch_id: str) -> Path:
    batch = root / f"detector_run_date={run_date}" / f"batch_id={batch_id}"
    batch.mkdir(parents=True)
    tables = {}
    for name in ["detector_catalog", "daily_detector_runs", "daily_detector_clues", "high_risk_detector_evidence"]:
        path = f"{name}.parquet"
        (batch / path).touch()
        tables[name] = path
    (batch / "manifest.json").write_text(
        json.dumps({"report_type": "daily_detector", "detector_tables": tables}), encoding="utf-8"
    )
    return batch
