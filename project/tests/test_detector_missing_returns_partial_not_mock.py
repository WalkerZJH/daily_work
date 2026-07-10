from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app
from observation_context_test_utils import configure_formal_observation_env


def test_missing_detector_run_returns_partial_status_not_mock(monkeypatch) -> None:
    configure_formal_observation_env(monkeypatch)

    response = TestClient(app).get(
        "/api/v1/daily-detector/status",
        params={"observation_date": "2025-12-05", "report_month": "2025-12"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is False
    assert payload["context_status"] == "detector_run_unavailable"
    assert payload["detector_run_date"] == "2025-12-05"
    assert payload["detector_run_available"] is False
    assert payload["data_source"] != "mock"
    assert "demo" not in json.dumps(payload, ensure_ascii=False).lower()


def test_missing_detector_run_clues_are_empty_not_mock(monkeypatch) -> None:
    configure_formal_observation_env(monkeypatch)

    response = TestClient(app).get(
        "/api/v1/daily-detector/clues",
        params={"observation_date": "2025-12-05", "report_month": "2025-12"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is False
    assert payload["context_status"] == "detector_run_unavailable"
    assert payload["detector_run_date"] == "2025-12-05"
    assert payload["total"] == 0
    assert payload["items"] == []
    assert payload["data_source"] != "mock"
