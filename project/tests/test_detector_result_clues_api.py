from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app
from detector_result_test_utils import override_detector_service


def test_detector_clues_api_returns_non_high_risk_rule_clues_without_creating_risk_entities() -> (
    None
):
    with override_detector_service():
        clues_response = TestClient(app).get(
            "/api/v1/detectors/clues",
            params={"page_size": 10},
        )
        risk_entities_response = TestClient(app).get("/api/v1/risk-entities")

    assert clues_response.status_code == 200
    payload = clues_response.json()
    items = payload["items"]
    non_high = next(item for item in items if item["detector_clue_id"] == "clue_non_high")

    assert non_high["is_monthly_high_risk_entity"] is False
    assert non_high["risk_entity_id"] == ""
    assert "detector_score" in non_high
    assert "detector_probability" not in json.dumps(payload)
    assert "detector_score is rule inspection score" in " ".join(payload["semantic_caveats"])

    assert risk_entities_response.status_code == 200
    risk_entity_ids = {item["entity_id"] for item in risk_entities_response.json()["entities"]}
    assert "clue_non_high" not in risk_entity_ids
    assert "" not in risk_entity_ids


def test_detector_clues_api_does_not_filter_by_monthly_candidate_state() -> None:
    with override_detector_service():
        response = TestClient(app).get("/api/v1/detectors/clues")

    assert response.status_code == 200
    items = response.json()["items"]
    assert items
    assert {item["detector_clue_id"] for item in items} >= {"clue_non_high"}


def test_detector_clues_supports_request_filters_sorting_and_pagination() -> None:
    with override_detector_service():
        filtered = TestClient(app).get(
            "/api/v1/detectors/clues",
            params={"detector_category": "sales", "detector_level": "watch"},
        )
        paged = TestClient(app).get(
            "/api/v1/detectors/clues",
            params={"sort_by": "detector_score", "sort_order": "asc", "page_size": 1},
        )

    assert filtered.status_code == 200
    assert [item["detector_clue_id"] for item in filtered.json()["items"]] == ["clue_non_high"]
    assert paged.status_code == 200
    payload = paged.json()
    assert payload["items"][0]["detector_clue_id"] == "clue_non_high"
    assert payload["pagination"] == {"page": 1, "page_size": 1, "total": 2, "total_pages": 2}
    assert payload["sort"] == {"sort_by": "detector_score", "sort_order": "asc"}
