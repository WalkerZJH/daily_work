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
            "risk_entity_horizon_profiles": pd.DataFrame(
                [
                    {
                        "risk_entity_id": "entity-1",
                        "report_month": "2025-12",
                        "horizon": "H3",
                        "risk_probability": 0.7,
                        "involved_amount": 30,
                        "involved_amount_source": "purchase_amount_sum_last_3m_asof_cutoff",
                        "risk_level": "yellow",
                        "risk_band": "Observation",
                        "main_reason_summary": "H3 profile",
                        "reason": "H3 profile",
                        "detector_evidence_count": 0,
                        "updated_at": "2025-12-31T00:00:00+00:00",
                    },
                    {
                        "risk_entity_id": "entity-1",
                        "report_month": "2025-12",
                        "horizon": "H6",
                        "risk_probability": 0.8,
                        "involved_amount": 60,
                        "involved_amount_source": "purchase_amount_sum_last_6m_asof_cutoff",
                        "risk_level": "high",
                        "risk_band": "High risk",
                        "main_reason_summary": "H6 profile",
                        "reason": "H6 profile",
                        "detector_evidence_count": 0,
                        "updated_at": "2025-12-31T00:00:00+00:00",
                    },
                    {
                        "risk_entity_id": "entity-1",
                        "report_month": "2025-12",
                        "horizon": "H12",
                        "risk_probability": 0.9,
                        "involved_amount": 120,
                        "involved_amount_source": "purchase_amount_sum_last_12m_asof_cutoff",
                        "risk_level": "high",
                        "risk_band": "High risk",
                        "main_reason_summary": "H12 profile",
                        "reason": "H12 profile",
                        "detector_evidence_count": 0,
                        "updated_at": "2025-12-31T00:00:00+00:00",
                    },
                ]
            ),
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
    assert payload["rows"][0]["involved_amount"] == 60
    assert payload["rows"][0]["involved_amount_source"] == "purchase_amount_sum_last_6m_asof_cutoff"
    assert "business_score" not in payload["rows"][0]
    assert payload["meta"]["model_core_filled_shortage"] is False


def test_dynamic_detail_payload_contains_all_horizons_and_neutral_shap() -> None:
    detail = PagePayloadBuilder(repository_without_payload_json()).build_frontend_risk_entity_detail_payload("entity-1")

    assert set(detail["horizon_profiles"]) == {"H3", "H6", "H12"}
    assert detail["horizon_profiles"]["H3"]["involved_amount"] == 30
    assert detail["horizon_profiles"]["H12"]["risk_probability"] == 0.9
    for profile in detail["horizon_profiles"].values():
        assert profile["detector_results"]
        assert profile["xgboost_shap"] == []
        assert profile["detector_narrative"]
        assert "business_score" not in profile
