from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from observation_context_test_utils import configure_formal_observation_env


def test_2025_12_05_observation_context_is_ready_with_daily_detector_run(monkeypatch) -> None:
    configure_formal_observation_env(monkeypatch)

    payload = TestClient(app).get(
        "/api/v1/report-context",
        params={"observation_date": "2025-12-05"},
    ).json()

    assert payload["observation_date"] == "2025-12-05"
    assert payload["probability_report_month"] == "2025-11"
    assert payload["detector_run_date"] == "2025-12-05"
    assert payload["probability_batch_available"] is True
    assert payload["detector_run_available"] is True
    assert payload["context_status"] == "ready"
    assert payload["manual_selection_required"] is False
