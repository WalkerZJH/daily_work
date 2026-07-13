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


def test_oneshot_terminals_counts_daily_and_monthly_new_terminals_without_horizon_filter() -> None:
    repo = make_frontend_repository()
    entities = repo.tables["risk_entities"].copy()
    oneshot_mask = entities["risk_entity_id"].isin(["entity_1", "entity_2"])
    entities.loc[oneshot_mask, "is_one_shot"] = True
    entities.loc[oneshot_mask, "final_candidate_status"] = "one_shot_attention"
    entities.loc[oneshot_mask, "review_status"] = "one_shot_attention"
    entities.loc[oneshot_mask, "candidate_type"] = "one_shot"
    entities.loc[entities["risk_entity_id"].eq("entity_1"), "first_purchase_date"] = "2025-12-31"
    entities.loc[entities["risk_entity_id"].eq("entity_2"), "first_purchase_date"] = "2025-12-05"
    entities.loc[entities["risk_entity_id"].eq("entity_1"), "first_purchase_amount"] = 1200
    entities.loc[entities["risk_entity_id"].eq("entity_2"), "first_purchase_amount"] = 800
    repo.tables["risk_entities"] = entities

    with override_frontend_result_repository(repo):
        response = TestClient(app).get(
            "/api/v1/oneshot-terminals",
            params={
                "user_id": "admin",
                "manufacturer_code": "M1",
                "observation_date": "2025-12-31",
                "horizon": "H12",
                "top_n": 5,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["summary"]["oneshot_count"] == 2
    assert payload["summary"]["daily_new_terminal_count"] == 1
    assert payload["summary"]["monthly_new_terminal_count"] == 2
    assert {item["oneshot_id"] for item in payload["items"]} == {"entity_1", "entity_2"}
    assert payload["items"][0]["first_purchase_date"] in {"2025-12-31", "2025-12-05"}
    assert {item["first_purchase_amount"] for item in payload["items"]} == {1200, 800}
