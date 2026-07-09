from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from frontend_api_test_utils import (
    empty_daily_detector_clues,
    empty_high_risk_detector_evidence,
    make_frontend_repository,
    override_frontend_result_repository,
)


def test_daily_detector_status_returns_ready_with_zero_clues() -> None:
    repository = make_frontend_repository(
        clues=empty_daily_detector_clues(),
        evidence=empty_high_risk_detector_evidence(),
    )
    with override_frontend_result_repository(repository):
        response = TestClient(app).get("/api/v1/daily-detector/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["run_date"] == "2025-12-31"
    assert payload["detector_run_id"] == "run_2025_12_31"
    assert payload["detector_config_version"] == "daily_detector_rules_v1"
    assert payload["clue_count"] == 0
    assert payload["attached_high_risk_count"] == 0
    assert payload["highest_detector_score"] is None
    assert payload["enabled_detectors"] == "purchase_interval_ipi"
    assert "下一次巡检运行后生效" in payload["config_effective_note"]
