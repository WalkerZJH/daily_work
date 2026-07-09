from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from observation_context_test_utils import configure_formal_observation_env


def test_observation_date_maps_to_probability_report_month(monkeypatch) -> None:
    configure_formal_observation_env(monkeypatch)

    response = TestClient(app).get(
        "/api/v1/report-context",
        params={"observation_date": "2025-12-05"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["observation_date"] == "2025-12-05"
    assert payload["probability_report_month"] == "2025-11"
    assert payload["effective_report_month"] == "2025-11"
    assert payload["context_status"] == "detector_run_unavailable"
