from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from frontend_api_test_utils import override_frontend_result_repository


def test_report_context_falls_back_from_today_to_latest_available() -> None:
    today = date.today().isoformat()
    with override_frontend_result_repository():
        response = TestClient(app).get(
            "/api/v1/report-context",
            params={"run_date": today, "horizon": "H99"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["requested_run_date"] == today
    assert payload["effective_run_date"] == "2025-12-31"
    assert payload["requested_horizon"] == "H99"
    assert payload["effective_horizon"] == "H6"
    assert payload["date_resolution_status"] == "fallback_to_latest_available"
    assert payload["fallback_used"] is True


def test_report_context_falls_back_from_missing_report_month() -> None:
    with override_frontend_result_repository():
        response = TestClient(app).get(
            "/api/v1/report-context",
            params={"report_month": "2099-01"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["requested_report_month"] == "2099-01"
    assert payload["effective_report_month"] == "2025-12"
    assert payload["date_resolution_status"] == "fallback_to_latest_report_month"
    assert payload["fallback_used"] is True
