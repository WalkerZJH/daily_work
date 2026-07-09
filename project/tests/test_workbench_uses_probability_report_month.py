from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.api.routes_frontend_pages import get_frontend_page_service
from app.main import app
from observation_context_test_utils import configure_formal_observation_env


def test_workbench_uses_probability_report_month_from_observation_context(monkeypatch) -> None:
    configure_formal_observation_env(monkeypatch, legacy_report_month="2025-12")
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
    assert payload["ready"] is True
    assert payload["report_context"]["probability_report_month"] == "2025-11"
    assert payload["report_context"]["detector_run_date"] == "2025-12-05"
    assert payload["batch_context"]["report_month"] == "2025-11"
    assert payload["current_observation_date"] == "2025-12-05"
    assert payload["risk_entities"]
    text = json.dumps(payload, ensure_ascii=False)
    assert "fill_policy" not in text
    assert "business_score" not in text
