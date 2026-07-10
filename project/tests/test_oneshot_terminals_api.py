from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from frontend_api_test_utils import make_frontend_repository, override_frontend_result_repository


def test_oneshot_terminals_uses_context_and_result_batch_display_lookup() -> None:
    repo = make_frontend_repository()
    entities = repo.tables["risk_entities"].copy()
    entities.loc[entities["risk_entity_id"].eq("entity_1"), "is_one_shot"] = True
    entities.loc[entities["risk_entity_id"].eq("entity_1"), "final_candidate_status"] = "one_shot_attention"
    entities.loc[entities["risk_entity_id"].eq("entity_1"), "review_status"] = "one_shot_attention"
    repo.tables["risk_entities"] = entities

    with override_frontend_result_repository(repo):
        response = TestClient(app).get(
            "/api/v1/oneshot-terminals",
            params={
                "user_id": "admin",
                "observation_date": "2025-12-31",
                "horizon": "H6",
                "top_n": 5,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["total"] == len(payload["items"])
    assert payload["items"]
    assert payload["items"][0]["manufacturer_name"] == "Manufacturer One"
    assert payload["items"][0]["manufacturer_name"] != payload["items"][0]["manufacturer_code"]
    assert payload["items"][0]["hospital_name"] == "Hospital One"
    assert payload["items"][0]["drug_name"] == "Drug One"
