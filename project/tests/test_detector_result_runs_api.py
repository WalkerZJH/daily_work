from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from detector_result_test_utils import override_detector_service


def test_detector_runs_api_returns_run_metadata_and_config_version() -> None:
    with override_detector_service():
        response = TestClient(app).get("/api/v1/detectors/runs")

    assert response.status_code == 200
    payload = response.json()
    run = payload["items"][0]

    assert run["detector_run_id"] == "run_2025_12_31"
    assert run["run_date"] == "2025-12-31"
    assert run["detector_config_version"] == "daily_detector_rules_v1"
    assert run["scanned_entity_count"] == 3
    assert run["clue_count"] == 2
    assert run["attached_high_risk_count"] == 1
    assert payload["ready"] is True
