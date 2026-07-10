from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app
from observation_context_test_utils import configure_formal_observation_env


def test_complete_probability_month_mapping_does_not_use_latest_fallback_wording(monkeypatch) -> None:
    configure_formal_observation_env(monkeypatch)

    response = TestClient(app).get(
        "/api/v1/report-context",
        params={"observation_date": "2025-12-05"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["probability_report_month"] == "2025-11"
    assert payload["probability_batch_available"] is True
    text = json.dumps(payload, ensure_ascii=False)
    assert "fallback_to_latest" not in text
    assert "latest_available" not in text
    assert payload["context_status"] == "ready"
