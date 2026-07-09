from __future__ import annotations

from datetime import date
from pathlib import Path

from risk_model_core.repositories import ParquetRiskResultRepository


ROOT = Path("algo_main/data/entity_complete_v2_coverage_expansion/16_multi_month_formal_result_batches")
BATCH_DIR = ROOT / "report_month=2025-12" / "batch_id=2025-12-monthly-risk-algorithm-formal-v2-raw"


def test_observation_date_maps_to_previous_complete_month() -> None:
    repo = ParquetRiskResultRepository(BATCH_DIR)
    context = repo.resolve_observation_context(observation_date="2025-12-05", batch_root=ROOT)

    assert context["observation_date"] == "2025-12-05"
    assert context["probability_report_month"] == "2025-11"
    assert context["detector_run_date"] == "2025-12-05"


def test_missing_detector_run_is_not_silent_fallback() -> None:
    repo = ParquetRiskResultRepository(BATCH_DIR)
    context = repo.resolve_observation_context(observation_date="2025-12-05", batch_root=ROOT)

    assert context["probability_batch_available"] is True
    assert context["detector_run_available"] is False
    assert context["context_status"] == "detector_run_unavailable"
    assert context["manual_selection_required"] is True


def test_today_observation_does_not_claim_today_report() -> None:
    repo = ParquetRiskResultRepository(BATCH_DIR)
    context = repo.resolve_observation_context(observation_date=date.today().isoformat(), batch_root=ROOT)

    assert context["observation_date"] == date.today().isoformat()
    assert context["context_status"] in {"probability_month_unavailable", "detector_run_unavailable", "manual_selection_required"}
    assert context["detector_run_date"] == date.today().isoformat()
    assert context["detector_run_available"] is False


def test_open_probability_repository_uses_context_batch() -> None:
    repo = ParquetRiskResultRepository(BATCH_DIR)
    context = repo.resolve_observation_context(observation_date="2025-12-05", batch_root=ROOT)
    probability_repo = repo.open_probability_repository(context)

    assert probability_repo.manifest().report_month == "2025-11"

