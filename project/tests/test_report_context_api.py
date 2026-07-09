from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from frontend_api_test_utils import override_frontend_result_repository


def test_report_context_api_returns_requested_and_effective_dates() -> None:
    with override_frontend_result_repository():
        response = TestClient(app).get(
            "/api/v1/report-context",
            params={
                "report_month": "2025-12",
                "run_date": "2025-12-31",
                "horizon": "H6",
                "manufacturer_code": "M1",
                "user_id": "frontend_user",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["requested_report_month"] == "2025-12"
    assert payload["effective_report_month"] == "2025-12"
    assert payload["requested_run_date"] == "2025-12-31"
    assert payload["effective_run_date"] == "2025-12-31"
    assert payload["requested_horizon"] == "H6"
    assert payload["effective_horizon"] == "H6"
    assert payload["date_resolution_status"] == "exact_match"
    assert payload["batch_id"] == "frontend-api-test"
    assert payload["available_report_months"] == ["2025-12"]
    assert payload["available_run_dates"] == ["2025-12-31"]
    assert payload["available_horizons"] == ["H3", "H6", "H12"]
    assert payload["fallback_used"] is False
