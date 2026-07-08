from __future__ import annotations

import pandas as pd

from risk_model_core.manifest import RiskResultManifest
from risk_model_core.page_payload_builder import PagePayloadBuilder
from risk_model_core.repositories import InMemoryRiskResultRepository


def repository_without_payload_json() -> InMemoryRiskResultRepository:
    manifest = RiskResultManifest(
        batch_id="core-dynamic",
        report_type="monthly",
        report_month="2025-12",
        report_date="2025-12-31",
        score_cutoff_month="2025-12-31",
        primary_horizon="H6",
        available_horizons=["H3", "H6", "H12"],
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
    risk_entities = pd.DataFrame(
        [
            {
                "risk_entity_id": "entity-1",
                "candidate_id": "candidate-1",
                "tenant_id": "tenant",
                "manufacturer_code": "M1",
                "hospital_code": "H1",
                "hospital_display_name": "Hospital One",
                "drug_group": "D1",
                "drug_display_name": "Drug One",
                "report_month": "2025-12",
                "primary_horizon": "H6",
                "risk_probability_value": 0.8,
                "value_at_risk_H": 100,
                "risk_level": "high",
                "risk_color": "red",
                "review_status": "pending",
                "final_candidate_status": "priority_review",
                "auto_dispatch_allowed": False,
                "is_one_shot": False,
                "is_observation": False,
            }
        ]
    )
    return InMemoryRiskResultRepository(
        manifest,
        {
            "risk_entities": risk_entities,
            "risk_cards": pd.DataFrame(),
            "risk_card_evidence": pd.DataFrame(),
            "risk_entity_timeline": pd.DataFrame(),
            "monthly_reports": pd.DataFrame(),
            "proof_cases": pd.DataFrame(),
        },
    )


def test_dynamic_workbench_payload_uses_result_batch_rows_without_demo_fill() -> None:
    payload = PagePayloadBuilder(repository_without_payload_json()).build_frontend_workbench_payload()

    assert payload["batch_context"]["result_batch_id"] == "core-dynamic"
    assert len(payload["rows"]) == 1
    assert payload["rows"][0]["entity_id"] == "entity-1"
    assert payload["rows"][0]["business_score"] == 80
    assert payload["meta"]["model_core_filled_shortage"] is False


def test_dynamic_detail_payload_contains_all_horizons_and_neutral_shap() -> None:
    detail = PagePayloadBuilder(repository_without_payload_json()).build_frontend_risk_entity_detail_payload("entity-1")

    assert set(detail["horizon_profiles"]) == {"H3", "H6", "H12"}
    for profile in detail["horizon_profiles"].values():
        assert profile["detector_results"]
        assert profile["xgboost_shap"] == []
        assert profile["detector_narrative"]
