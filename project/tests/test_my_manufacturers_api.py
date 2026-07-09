from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from frontend_api_test_utils import override_frontend_result_repository


def test_my_manufacturers_returns_batch_fallback_scope_without_404() -> None:
    with override_frontend_result_repository():
        response = TestClient(app).get(
            "/api/v1/my/manufacturers",
            params={
                "user_id": "user_without_real_scope",
                "report_month": "2025-12",
                "run_date": "2025-12-31",
                "horizon": "H6",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_user_id"] == "user_without_real_scope"
    assert payload["ready"] == "conditional"
    assert payload["scope_source"] == "batch_manufacturer_fallback"
    assert payload["requested_run_date"] == "2025-12-31"
    assert payload["effective_run_date"] == "2025-12-31"
    assert payload["date_resolution_status"] == "exact_match"
    assert payload["default_manufacturer_code"] == "M1"
    assert [item["manufacturer_code"] for item in payload["manufacturers"]] == ["M1", "M2"]
