from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.frontend_page_service import FrontendPageService
from frontend_api_test_utils import make_frontend_repository, override_frontend_result_repository


def _get(repo, **params):
    with override_frontend_result_repository(repo):
        return TestClient(app).get(
            "/api/v1/oneshot-terminals",
            params={"user_id": "admin", "observation_date": "2025-12-31", **params},
        )


def test_oneshot_terminals_reads_formal_table_and_exposes_only_facts() -> None:
    response = _get(make_frontend_repository(), manufacturer_code="M1", page_size=5)

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["source_table"] == "oneshot_terminals"
    assert payload["source_schema_version"] == "oneshot_terminal_v1"
    assert payload["result_batch_id"] == "frontend-api-test"
    assert payload["score_cutoff_date"] == "2025-12-31"
    assert payload["total"] == 2
    assert payload["summary"] == {"oneshot_count": 2}
    assert payload["items"][0]["manufacturer_name"] == "Manufacturer One"
    assert payload["items"][0]["hospital_name"] == "Hospital One"
    assert payload["items"][0]["drug_name"] == "Drug One"
    forbidden = {
        "repurchase_propensity",
        "expected_repurchase_amount",
        "priority",
        "ranking_basis",
        "reason",
    }
    assert forbidden.isdisjoint(payload["summary"])
    assert all(forbidden.isdisjoint(item) for item in payload["items"])


def test_oneshot_terminals_supports_server_pagination_and_fact_sorting() -> None:
    repo = make_frontend_repository()
    first = _get(
        repo,
        manufacturer_code="M1",
        page=1,
        page_size=1,
        sort_by="first_purchase_amount",
        sort_order="asc",
    ).json()
    second = _get(
        repo,
        manufacturer_code="M1",
        page=2,
        page_size=1,
        sort_by="first_purchase_amount",
        sort_order="asc",
    ).json()

    assert first["pagination"] == {"page": 1, "page_size": 1, "total": 2, "total_pages": 2}
    assert second["pagination"] == {"page": 2, "page_size": 1, "total": 2, "total_pages": 2}
    assert first["items"][0]["first_purchase_amount"] == 800
    assert second["items"][0]["first_purchase_amount"] == 1200
    assert first["sort"] == {"sort_by": "first_purchase_amount", "sort_order": "asc"}


def test_oneshot_terminals_out_of_range_page_is_an_explicit_empty_page() -> None:
    payload = _get(make_frontend_repository(), manufacturer_code="M1", page=3, page_size=1).json()

    assert payload["ready"] is True
    assert payload["total"] == 2
    assert payload["pagination"]["total_pages"] == 2
    assert payload["items"] == []


def test_oneshot_terminals_rejects_prediction_sort() -> None:
    response = _get(make_frontend_repository(), sort_by="repurchase_propensity")

    assert response.status_code == 422
    assert response.json()["detail"]["error_code"] == "ONESHOT_SORT_NOT_ALLOWED"


def test_oneshot_missing_formal_declaration_does_not_fall_back_to_risk_entities() -> None:
    repo = make_frontend_repository()
    repo._manifest.raw.pop("oneshot_terminals")
    repo.tables.pop("oneshot_terminals")
    entities = repo.tables["risk_entities"].copy()
    entities.loc[:, "is_one_shot"] = True
    entities.loc[:, "candidate_type"] = "one_shot"
    repo.tables["risk_entities"] = entities

    payload = _get(repo, manufacturer_code="M1").json()

    assert payload["ready"] is False
    assert payload["availability_status"] == "unavailable"
    assert payload["error_code"] == "ONESHOT_RESULT_NOT_AVAILABLE"
    assert payload["items"] == []
    assert payload["total"] == 0


def test_oneshot_service_without_batch_does_not_return_default_mock(monkeypatch) -> None:
    monkeypatch.delenv("ALLOW_MOCK_PAYLOADS", raising=False)

    payload = FrontendPageService().oneshot_terminals(page=2, page_size=20)

    assert payload["ready"] is False
    assert payload["error_code"] == "ONESHOT_RESULT_NOT_AVAILABLE"
    assert payload["pagination"] == {"page": 2, "page_size": 20, "total": 0, "total_pages": 0}
    assert payload["items"] == []
