from __future__ import annotations

import inspect

import pandas as pd

from risk_model_core.manifest import RiskResultManifest
from risk_model_core.page_payload_builder import PagePayloadBuilder
from risk_model_core.repositories import InMemoryRiskResultRepository
import risk_model_core.repositories as repositories
from risk_model_core.schemas import RISK_ENTITY_HORIZON_PROFILE_REQUIRED_COLUMNS, STANDARD_TABLES
from risk_result_contracts.schemas import (
    RISK_ENTITY_HORIZON_PROFILE_REQUIRED_COLUMNS as CONTRACT_HORIZON_PROFILE_REQUIRED_COLUMNS,
    STANDARD_TABLES as CONTRACT_STANDARD_TABLES,
)


def make_manifest() -> RiskResultManifest:
    return RiskResultManifest(
        batch_id="horizon-profile-test",
        report_type="monthly",
        report_month="2026-07",
        report_date="2026-07-31",
        score_cutoff_month="2026-07-31",
        primary_horizon="H6",
        available_horizons=["H3", "H6", "H12"],
        schema_version="risk_result_batch_monthly_v2",
        data_backend="in_memory",
        allowed_usage=["backend_api"],
        forbidden_usage=["raw_data_access", "auto_dispatch"],
        customer_facing_probability_service_allowed=False,
        auto_dispatch_allowed=False,
        proof_case_report_allowed=False,
        caveats=[],
        raw={},
    )


def make_repository() -> InMemoryRiskResultRepository:
    tables = {
        "risk_entities": pd.DataFrame(
            [
                {
                    "risk_entity_id": "entity-1",
                    "candidate_id": "entity-1|H6",
                    "tenant_id": "tenant",
                    "manufacturer_code": "M1",
                    "hospital_code": "H1",
                    "hospital_display_name": "Hospital One",
                    "drug_group": "D1",
                    "drug_display_name": "Drug One",
                    "report_month": "2026-07",
                    "primary_horizon": "H6",
                    "risk_probability_value": 0.62,
                    "risk_level": "orange",
                    "risk_color": "orange",
                    "review_status": "pending",
                    "final_candidate_status": "priority_review",
                    "auto_dispatch_allowed": False,
                    "is_one_shot": False,
                    "is_observation": False,
                }
            ]
        ),
        "risk_entity_horizon_profiles": pd.DataFrame(
            [
                {
                    "risk_entity_id": "entity-1",
                    "report_month": "2026-07",
                    "horizon": "H3",
                    "risk_probability": 0.31,
                    "involved_amount": 300.0,
                    "involved_amount_source": "purchase_amount_sum_last_3m_asof_cutoff",
                    "risk_level": "yellow",
                    "risk_band": "Observation",
                    "main_reason_summary": "H3 monthly profile",
                    "reason": "H3 monthly profile",
                    "detector_evidence_count": 1,
                    "updated_at": "2026-07-31T00:00:00+00:00",
                },
                {
                    "risk_entity_id": "entity-1",
                    "report_month": "2026-07",
                    "horizon": "H6",
                    "risk_probability": 0.62,
                    "involved_amount": 600.0,
                    "involved_amount_source": "purchase_amount_sum_last_6m_asof_cutoff",
                    "risk_level": "orange",
                    "risk_band": "Medium risk",
                    "main_reason_summary": "H6 monthly profile",
                    "reason": "H6 monthly profile",
                    "detector_evidence_count": 1,
                    "updated_at": "2026-07-31T00:00:00+00:00",
                },
                {
                    "risk_entity_id": "entity-1",
                    "report_month": "2026-07",
                    "horizon": "H12",
                    "risk_probability": 0.91,
                    "involved_amount": 1200.0,
                    "involved_amount_source": "purchase_amount_sum_last_12m_asof_cutoff",
                    "risk_level": "red",
                    "risk_band": "High risk",
                    "main_reason_summary": "H12 monthly profile",
                    "reason": "H12 monthly profile",
                    "detector_evidence_count": 1,
                    "updated_at": "2026-07-31T00:00:00+00:00",
                },
            ]
        ),
        "risk_cards": pd.DataFrame(),
        "risk_card_evidence": pd.DataFrame(),
        "risk_entity_timeline": pd.DataFrame(),
        "monthly_reports": pd.DataFrame(),
        "proof_cases": pd.DataFrame(),
        "high_risk_detector_evidence": pd.DataFrame(
            [
                {
                    "risk_entity_id": "entity-1",
                    "detector_run_id": "run-1",
                    "run_date": "2026-07-31",
                    "detector_id": "purchase_interval_ipi",
                    "detector_family": "purchase_interval",
                    "detector_score": 88.0,
                    "confidence": "medium",
                    "root_cause_label": "规则证据命中",
                    "evidence_text": "规则巡检证据。",
                    "evidence_payload": "{}",
                    "caveat": "detector_score is not probability",
                    "created_at": "2026-07-31T00:00:00+00:00",
                }
            ]
        ),
    }
    return InMemoryRiskResultRepository(make_manifest(), tables, payloads={})


def test_horizon_profile_is_standard_result_batch_table() -> None:
    assert "risk_entity_horizon_profiles" in STANDARD_TABLES
    assert "risk_entity_horizon_profiles" in CONTRACT_STANDARD_TABLES
    for required in [
        "risk_entity_id",
        "report_month",
        "horizon",
        "risk_probability",
        "involved_amount",
        "risk_level",
        "risk_band",
        "main_reason_summary",
        "reason",
        "updated_at",
    ]:
        assert required in RISK_ENTITY_HORIZON_PROFILE_REQUIRED_COLUMNS
        assert required in CONTRACT_HORIZON_PROFILE_REQUIRED_COLUMNS


def test_repository_reads_horizon_profiles_only_from_result_batch() -> None:
    rows = make_repository().list_risk_entity_horizon_profiles(risk_entity_id="entity-1", horizon="H6")

    assert len(rows) == 1
    assert rows.iloc[0]["involved_amount"] == 600.0
    source = inspect.getsource(repositories)
    forbidden = ["SQL_DATABASE_URL", "create_engine", "fact_purchase_event", "raw orders"]
    assert not any(token in source for token in forbidden)


def test_detail_payload_uses_result_batch_horizon_profiles_without_loss_value() -> None:
    detail = PagePayloadBuilder(make_repository(), prefer_existing_payloads=False).build_frontend_risk_entity_detail_payload("entity-1")

    assert set(detail["horizon_profiles"]) == {"H3", "H6", "H12"}
    assert detail["horizon_profiles"]["H3"]["risk_probability"] == 0.31
    assert detail["horizon_profiles"]["H3"]["involved_amount"] == 300.0
    assert detail["horizon_profiles"]["H3"]["involved_amount_source"] == "purchase_amount_sum_last_3m_asof_cutoff"
    assert detail["horizon_profiles"]["H12"]["main_reason_summary"] == "H12 monthly profile"
    assert detail["horizon_profiles"]["H12"]["detector_evidence_count"] == 1
    for profile in detail["horizon_profiles"].values():
        assert "loss_value" not in profile
        assert "monthly_loss_value" not in profile
        assert "business_score" not in profile


def test_customer_facing_workbench_payload_does_not_force_loss_value_or_business_score() -> None:
    payload = PagePayloadBuilder(make_repository(), prefer_existing_payloads=False).build_frontend_workbench_payload()

    assert payload["rows"]
    for forbidden in ["loss_value", "monthly_loss_value", "business_score"]:
        assert forbidden not in payload["rows"][0]
