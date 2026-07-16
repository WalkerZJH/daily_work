from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import pandas as pd

from app.main import app
from risk_model_core.manifest import RiskResultManifest
from risk_model_core.repositories import InMemoryRiskResultRepository


@contextmanager
def override_detector_service(
    repository: InMemoryRiskResultRepository | None = None,
) -> Iterator[None]:
    from app.api.routes_detector_results import get_detector_result_service
    from app.services.detector_result_service import DetectorResultService

    repo = repository or make_detector_repository()
    app.dependency_overrides[get_detector_result_service] = lambda: DetectorResultService(repo)
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_detector_result_service, None)


def make_detector_repository() -> InMemoryRiskResultRepository:
    return InMemoryRiskResultRepository(
        _manifest(),
        {
            "risk_entities": _risk_entities(),
            "detector_catalog": _detector_catalog(),
            "daily_detector_runs": _daily_detector_runs(),
            "daily_detector_results": _daily_detector_results(),
            "daily_detector_clues": _daily_detector_clues(),
            "high_risk_detector_evidence": _high_risk_detector_evidence(),
        },
    )


def _manifest() -> RiskResultManifest:
    return RiskResultManifest(
        batch_id="detector-result-test",
        report_type="monthly",
        report_month="2025-12",
        report_date="2025-12-31",
        score_cutoff_month="2025-12-31",
        primary_horizon="H6",
        available_horizons=["H6"],
        schema_version="test",
        data_backend="memory",
        allowed_usage=["backend_api"],
        forbidden_usage=[],
        customer_facing_probability_service_allowed=False,
        auto_dispatch_allowed=False,
        proof_case_report_allowed=False,
        caveats=[],
        raw={},
    )


def _detector_catalog() -> pd.DataFrame:
    rows = [
        ("purchase_interval_ipi", "purchase_interval", "implemented", True),
        ("purchase_quantity_trend", "purchase_quantity", "implemented", True),
        ("purchase_frequency_drop", "purchase_frequency", "implemented", True),
        ("sku_shrink", "sku_wallet", "interface_only", False),
        ("fulfillment_gap", "fulfillment", "experimental", False),
        ("price_competition", "price", "reserved", False),
        ("peer_contrast", "peer", "reserved", False),
    ]
    return pd.DataFrame(
        [
            {
                "detector_id": detector_id,
                "detector_family": family,
                "detector_name": detector_id.replace("_", " ").title(),
                "status": status,
                "enabled_by_default": enabled,
                "method": "rule_result_batch",
                "required_fields": "[]",
                "optional_fields": "[]",
                "output_schema_version": "daily_detector_clue_v1",
                "caveat": "reserved detector disabled" if status == "reserved" else "",
            }
            for detector_id, family, status, enabled in rows
        ]
    )


def _daily_detector_runs() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "detector_run_id": "run_2025_12_31",
                "run_date": "2025-12-31",
                "report_month": "2025-12",
                "source_raw_batch_id": "raw_2025_12_31",
                "source_result_batch_id": "detector-result-test",
                "detector_config_version": "daily_detector_rules_v1",
                "enabled_detectors": "purchase_interval_ipi,purchase_quantity_trend,purchase_frequency_drop",
                "scanned_entity_count": 3,
                "clue_count": 2,
                "attached_high_risk_count": 1,
                "created_at": "2025-12-31T09:00:00+08:00",
            }
        ]
    )


def _daily_detector_clues() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "detector_clue_id": "clue_high",
                "detector_run_id": "run_2025_12_31",
                "run_date": "2025-12-31",
                "tenant_id": "tenant",
                "manufacturer_code": "m1",
                "hospital_code": "h1",
                "drug_group": "d1",
                "detector_id": "purchase_interval_ipi",
                "detector_family": "purchase_interval",
                "detector_score": 0.82,
                "detector_level": "warning",
                "confidence": 0.7,
                "hit_flag": True,
                "root_cause_label": "规则证据命中",
                "evidence_text": "建议复核采购节奏",
                "evidence_payload": "{}",
                "is_monthly_high_risk_entity": True,
                "risk_entity_id": "entity_high",
                "monthly_risk_probability": 0.91,
                "monthly_loss_value": 910,
                "display_rank": 1,
                "caveat": "detector_score is rule inspection score, not probability",
                "created_at": "2025-12-31T09:05:00+08:00",
            },
            {
                "detector_clue_id": "clue_non_high",
                "detector_run_id": "run_2025_12_31",
                "run_date": "2025-12-31",
                "tenant_id": "tenant",
                "manufacturer_code": "m1",
                "hospital_code": "h2",
                "drug_group": "d2",
                "detector_id": "purchase_frequency_drop",
                "detector_family": "purchase_frequency",
                "detector_score": 0.76,
                "detector_level": "watch",
                "confidence": 0.6,
                "hit_flag": True,
                "root_cause_label": "规则证据命中",
                "evidence_text": "建议复核采购节奏",
                "evidence_payload": "{}",
                "is_monthly_high_risk_entity": False,
                "risk_entity_id": "",
                "monthly_risk_probability": pd.NA,
                "monthly_loss_value": pd.NA,
                "display_rank": 2,
                "caveat": "daily detector clue, not model high risk",
                "created_at": "2025-12-31T09:06:00+08:00",
            },
        ]
    )


def _daily_detector_results() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "detector_result_id": "clue_high", "run_id": "run_2025_12_31",
                "source_raw_batch_id": "clean-input", "observation_date": "2025-12-31",
                "manufacturer_code": "m1", "hospital_code": "h1", "drug_code": "d1",
                "purchase_unit": "盒", "detector_family": "purchase_interval",
                "detector_id": "purchase_interval_ipi", "detector_name": "Purchase interval IPI",
                "detector_version": "purchase_interval_ipi_v1", "config_id": "cfg-1",
                "config_hash": "a" * 64, "hit_flag": True, "severity": "high", "confidence": 0.8,
                "eligibility_status": "applicable", "inapplicable_reason": pd.NA,
                "demand_shape_label": "smooth", "evidence_window_start": "2025-01-01",
                "evidence_window_end": "2025-12-31", "current_value": 60.0,
                "baseline_value": 20.0, "comparison_value": 4.0, "threshold_value": 1.5,
                "threshold_operator": ">=", "evidence_payload": "{}",
                "evidence_text": "采购节奏异常", "hit_reason": "采购节奏异常",
                "caveat": "fact only", "created_at": "2025-12-31T09:05:00+08:00",
            },
            {
                "detector_result_id": "clue_non_high", "run_id": "run_2025_12_31",
                "source_raw_batch_id": "clean-input", "observation_date": "2025-12-31",
                "manufacturer_code": "m1", "hospital_code": "h2", "drug_code": "d2",
                "purchase_unit": "盒", "detector_family": "purchase_frequency",
                "detector_id": "purchase_frequency_drop", "detector_name": "Purchase frequency drop",
                "detector_version": "purchase_frequency_drop_v1", "config_id": "cfg-2",
                "config_hash": "b" * 64, "hit_flag": True, "severity": "medium", "confidence": 0.6,
                "eligibility_status": "applicable", "inapplicable_reason": pd.NA,
                "demand_shape_label": "intermittent", "evidence_window_start": "2025-01-01",
                "evidence_window_end": "2025-12-31", "current_value": 1.0,
                "baseline_value": 4.0, "comparison_value": 0.25, "threshold_value": 0.6,
                "threshold_operator": "<=", "evidence_payload": "{}",
                "evidence_text": "采购频次下降", "hit_reason": "采购频次低于历史基准",
                "caveat": "fact only", "created_at": "2025-12-31T09:06:00+08:00",
            },
        ]
    )


def _high_risk_detector_evidence() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "risk_entity_id": "entity_high",
                "detector_run_id": "run_2025_12_31",
                "run_date": "2025-12-31",
                "detector_id": "purchase_interval_ipi",
                "detector_family": "purchase_interval",
                "detector_score": 0.82,
                "confidence": 0.7,
                "root_cause_label": "规则证据命中",
                "evidence_text": "建议复核采购节奏",
                "evidence_payload": "{}",
                "caveat": "detector_score is rule inspection score, not probability",
                "created_at": "2025-12-31T09:05:00+08:00",
            }
        ]
    )


def _risk_entities() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "risk_entity_id": "entity_high",
                "candidate_id": "candidate_high",
                "tenant_id": "tenant",
                "manufacturer_code": "m1",
                "hospital_code": "h1",
                "drug_group": "d1",
                "report_month": "2025-12",
                "primary_horizon": "H6",
                "risk_probability_value": 0.91,
                "monthly_loss_value": 910,
                "average_consumption_in_window": 1000,
                "risk_level": "orange",
                "review_status": "recurring",
                "final_candidate_status": "recurring",
                "auto_dispatch_allowed": False,
                "is_high_risk": True,
                "is_observation": False,
                "is_one_shot": False,
            }
        ]
    )
