from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from frontend_api_test_utils import override_frontend_result_repository


def test_daily_detector_status_uses_effective_run_date() -> None:
    today = date.today().isoformat()
    with override_frontend_result_repository():
        response = TestClient(app).get(
            "/api/v1/daily-detector/status",
            params={"run_date": today},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["requested_run_date"] == today
    assert payload["effective_run_date"] == "2025-12-31"
    assert payload["run_date"] == "2025-12-31"
    assert payload["date_resolution_status"] == "fallback_to_latest_available"


def test_daily_detector_clues_uses_effective_run_date() -> None:
    today = date.today().isoformat()
    with override_frontend_result_repository():
        response = TestClient(app).get(
            "/api/v1/daily-detector/clues",
            params={"run_date": today, "top_n": 5},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["requested_run_date"] == today
    assert payload["effective_run_date"] == "2025-12-31"
    assert payload["run_date"] == "2025-12-31"
    assert payload["date_resolution_status"] == "fallback_to_latest_available"
    assert payload["total"] == 2
