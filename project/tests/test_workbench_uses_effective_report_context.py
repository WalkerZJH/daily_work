from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from frontend_api_test_utils import override_frontend_result_repository


def test_workbench_uses_effective_report_context_for_missing_today() -> None:
    today = date.today().isoformat()
    with override_frontend_result_repository():
        response = TestClient(app).get(
            "/api/v1/workbench",
            params={
                "report_month": "2099-01",
                "run_date": today,
                "horizon": "H99",
                "top_n": 2,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    context = payload["report_context"]
    assert context["requested_report_month"] == "2099-01"
    assert context["effective_report_month"] == "2025-12"
    assert context["requested_run_date"] == today
    assert context["effective_run_date"] == "2025-12-31"
    assert context["effective_horizon"] == "H6"
    assert context["fallback_used"] is True
    assert payload["requested_run_date"] == today
    assert payload["effective_run_date"] == "2025-12-31"
    assert payload["batch_context"]["report_month"] == "2025-12"
    assert payload["horizon"] == "H6"
    assert payload["current_observation_date"] == "2025-12-31"
