from __future__ import annotations

from pathlib import Path

import pandas as pd

from risk_model_core.manifest import RiskResultManifest
from risk_model_core.page_payload_builder import PagePayloadBuilder
from risk_model_core.repositories import ClickHouseRiskResultRepository, InMemoryRiskResultRepository
from risk_model_core import page_payload_builder as page_payload_module


ROOT = Path(__file__).resolve().parents[1]
MODEL_CORE = ROOT / "risk_model_core"


def make_manifest() -> RiskResultManifest:
    return RiskResultManifest(
        batch_id="dynamic-test-batch",
        report_type="monthly",
        report_month="2025-12",
        report_date="2025-12-31",
        score_cutoff_month="2025-12-31",
        primary_horizon="H6",
        available_horizons=["H3", "H6", "H12"],
        schema_version="test",
        data_backend="in_memory",
        allowed_usage=["backend_api"],
        forbidden_usage=["raw_data_access", "auto_dispatch"],
        customer_facing_probability_service_allowed=False,
        auto_dispatch_allowed=False,
        proof_case_report_allowed=False,
        caveats=[],
        raw={"batch_id": "dynamic-test-batch"},
    )


def make_repository_without_page_payloads() -> InMemoryRiskResultRepository:
    tables = {
        "risk_entities": pd.DataFrame(
            [
                {
                    "risk_entity_id": "recurring-1",
                    "candidate_id": "candidate-1",
                    "tenant_id": "tenant",
                    "manufacturer_code": "M1",
                    "hospital_code": "H1",
                    "hospital_display_name": "Hospital One",
                    "drug_group": "D1",
                    "drug_display_name": "Drug One",
                    "region_display_name": "North",
                    "report_month": "2025-12",
                    "primary_horizon": "H6",
                    "risk_probability_value": 0.72,
                    "churn_probability_H": 0.72,
                    "risk_score_display": 0.91,
                    "risk_score": 0.91,
                    "probability_rank_score": 0.9,
                    "interval_rank_score": 0.8,
                    "frequency_rank_score": 0.7,
                    "business_priority_score_H": 123.0,
                    "value_at_risk_H": 456.0,
                    "overdue_ratio": 1.4,
                    "frequency_decay_baseline": 0.3,
                    "interval_overdue_baseline": 0.4,
                    "recency_only_baseline": 0.5,
                    "candidate_type": "recurring",
                    "display_section": "risk_list",
                    "probability_display_level": "risk_band_only",
                    "risk_level": "high",
                    "risk_color": "red",
                    "review_status": "pending",
                    "final_candidate_status": "priority_review",
                    "auto_dispatch_allowed": False,
                    "is_one_shot": False,
                    "is_observation": False,
                },
                {
                    "risk_entity_id": "oneshot-1",
                    "candidate_id": "candidate-2",
                    "tenant_id": "tenant",
                    "manufacturer_code": "M1",
                    "hospital_code": "H2",
                    "hospital_display_name": "Hospital Two",
                    "drug_group": "D2",
                    "drug_display_name": "Drug Two",
                    "region_display_name": "East",
                    "report_month": "2025-12",
                    "primary_horizon": "H6",
                    "risk_probability_value": None,
                    "risk_score_display": 0.83,
                    "candidate_type": "one_shot",
                    "display_section": "oneshot",
                    "risk_level": "attention",
                    "risk_color": "gray",
                    "review_status": "new_terminal",
                    "final_candidate_status": "one_shot_attention",
                    "auto_dispatch_allowed": False,
                    "is_one_shot": True,
                    "is_observation": False,
                },
                {
                    "risk_entity_id": "observation-1",
                    "candidate_id": "candidate-3",
                    "tenant_id": "tenant",
                    "manufacturer_code": "M2",
                    "hospital_code": "H3",
                    "hospital_display_name": "Hospital Three",
                    "drug_group": "D3",
                    "drug_display_name": "Drug Three",
                    "region_display_name": "West",
                    "report_month": "2025-12",
                    "primary_horizon": "H6",
                    "risk_probability_value": 0.4,
                    "risk_score_display": 0.6,
                    "candidate_type": "observation",
                    "display_section": "watchlist",
                    "risk_level": "observation",
                    "risk_color": "yellow",
                    "review_status": "watching",
                    "final_candidate_status": "observation_only",
                    "auto_dispatch_allowed": False,
                    "is_one_shot": False,
                    "is_observation": True,
                },
            ]
        ),
        "oneshot_terminals": pd.DataFrame(
            [
                {
                    "oneshot_id": "oneshot-1",
                    "tenant_id": "tenant",
                    "manufacturer_code": "M1",
                    "hospital_code": "H2",
                    "hospital_display_name": "Hospital Two",
                    "drug_group": "D2",
                    "drug_display_name": "Drug Two",
                    "region_display_name": "East",
                    "report_month": "2025-12",
                    "candidate_type": "one_shot",
                    "first_purchase_date": "2025-12-10",
                    "first_purchase_amount": 500,
                    "days_since_first_purchase": 21,
                }
            ]
        ),
        "risk_cards": pd.DataFrame(
            [
                {
                    "risk_card_id": "card-1",
                    "risk_entity_id": "recurring-1",
                    "candidate_id": "candidate-1",
                    "card_type": "primary_risk",
                    "card_title": "Purchasing rhythm review",
                    "card_level": "high",
                    "source_module": "runtime",
                    "is_primary": True,
                    "source_detector_name": "purchase_interval_overdue_warning",
                }
            ]
        ),
        "risk_card_evidence": pd.DataFrame(
            [
                {
                    "evidence_id": "evidence-1",
                    "risk_card_id": "card-1",
                    "risk_entity_id": "recurring-1",
                    "candidate_id": "candidate-1",
                    "evidence_type": "interval",
                    "evidence_text": "Purchase interval is longer than the entity history.",
                    "visibility_level": "business_visible",
                }
            ]
        ),
        "risk_entity_timeline": pd.DataFrame(),
        "monthly_reports": pd.DataFrame(
            [
                {
                    "monthly_report_id": "monthly-2025-12",
                    "report_type": "monthly",
                    "report_month": "2025-12",
                    "title": "2025-12 Monthly Risk Review",
                    "summary_text": "Monthly result batch summary.",
                }
            ]
        ),
        "proof_cases": pd.DataFrame(),
    }
    return InMemoryRiskResultRepository(make_manifest(), tables, payloads={})


def test_risk_model_core_source_does_not_access_raw_or_source_databases() -> None:
    forbidden = [
        "risk_algorithm_core.raw_input",
        "sqlalchemy.create_engine",
        "create_engine(",
        "SQL_DATABASE_URL",
        "fact_purchase_event",
        "entity_cutoff_feature_table",
        "raw orders",
    ]
    scanned = "\n".join(path.read_text(encoding="utf-8") for path in MODEL_CORE.glob("*.py"))

    assert not [token for token in forbidden if token in scanned]


def test_clickhouse_repository_documents_result_serving_boundary() -> None:
    doc = ClickHouseRiskResultRepository.__doc__ or ""

    assert "This repository reads result-batch serving tables only." in doc
    assert "It must not read raw business/source tables." in doc


def test_page_payload_builder_constructs_real_payloads_when_json_is_absent() -> None:
    builder = PagePayloadBuilder(make_repository_without_page_payloads())

    workbench = builder.build_frontend_workbench_payload()
    risk_entities = builder.build_frontend_risk_entities_payload()
    detail = builder.build_frontend_risk_entity_detail_payload("recurring-1")
    oneshot = builder.build_frontend_oneshot_payload()
    reports = builder.build_frontend_monthly_reports_payload()

    assert workbench["batch_context"]["result_batch_id"] == "dynamic-test-batch"
    assert workbench["rows"][0]["entity_id"] == "recurring-1"
    assert "fill_policy" not in workbench
    assert workbench["scope_policy"]["model_core_does_not_fill_user_worklists"] is True
    assert workbench["scope_policy"]["backend_may_request_top_n"] is True
    assert risk_entities["entities"][0]["entity_id"] == "recurring-1"
    assert detail["entity"]["entity_id"] == "recurring-1"
    assert detail["horizon_profiles"]["H6"]["detector_results"]
    assert oneshot["items"][0]["oneshot_id"] == "oneshot-1"
    assert "risk_probability" not in oneshot["items"][0]
    assert "repurchase_propensity" not in oneshot["items"][0]
    assert "expected_repurchase_amount" not in oneshot["items"][0]
    assert reports["monthly_reports"][0]["monthly_report_id"] == "monthly-2025-12"


def test_oneshot_summary_uses_vectorized_date_handling(monkeypatch) -> None:
    rows = pd.DataFrame(
        {
            "first_purchase_date": ["2025-12-31", "2025-12-05"] * 50,
        }
    )
    original = page_payload_module._parse_date
    calls = 0

    def tracked_parse_date(value):
        nonlocal calls
        calls += 1
        return original(value)

    monkeypatch.setattr(page_payload_module, "_parse_date", tracked_parse_date)

    summary = page_payload_module._oneshot_summary(rows, "2025-12-31", None)

    assert summary == {"daily_new_terminal_count": 50, "monthly_new_terminal_count": 100}
    assert calls <= 2


def test_dynamic_payloads_preserve_optional_ranking_fields_without_fabrication() -> None:
    builder = PagePayloadBuilder(make_repository_without_page_payloads())

    item = builder.build_frontend_risk_entities_payload()["entities"][0]

    for field in [
        "risk_probability_value",
        "churn_probability_H",
        "risk_score_display",
        "risk_score",
        "probability_rank_score",
        "interval_rank_score",
        "frequency_rank_score",
        "business_priority_score_H",
        "value_at_risk_H",
        "overdue_ratio",
        "frequency_decay_baseline",
        "interval_overdue_baseline",
        "recency_only_baseline",
        "candidate_type",
        "display_section",
        "probability_display_level",
    ]:
        assert field in item


def test_model_core_does_not_fix_top_n_or_fill_user_worklists() -> None:
    builder = PagePayloadBuilder(make_repository_without_page_payloads())

    payload = builder.build_frontend_workbench_payload()

    assert len(payload["rows"]) == 1
    assert payload["meta"]["top_n_requested"] is None
    assert payload["meta"]["model_core_filled_shortage"] is False
    assert payload["meta"]["user_scope_resolved_by_backend"] is True


def test_customer_payloads_do_not_expose_deprecated_frontend_strategy_fields() -> None:
    builder = PagePayloadBuilder(make_repository_without_page_payloads())
    payload = builder.build_frontend_workbench_payload()
    rendered = str(payload)

    for forbidden in [
        "fill_policy",
        "补齐",
        "回补",
        "补充算法",
        "新进终端补齐",
        "规则巡检补充",
        "历史节奏回补",
        "高价值终端覆盖",
        "risk_probability * average_consumption_in_window",
        "RiskResultBatch",
    ]:
        assert forbidden not in rendered
