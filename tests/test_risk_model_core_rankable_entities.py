import pandas as pd

from risk_model_core.manifest import RiskResultManifest
from risk_model_core.repositories import InMemoryRiskResultRepository
from risk_model_core.services import RiskQueryService


def make_manifest() -> RiskResultManifest:
    return RiskResultManifest(
        batch_id="test-batch",
        report_type="monthly",
        report_month="2025-12",
        report_date="2025-12-31",
        score_cutoff_month="2025-12",
        primary_horizon="H6",
        available_horizons=["H3", "H6", "H12"],
        schema_version="test",
        data_backend="in_memory",
        allowed_usage=["backend_api"],
        forbidden_usage=["auto_dispatch"],
        customer_facing_probability_service_allowed=False,
        auto_dispatch_allowed=False,
        proof_case_report_allowed=False,
        caveats=[],
        raw={},
    )


def make_repository() -> InMemoryRiskResultRepository:
    risk_entities = pd.DataFrame(
        [
            {
                "risk_entity_id": "e1",
                "candidate_id": "c1",
                "tenant_id": "t",
                "manufacturer_code": "M1",
                "hospital_code": "H1",
                "drug_group": "D1",
                "report_month": "2025-12",
                "primary_horizon": "H6",
                "risk_probability_value": 0.71,
                "risk_score_display": 8.0,
                "business_priority_score": 100.0,
                "purchase_interval_overdue_score": 3.0,
                "purchase_frequency_drop_score": 2.0,
                "final_candidate_status": "priority_review",
                "risk_level": "high",
                "review_status": "pending",
                "auto_dispatch_allowed": False,
                "is_one_shot": False,
                "is_observation": False,
            },
            {
                "risk_entity_id": "e2",
                "candidate_id": "c2",
                "tenant_id": "t",
                "manufacturer_code": "M2",
                "hospital_code": "H2",
                "drug_group": "D2",
                "report_month": "2025-12",
                "primary_horizon": "H6",
                "risk_probability_value": 0.95,
                "risk_score_display": 9.0,
                "business_priority_score": 200.0,
                "purchase_interval_overdue_score": 5.0,
                "purchase_frequency_drop_score": 4.0,
                "final_candidate_status": "priority_review",
                "risk_level": "high",
                "review_status": "pending",
                "auto_dispatch_allowed": False,
                "is_one_shot": False,
                "is_observation": False,
            },
            {
                "risk_entity_id": "e3",
                "candidate_id": "c3",
                "tenant_id": "t",
                "manufacturer_code": "M1",
                "hospital_code": "H3",
                "drug_group": "D3",
                "report_month": "2025-12",
                "primary_horizon": "H6",
                "risk_probability_value": None,
                "risk_score_display": 7.0,
                "business_priority_score": 80.0,
                "purchase_interval_overdue_score": 1.0,
                "purchase_frequency_drop_score": 1.0,
                "final_candidate_status": "one_shot_attention",
                "risk_level": "attention",
                "review_status": "new_terminal",
                "auto_dispatch_allowed": False,
                "is_one_shot": True,
                "is_observation": False,
            },
            {
                "risk_entity_id": "e4",
                "candidate_id": "c4",
                "tenant_id": "t",
                "manufacturer_code": "M3",
                "hospital_code": "H4",
                "drug_group": "D4",
                "report_month": "2025-11",
                "primary_horizon": "H6",
                "risk_probability_value": 0.5,
                "risk_score_display": 6.0,
                "business_priority_score": 60.0,
                "purchase_interval_overdue_score": 2.0,
                "purchase_frequency_drop_score": 1.0,
                "final_candidate_status": "observation_only",
                "risk_level": "observation",
                "review_status": "watching",
                "auto_dispatch_allowed": False,
                "is_one_shot": False,
                "is_observation": True,
            },
        ]
    )
    return InMemoryRiskResultRepository(make_manifest(), {"risk_entities": risk_entities})


def test_repository_lists_rankable_entities_for_backend_resolved_manufacturer_scope() -> None:
    repo = make_repository()

    rows = repo.list_rankable_entities(
        manufacturer_codes=["M1", "M3"],
        report_month="2025-12",
        horizon="H6",
        candidate_type="recurring",
        sort_by=["business_priority_score", "risk_score_display"],
    )

    assert rows["risk_entity_id"].tolist() == ["e1"]
    assert "business_priority_score" in rows.columns
    assert "risk_probability_value" in rows.columns
    assert "purchase_interval_overdue_score" in rows.columns
    assert "purchase_frequency_drop_score" in rows.columns


def test_service_reports_shortage_without_filling_or_treating_manufacturer_as_user() -> None:
    service = RiskQueryService(make_repository())

    result = service.list_rankable_entities(
        manufacturer_codes=["M1", "M3"],
        report_month="2025-12",
        horizon="H6",
        candidate_type="recurring",
        target_min=20,
        limit=50,
    )

    assert [item["risk_entity_id"] for item in result["items"]] == ["e1"]
    assert result["available_count"] == 1
    assert result["returned_count"] == 1
    assert result["shortage_count"] == 19
    assert result["scope"]["manufacturer_codes"] == ["M1", "M3"]
    assert result["scope"]["scope_resolved_by_backend"] is True
    assert result["scope"]["manufacturer_code_is_user_scope"] is False
