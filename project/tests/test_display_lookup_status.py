from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from risk_model_core.manifest import RiskResultManifest
from risk_model_core.repositories import InMemoryRiskResultRepository


def test_display_lookup_status_endpoint_returns_missing_when_lookup_is_not_available() -> None:
    from app.api.routes_display_lookup import get_display_lookup_service
    from app.services.display_lookup_service import DisplayLookupService

    app.dependency_overrides[get_display_lookup_service] = lambda: DisplayLookupService(
        InMemoryRiskResultRepository(_manifest(), {})
    )
    try:
        response = TestClient(app).get("/api/v1/display-lookup/status")
    finally:
        app.dependency_overrides.pop(get_display_lookup_service, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is False
    assert payload["status"] == "missing"
    assert payload["source"] == "risk_model_core"
    assert payload["table"] == "entity_display_lookup"
    assert payload["row_count"] == 0
    assert payload["hospital_name_ready"] is False
    assert payload["drug_name_ready"] is False
    assert payload["manufacturer_name_ready"] is False
    assert payload["region_ready"] is False
    assert payload["warnings"] == ["ENTITY_DISPLAY_LOOKUP_NOT_AVAILABLE"]


def test_display_lookup_status_endpoint_returns_ready_when_model_repository_returns_lookup() -> (
    None
):
    from app.api.routes_display_lookup import get_display_lookup_service
    from app.services.display_lookup_service import DisplayLookupService

    app.dependency_overrides[get_display_lookup_service] = lambda: DisplayLookupService(
        InMemoryRiskResultRepository(_manifest(), {"entity_display_lookup": _lookup()})
    )
    try:
        response = TestClient(app).get("/api/v1/display-lookup/status")
    finally:
        app.dependency_overrides.pop(get_display_lookup_service, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["status"] == "ready"
    assert payload["source"] == "risk_model_core"
    assert payload["table"] == "entity_display_lookup"
    assert payload["row_count"] == 1
    assert payload["schema_version"] == "v1"
    assert payload["hospital_name_ready"] is True
    assert payload["drug_name_ready"] is True
    assert payload["manufacturer_name_ready"] is True
    assert payload["region_ready"] is True
    assert payload["warnings"] == []


def test_display_lookup_status_endpoint_returns_conditional_when_display_values_echo_codes() -> None:
    from app.api.routes_display_lookup import get_display_lookup_service
    from app.services.display_lookup_service import DisplayLookupService

    app.dependency_overrides[get_display_lookup_service] = lambda: DisplayLookupService(
        InMemoryRiskResultRepository(
            _manifest(),
            {
                "entity_display_lookup": pd.DataFrame(
                    [
                        {
                            "tenant_id": "tenant",
                            "report_month": "2025-12",
                            "manufacturer_code": "M1",
                            "manufacturer_display_name": "M1",
                            "hospital_code": "H1",
                            "hospital_display_name": "H1",
                            "drug_code": "D1",
                            "drug_group": "D1",
                            "drug_display_name": "D1",
                            "region_code": "R1",
                            "region_display_name": "R1",
                            "display_name_quality": "master",
                        }
                    ]
                )
            },
        )
    )
    try:
        response = TestClient(app).get("/api/v1/display-lookup/status")
    finally:
        app.dependency_overrides.pop(get_display_lookup_service, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] == "conditional"
    assert payload["manufacturer_name_ready"] is False
    assert payload["hospital_name_ready"] is False
    assert payload["drug_name_ready"] is False
    assert payload["fallback_policy"] == "code_fallback_when_display_equals_code"


def test_frontend_payloads_continue_when_display_lookup_is_missing() -> None:
    from app.api.routes_display_lookup import get_display_lookup_service
    from app.services.display_lookup_service import DisplayLookupService

    app.dependency_overrides[get_display_lookup_service] = lambda: DisplayLookupService(
        InMemoryRiskResultRepository(_manifest(), {})
    )
    try:
        client = TestClient(app)
        workbench = client.get("/api/v1/workbench")
        risk_entities = client.get("/api/v1/risk-entities")
        proof_cases = client.get("/api/v1/proof-cases")
    finally:
        app.dependency_overrides.pop(get_display_lookup_service, None)

    for response in [workbench, risk_entities, proof_cases]:
        assert response.status_code == 200
        assert response.json()["display_lookup_status"]["ready"] is False
        assert response.json()["display_lookup_status"]["warnings"] == [
            "ENTITY_DISPLAY_LOOKUP_NOT_AVAILABLE"
        ]


def test_top_entities_payload_includes_display_lookup_status_without_requiring_lookup() -> None:
    from app.api.routes_display_lookup import get_display_lookup_service
    from app.api.routes_user_top_entities import get_user_top_entity_service
    from app.services.display_lookup_service import DisplayLookupService
    from app.services.user_top_entity_service import TopEntityService

    repository = InMemoryRiskResultRepository(_manifest(), {"risk_entities": _risk_entities()})
    app.dependency_overrides[get_user_top_entity_service] = lambda: TopEntityService(repository)
    app.dependency_overrides[get_display_lookup_service] = lambda: DisplayLookupService(repository)
    try:
        response = TestClient(app).get("/api/risk/my/top-entities", params={"top_n": 1})
    finally:
        app.dependency_overrides.pop(get_user_top_entity_service, None)
        app.dependency_overrides.pop(get_display_lookup_service, None)

    assert response.status_code == 200
    assert response.json()["display_lookup_status"]["ready"] is False


def test_project_display_lookup_path_does_not_import_algo_main_or_raw_source_db() -> None:
    project_root = Path(__file__).resolve().parents[1]
    sources = [
        project_root / "app" / "api" / "routes_display_lookup.py",
        project_root / "app" / "services" / "display_lookup_service.py",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in sources)

    for forbidden in [
        "algo_main",
        "DATABASE_URL",
        "sql_table_adapter",
        "backbone_service",
        "app.algorithms",
        "front_end",
        "read_csv",
        "read_parquet",
    ]:
        assert forbidden not in text


def _lookup() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "tenant_id": "tenant",
                "report_month": "2025-12",
                "manufacturer_code": "m1",
                "manufacturer_display_name": "Manufacturer One",
                "hospital_code": "h1",
                "hospital_display_name": "Hospital One",
                "drug_code": "d1",
                "drug_group": "d1",
                "drug_display_name": "Drug One",
                "product_line_code": "pl1",
                "product_line_name": "Line One",
                "region_code": "r1",
                "region_display_name": "Region One",
                "display_key": "tenant|2025-12|m1|h1|d1",
                "display_name_source": "master",
                "display_name_quality": "master",
                "source_raw_batch_id": "raw",
                "updated_at": "2026-07-08T00:00:00+00:00",
            }
        ]
    )


def _risk_entities() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "risk_entity_id": "re_1",
                "candidate_id": "candidate_1",
                "tenant_id": "tenant",
                "manufacturer_code": "m1",
                "hospital_code": "h1",
                "drug_group": "d1",
                "report_month": "2025-12",
                "primary_horizon": "H6",
                "risk_probability_value": 0.9,
                "risk_level": "orange",
                "review_status": "recurring",
                "final_candidate_status": "recurring",
                "auto_dispatch_allowed": False,
                "is_one_shot": False,
                "is_observation": False,
                "is_high_risk": True,
            }
        ]
    )


def _manifest() -> RiskResultManifest:
    return RiskResultManifest(
        batch_id="display-lookup-test",
        report_type="monthly",
        report_month="2025-12",
        report_date="2025-12-31",
        score_cutoff_month="2025-12-31",
        primary_horizon="H6",
        available_horizons=["H6"],
        schema_version="test",
        data_backend="in_memory",
        allowed_usage=["backend_api"],
        forbidden_usage=[],
        customer_facing_probability_service_allowed=False,
        auto_dispatch_allowed=False,
        proof_case_report_allowed=False,
        caveats=[],
        raw={},
    )
