from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app
from observation_context_test_utils import configure_formal_observation_env


def test_runtime_profile_is_internal_diagnostics_only(monkeypatch) -> None:
    configure_formal_observation_env(monkeypatch)

    response = TestClient(app).get("/api/v1/runtime-profile", params={"report_month": "2025-11"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["visibility"] == "internal_diagnostics_only"
    assert "monthly_probability_total_seconds" in payload["runtime_profile"]
    assert "detector_total_seconds" in payload["runtime_profile"]


def test_workbench_does_not_expose_runtime_profile(monkeypatch) -> None:
    configure_formal_observation_env(monkeypatch)

    response = TestClient(app).get(
        "/api/v1/workbench",
        params={"observation_date": "2025-12-01", "top_n": 3},
    )

    assert response.status_code == 200
    text = json.dumps(response.json(), ensure_ascii=False)
    assert "monthly_probability_total_seconds" not in text
    assert "detector_total_seconds" not in text
    assert "end_to_end_seconds" not in text
