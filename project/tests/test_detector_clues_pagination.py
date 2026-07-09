from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from observation_context_test_utils import configure_formal_observation_env


def test_detector_clues_pagination_and_top_n_limit_response_size(monkeypatch) -> None:
    configure_formal_observation_env(monkeypatch)

    response = TestClient(app).get(
        "/api/v1/daily-detector/clues",
        params={
            "observation_date": "2025-12-01",
            "page": 1,
            "page_size": 3,
            "top_n": 3,
            "sort_by": "detector_score",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["detector_run_available"] is True
    assert payload["run_date"] == "2025-12-01"
    assert payload["pagination"]["page_size"] == 3
    assert len(payload["items"]) <= 3
    assert len(payload["clues"]) <= 3


def test_workbench_only_embeds_top_rule_clues(monkeypatch) -> None:
    configure_formal_observation_env(monkeypatch)

    response = TestClient(app).get(
        "/api/v1/workbench",
        params={"observation_date": "2025-12-01", "top_n": 5},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["top_rule_clues"]) <= 5
    assert len(payload["daily_detector_summary"].get("top_clues") or []) <= 5
