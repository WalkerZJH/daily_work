from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import pandas as pd

from app.main import app
from risk_model_core.manifest import RiskResultManifest
from risk_model_core.repositories import InMemoryRiskResultRepository


@contextmanager
def override_frontend_result_repository(
    repository: InMemoryRiskResultRepository | None = None,
) -> Iterator[InMemoryRiskResultRepository]:
    from app.api.routes_detector_results import get_detector_result_service
    from app.api.routes_display_lookup import get_display_lookup_service
    from app.api.routes_frontend_pages import get_frontend_page_service
    from app.api.routes_report_context import get_report_context_service
    from app.api.routes_user_top_entities import get_user_top_entity_service
    from app.services.detector_result_service import DetectorResultService
    from app.services.display_lookup_service import DisplayLookupService
    from app.services.frontend_page_service import FrontendPageService
    from app.services.report_context_service import ReportContextService
    from app.services.user_top_entity_service import TopEntityService

    repo = repository or make_frontend_repository()
    app.dependency_overrides[get_user_top_entity_service] = lambda: TopEntityService(repo)
    app.dependency_overrides[get_detector_result_service] = lambda: DetectorResultService(repo)
    app.dependency_overrides[get_display_lookup_service] = lambda: DisplayLookupService(repo)
    app.dependency_overrides[get_frontend_page_service] = lambda: FrontendPageService(repository=repo)
    app.dependency_overrides[get_report_context_service] = lambda: ReportContextService(repo)
    try:
        yield repo
    finally:
        app.dependency_overrides.pop(get_user_top_entity_service, None)
        app.dependency_overrides.pop(get_detector_result_service, None)
        app.dependency_overrides.pop(get_display_lookup_service, None)
        app.dependency_overrides.pop(get_frontend_page_service, None)
        app.dependency_overrides.pop(get_report_context_service, None)


def make_frontend_repository(
    *,
    clues: pd.DataFrame | None = None,
    evidence: pd.DataFrame | None = None,
) -> InMemoryRiskResultRepository:
    return InMemoryRiskResultRepository(
        _manifest(),
        {
            "risk_entities": _risk_entities(),
            "oneshot_terminals": _oneshot_terminals(),
            "entity_display_lookup": _entity_display_lookup(),
            "detector_catalog": _detector_catalog(),
            "daily_detector_runs": _daily_detector_runs(
                clue_count=0 if clues is not None and clues.empty else 2,
                attached_high_risk_count=0 if evidence is not None and evidence.empty else 1,
            ),
            "daily_detector_clues": _daily_detector_clues() if clues is None else clues,
            "high_risk_detector_evidence": _high_risk_detector_evidence() if evidence is None else evidence,
            "monthly_reports": _monthly_reports(),
            "proof_cases": pd.DataFrame(columns=["proof_case_id", "risk_entity_id", "candidate_id", "proof_status"]),
        },
    )


def empty_daily_detector_clues() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "detector_clue_id",
            "detector_run_id",
            "run_date",
            "tenant_id",
            "manufacturer_code",
            "hospital_code",
            "drug_group",
            "detector_id",
            "detector_family",
            "detector_score",
            "detector_level",
            "confidence",
            "hit_flag",
            "root_cause_label",
            "evidence_text",
            "evidence_payload",
            "is_monthly_high_risk_entity",
            "risk_entity_id",
            "monthly_risk_probability",
            "monthly_loss_value",
            "display_rank",
            "caveat",
            "created_at",
        ]
    )


def empty_high_risk_detector_evidence() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "risk_entity_id",
            "detector_run_id",
            "run_date",
            "detector_id",
            "detector_family",
            "detector_score",
            "confidence",
            "root_cause_label",
            "evidence_text",
            "evidence_payload",
            "caveat",
            "created_at",
        ]
    )


def _manifest() -> RiskResultManifest:
    return RiskResultManifest(
        batch_id="frontend-api-test",
        report_type="monthly",
        report_month="2025-12",
        report_date="2025-12-31",
        score_cutoff_month="2025-12-31",
        primary_horizon="H6",
        available_horizons=["H3", "H6", "H12"],
        schema_version="risk_result_batch_monthly_v2",
        data_backend="memory",
        allowed_usage=["backend_api"],
        forbidden_usage=[],
        customer_facing_probability_service_allowed=False,
        auto_dispatch_allowed=False,
        proof_case_report_allowed=False,
        caveats=["detector_score is not probability"],
        raw={
            "batch_id": "frontend-api-test",
            "result_batch_id": "frontend-api-test",
            "report_type": "monthly",
            "report_month": "2025-12",
            "report_date": "2025-12-31",
            "score_as_of_date": "2025-12-31",
            "run_date": "2025-12-30",
            "available_horizons": ["H3", "H6", "H12"],
            "primary_horizon": "H6",
            "detector_config_version": "daily_detector_rules_v1",
            "conditional_fact_mode_ready": True,
            "oneshot_terminals": {
                "table_name": "oneshot_terminals",
                "schema_version": "oneshot_terminal_v1",
                "path": "oneshot_terminals.parquet",
                "row_count": 3,
            },
            "caveats": ["detector_score is not probability"],
        },
    )


def _risk_entities() -> pd.DataFrame:
    return pd.DataFrame(
        [
            _entity("entity_1", "M1", "H6", 0.8, 1000),
            _entity("entity_2", "M1", "H6", 0.7, 500),
            _entity("entity_h3", "M1", "H3", 0.6, 300),
            _entity("entity_3", "M2", "H6", 0.9, 0),
        ]
    )


def _oneshot_terminals() -> pd.DataFrame:
    return pd.DataFrame(
        [
            _oneshot("oneshot_1", "M1", "entity_1", "2025-12-31", 1200, 0),
            _oneshot("oneshot_2", "M1", "entity_2", "2025-12-05", 800, 26),
            _oneshot("oneshot_3", "M2", "entity_3", "2025-11-20", 500, 41),
        ]
    )


def _oneshot(
    oneshot_id: str,
    manufacturer_code: str,
    entity_key: str,
    first_purchase_date: str,
    first_purchase_amount: int,
    days_since_first_purchase: int,
) -> dict[str, object]:
    return {
        "oneshot_id": oneshot_id,
        "tenant_id": "tenant",
        "enterprise_id": "enterprise",
        "manufacturer_code": manufacturer_code,
        "manufacturer_display_name": f"{manufacturer_code} display",
        "hospital_code": f"{entity_key}_hospital",
        "hospital_display_name": f"{entity_key} hospital",
        "drug_group": f"{entity_key}_drug",
        "drug_display_name": f"{entity_key} drug",
        "region_code": "R1",
        "region_display_name": "region",
        "report_month": "2025-12",
        "candidate_type": "one_shot",
        "first_purchase_date": first_purchase_date,
        "first_purchase_amount": first_purchase_amount,
        "days_since_first_purchase": days_since_first_purchase,
        # Legacy physical columns deliberately remain in the fixture. The API
        # contract must never expose or sort by them.
        "repurchase_propensity": 0.99,
        "expected_repurchase_amount": 9999,
        "priority": "high",
        "ranking_basis": "internal attention score",
    }


def _entity(
    entity_id: str,
    manufacturer_code: str,
    horizon: str,
    risk_probability: float,
    average_consumption: int,
) -> dict[str, object]:
    return {
        "risk_entity_id": entity_id,
        "candidate_id": entity_id,
        "tenant_id": "tenant",
        "enterprise_id": "enterprise",
        "manufacturer_code": manufacturer_code,
        "manufacturer_display_name": f"{manufacturer_code} display",
        "hospital_code": f"{entity_id}_hospital",
        "hospital_display_name": f"{entity_id} hospital",
        "drug_code": f"{entity_id}_drug",
        "drug_group": f"{entity_id}_drug",
        "drug_display_name": f"{entity_id} drug",
        "report_month": "2025-12",
        "primary_horizon": horizon,
        "risk_probability_value": risk_probability,
        "average_consumption_in_window": average_consumption,
        "risk_level": "warning",
        "risk_color": "orange",
        "main_reason_summary": "规则证据命中",
        "region_display_name": "region",
        "review_status": "recurring",
        "final_candidate_status": "recurring",
        "review_priority": "P1",
        "risk_card_count": 1,
        "is_high_risk": True,
        "is_observation": False,
        "is_one_shot": False,
        "auto_dispatch_allowed": False,
    }


def _entity_display_lookup() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "tenant_id": "tenant",
                "report_month": "2025-12",
                "manufacturer_code": "M1",
                "manufacturer_display_name": "Manufacturer One",
                "hospital_code": "entity_1_hospital",
                "hospital_display_name": "Hospital One",
                "drug_code": "entity_1_drug",
                "drug_group": "entity_1_drug",
                "drug_display_name": "Drug One",
                "region_code": "R1",
                "region_display_name": "Region One",
                "display_name_quality": "result_batch",
            },
            {
                "tenant_id": "tenant",
                "report_month": "2025-12",
                "manufacturer_code": "M1",
                "manufacturer_display_name": "Manufacturer One",
                "hospital_code": "clue_high_hospital",
                "hospital_display_name": "High Clue Hospital",
                "drug_code": "clue_high_drug",
                "drug_group": "clue_high_drug",
                "drug_display_name": "High Clue Drug",
                "region_code": "R1",
                "region_display_name": "Region One",
                "display_name_quality": "result_batch",
            },
            {
                "tenant_id": "tenant",
                "report_month": "2025-12",
                "manufacturer_code": "M1",
                "manufacturer_display_name": "Manufacturer One",
                "hospital_code": "clue_rule_only_hospital",
                "hospital_display_name": "Rule Only Hospital",
                "drug_code": "clue_rule_only_drug",
                "drug_group": "clue_rule_only_drug",
                "drug_display_name": "Rule Only Drug",
                "region_code": "R1",
                "region_display_name": "Region One",
                "display_name_quality": "result_batch",
            }
        ]
    )


def _detector_catalog() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "detector_id": "purchase_interval_ipi",
                "detector_family": "interval",
                "detector_name": "Purchase interval IPI",
                "status": "implemented",
                "enabled_by_default": True,
                "method": "rule_result_batch",
                "required_fields": "[]",
                "optional_fields": "[]",
                "output_schema_version": "daily_detector_clue_v1",
                "caveat": "detector_score is not probability",
            }
        ]
    )


def _daily_detector_runs(
    *,
    clue_count: int,
    attached_high_risk_count: int,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "detector_run_id": "run_2025_12_31",
                "run_date": "2025-12-31",
                "report_month": "2025-12",
                "source_result_batch_id": "frontend-api-test",
                "detector_config_version": "daily_detector_rules_v1",
                "enabled_detectors": "purchase_interval_ipi",
                "scanned_entity_count": 3,
                "clue_count": clue_count,
                "attached_high_risk_count": attached_high_risk_count,
                "created_at": "2025-12-31T09:00:00+08:00",
            }
        ]
    )


def _daily_detector_clues() -> pd.DataFrame:
    return pd.DataFrame(
        [
            _clue("clue_high", "M1", "entity_1", True, 0.82, 800),
            _clue("clue_rule_only", "M1", "", False, 0.76, None),
        ]
    )


def _clue(
    clue_id: str,
    manufacturer_code: str,
    risk_entity_id: str,
    monthly_high: bool,
    score: float,
    monthly_loss_value: int | None,
) -> dict[str, object]:
    return {
        "detector_clue_id": clue_id,
        "detector_run_id": "run_2025_12_31",
        "run_date": "2025-12-31",
        "tenant_id": "tenant",
        "manufacturer_code": manufacturer_code,
        "hospital_code": f"{clue_id}_hospital",
        "drug_group": f"{clue_id}_drug",
        "drug_code": f"{clue_id}_drug",
        "detector_id": "purchase_interval_ipi",
        "detector_family": "interval",
        "detector_score": score,
        "detector_level": "warning",
        "confidence": 0.7,
        "hit_flag": True,
        "root_cause_label": "规则证据命中",
        "evidence_text": "建议复核采购节奏",
        "evidence_payload": "{}",
        "is_monthly_high_risk_entity": monthly_high,
        "risk_entity_id": risk_entity_id,
        "monthly_risk_probability": 0.8 if monthly_high else pd.NA,
        "monthly_loss_value": monthly_loss_value if monthly_high else pd.NA,
        "display_rank": 1 if monthly_high else 2,
        "caveat": "detector_score is rule inspection score, not probability",
        "created_at": "2025-12-31T09:05:00+08:00",
    }


def _high_risk_detector_evidence() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "risk_entity_id": "entity_1",
                "detector_run_id": "run_2025_12_31",
                "run_date": "2025-12-31",
                "detector_id": "purchase_interval_ipi",
                "detector_family": "interval",
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


def _monthly_reports() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "monthly_report_id": "monthly_2025_12",
                "report_type": "monthly",
                "report_month": "2025-12",
                "title": "monthly review",
                "summary_text": "bounded worklist",
            }
        ]
    )
