from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from observation_context_test_utils import configure_formal_observation_env


def test_daily_detector_missing_run_does_not_mock(monkeypatch) -> None:
    configure_formal_observation_env(monkeypatch)
    client = TestClient(app)

    status = client.get(
        "/api/v1/daily-detector/status",
        params={"observation_date": "2025-12-05", "report_month": "2025-12"},
    ).json()
    clues = client.get(
        "/api/v1/daily-detector/clues",
        params={"observation_date": "2025-12-05", "report_month": "2025-12"},
    ).json()

    assert status["ready"] is False
    assert status["detector_run_available"] is False
    assert status["context_status"] == "detector_run_unavailable"
    assert clues["ready"] is False
    assert clues["total"] == 0
    assert clues["items"] == []
    assert clues["clues"] == []
    assert clues["data_source"] != "mock"
