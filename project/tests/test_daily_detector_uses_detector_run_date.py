from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from observation_context_test_utils import configure_formal_observation_env


def test_daily_detector_status_uses_detector_run_date_from_observation_context(monkeypatch) -> None:
    configure_formal_observation_env(monkeypatch)

    response = TestClient(app).get(
        "/api/v1/daily-detector/status",
        params={"observation_date": "2025-12-01"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["report_context"]["probability_report_month"] == "2025-11"
    assert payload["report_context"]["detector_run_date"] == "2025-12-01"
    assert payload["run_date"] == "2025-12-01"
    assert payload["detector_run_available"] is True
    assert payload["context_status"] == "ready"


def test_daily_detector_clues_uses_detector_run_date_from_observation_context(monkeypatch) -> None:
    configure_formal_observation_env(monkeypatch)

    response = TestClient(app).get(
        "/api/v1/daily-detector/clues",
        params={"observation_date": "2025-12-01", "top_n": 5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["report_context"]["detector_run_date"] == "2025-12-01"
    assert payload["run_date"] == "2025-12-01"
    assert payload["detector_run_available"] is True
    assert payload["context_status"] == "ready"
