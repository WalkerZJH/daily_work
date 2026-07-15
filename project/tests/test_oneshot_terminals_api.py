from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from frontend_api_test_utils import make_frontend_repository, override_frontend_result_repository


def test_oneshot_terminals_returns_only_formal_facts_with_batch_context() -> None:
    with override_frontend_result_repository(make_frontend_repository()):
        response = TestClient(app).get(
            "/api/v1/oneshot-terminals",
            params={
                "user_id": "admin",
                "observation_date": "2025-12-31",
                "manufacturer_code": "M1",
                "page": 1,
                "page_size": 2,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["status"] == "ready"
    assert payload["report_month"] == "2025-12"
    assert payload["cutoff_date"] == "2025-12-31"
    assert payload["result_batch_id"] == "frontend-api-test"
    assert payload["pagination"] == {"page": 1, "page_size": 2, "total": 3, "total_pages": 2}
    assert len(payload["items"]) == 2
    assert payload["items"][0]["manufacturer_name"] == "Manufacturer One"
    assert payload["items"][0]["manufacturer_name"] != payload["items"][0]["manufacturer_code"]
    assert payload["items"][0]["hospital_name"] == "Hospital One"
    assert payload["items"][0]["drug_name"] == "Drug One"
    for forbidden in [
        "repurchase_propensity",
        "expected_repurchase_amount",
        "priority",
        "reason",
        "ranking_basis",
        "high_repurchase_propensity_count",
        "average_repurchase_propensity",
    ]:
        assert forbidden not in response.text


def test_oneshot_terminals_paginates_filtered_rows_and_sorts_by_formal_fact() -> None:
    with override_frontend_result_repository(make_frontend_repository()):
        response = TestClient(app).get(
            "/api/v1/oneshot-terminals",
            params={
                "manufacturer_code": "M1",
                "observation_date": "2025-12-31",
                "page": 2,
                "page_size": 1,
                "sort_by": "first_purchase_amount",
                "sort_order": "desc",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["oneshot_count"] == 3
    assert payload["summary"]["daily_new_terminal_count"] == 1
    assert payload["summary"]["monthly_new_terminal_count"] == 2
    assert payload["pagination"] == {"page": 2, "page_size": 1, "total": 3, "total_pages": 3}
    assert [item["oneshot_id"] for item in payload["items"]] == ["oneshot_1"]


def test_oneshot_explicit_report_month_is_not_replaced_by_probability_month_resolution() -> None:
    from app.api.routes_report_context import get_report_context_service

    class PreviousProbabilityMonthContext:
        def resolve(self, **_kwargs):
            return {
                "observation_date": "2025-12-05",
                "effective_observation_date": "2025-12-05",
                "effective_report_month": "2025-11",
                "probability_report_month": "2025-11",
                "effective_probability_report_month": "2025-11",
                "probability_batch_available": True,
                "context_status": "ready",
            }

    with override_frontend_result_repository(make_frontend_repository()):
        app.dependency_overrides[get_report_context_service] = PreviousProbabilityMonthContext
        try:
            response = TestClient(app).get(
                "/api/v1/oneshot-terminals",
                params={
                    "report_month": "2025-12",
                    "observation_date": "2025-12-05",
                    "manufacturer_code": "M1",
                },
            )
        finally:
            app.dependency_overrides.pop(get_report_context_service, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["report_month"] == "2025-12"
    assert payload["pagination"]["total"] == 3


def test_oneshot_terminals_out_of_range_page_is_an_explicit_empty_page() -> None:
    with override_frontend_result_repository(make_frontend_repository()):
        response = TestClient(app).get(
            "/api/v1/oneshot-terminals",
            params={"manufacturer_code": "M1", "page": 9, "page_size": 2},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["items"] == []
    assert payload["pagination"] == {"page": 9, "page_size": 2, "total": 3, "total_pages": 2}


def test_oneshot_terminals_rejects_prediction_sort_fields() -> None:
    with override_frontend_result_repository(make_frontend_repository()):
        response = TestClient(app).get(
            "/api/v1/oneshot-terminals",
            params={"sort_by": "repurchase_propensity", "sort_order": "desc"},
        )

    assert response.status_code == 422
    assert response.json()["detail"]["error_code"] == "ONESHOT_SORT_NOT_AVAILABLE"


def test_oneshot_terminals_missing_formal_table_does_not_fallback_to_risk_entities() -> None:
    repo = make_frontend_repository()
    repo.tables.pop("oneshot_terminals")
    entities = repo.tables["risk_entities"].copy()
    entities["candidate_type"] = "one_shot"
    entities["is_one_shot"] = True
    repo.tables["risk_entities"] = entities

    with override_frontend_result_repository(repo):
        response = TestClient(app).get("/api/v1/oneshot-terminals")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is False
    assert payload["status"] == "ONESHOT_RESULT_NOT_AVAILABLE"
    assert payload["items"] == []
    assert payload["pagination"]["total"] == 0


def test_oneshot_terminals_does_not_fabricate_missing_fact_values() -> None:
    repo = make_frontend_repository()
    rows = repo.tables["oneshot_terminals"].copy()
    missing = rows["oneshot_id"].eq("oneshot_1")
    rows.loc[missing, ["first_purchase_date", "first_purchase_amount", "days_since_first_purchase"]] = None
    repo.tables["oneshot_terminals"] = rows

    with override_frontend_result_repository(repo):
        response = TestClient(app).get(
            "/api/v1/oneshot-terminals",
            params={"manufacturer_code": "M1", "sort_by": "first_purchase_amount", "sort_order": "desc"},
        )

    assert response.status_code == 200
    item = next(item for item in response.json()["items"] if item["oneshot_id"] == "oneshot_1")
    assert item["first_purchase_date"] is None
    assert item["first_purchase_amount"] is None
    assert item["days_since_first_purchase"] is None
