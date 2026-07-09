from __future__ import annotations

from datetime import date
from pathlib import Path

from risk_model_core.repositories import ParquetRiskResultRepository


BATCH_DIR = Path(
    "algo_main/data/entity_complete_v2_coverage_expansion/13_formal_algorithm_core_raw_to_batch/"
    "formal_result_batches/report_month=2025-12/batch_id=2025-12-monthly-risk-algorithm-formal-v2-raw"
)


def test_report_context_manifest_exists() -> None:
    assert (BATCH_DIR / "report_context.json").exists()
    assert (BATCH_DIR.parent.parent / "available_report_contexts.csv").exists()


def test_available_report_contexts_are_listed() -> None:
    repo = ParquetRiskResultRepository(BATCH_DIR)
    contexts = repo.list_available_report_contexts()

    assert len(contexts) >= 1
    assert contexts.iloc[0]["report_month"] == "2025-12"
    assert contexts.iloc[0]["run_date"] == "2026-07-07"


def test_exact_report_context_resolution() -> None:
    repo = ParquetRiskResultRepository(BATCH_DIR)
    resolved = repo.resolve_report_context(requested_report_month="2025-12", requested_run_date="2026-07-07")

    assert resolved["ready"] is True
    assert resolved["date_resolution_status"] == "exact_match"
    assert resolved["effective_report_month"] == "2025-12"
    assert resolved["effective_run_date"] == "2026-07-07"
    assert resolved["is_exact_match"] is True
    assert resolved["fallback_used"] is False


def test_today_report_context_falls_back_to_latest_available_without_faking_today() -> None:
    today = date.today().isoformat()
    repo = ParquetRiskResultRepository(BATCH_DIR)
    resolved = repo.resolve_report_context(requested_run_date=today)

    assert resolved["ready"] is True
    assert resolved["date_resolution_status"] == "fallback_to_latest_available"
    assert resolved["requested_run_date"] == today
    assert resolved["effective_report_month"] == "2025-12"
    assert resolved["effective_run_date"] == "2026-07-07"
    assert resolved["effective_run_date"] != today
    assert resolved["fallback_used"] is True
    assert "2026-07-07" in resolved["available_run_dates"]

