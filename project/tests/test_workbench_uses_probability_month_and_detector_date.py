from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.routes_frontend_pages import get_frontend_page_service
from app.main import app
from observation_context_test_utils import configure_formal_observation_env


def test_workbench_uses_probability_month_and_detector_date(monkeypatch) -> None:
    configure_formal_observation_env(monkeypatch)
    get_frontend_page_service.cache_clear()
    try:
        response = TestClient(app).get(
            "/api/v1/workbench",
            params={"observation_date": "2025-12-05", "horizon": "H6", "top_n": 3},
        )
    finally:
        get_frontend_page_service.cache_clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["report_context"]["probability_report_month"] == "2025-11"
    assert payload["report_context"]["detector_run_date"] == "2025-12-05"
    assert payload["batch_context"]["report_month"] == "2025-11"
    assert payload["daily_detector_summary"]["ready"] is False
    assert payload["top_rule_clues"] == []
    assert len(payload["risk_entities"]) <= 3
