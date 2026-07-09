from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app
from frontend_api_test_utils import override_frontend_result_repository


def test_workbench_response_has_no_fill_policy_or_business_score() -> None:
    with override_frontend_result_repository():
        response = TestClient(app).get(
            "/api/v1/workbench",
            params={"top_n": 2, "sort_by": "loss_value"},
        )

    assert response.status_code == 200
    text = json.dumps(response.json(), ensure_ascii=False)
    assert "fill_policy" not in text
    assert "business_score" not in text
    assert "risk_probability * average_consumption_in_window" not in text
