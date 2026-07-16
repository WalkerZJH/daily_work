from __future__ import annotations

from pathlib import Path
import json

import pandas as pd

from risk_algorithm_core.daily_detector_runner import build_daily_detector_tables
from risk_result_contracts import write_production_parquet


def build_detector_fixture(include_non_high_risk_scan: bool = False) -> dict:
    risk_entities = pd.DataFrame(
        [
            {
                "risk_entity_id": "entity_high",
                "candidate_id": "entity_high|H6",
                "tenant_id": "tenant_a",
                "manufacturer_code": "m1",
                "hospital_code": "h1",
                "drug_group": "d1",
                "report_month": "2026-07",
                "risk_level": "orange",
                "review_status": "priority_review",
                "final_candidate_status": "priority_review",
                "auto_dispatch_allowed": False,
                "is_high_risk": True,
                "risk_probability_value": 0.77,
                "value_at_risk_H": 1200.0,
            }
        ]
    )
    scan_features = pd.DataFrame(
        [
            {
                "risk_entity_id": "entity_high",
                "candidate_id": "entity_high|H6",
                "entity_id": "entity_high",
                "tenant_id": "tenant_a",
                "manufacturer_code": "m1",
                "hospital_code": "h1",
                "drug_group": "d1",
                "report_month": "2026-07",
                "days_since_last_purchase": 80,
                "historical_interval_median": 30,
                "historical_interval_mad": 10,
                "purchase_count_total": 12,
                "quantity_ratio": 0.35,
                "frequency_ratio": 0.4,
                "purchase_frequency_baseline": 2.5,
                "churn_probability_H": 0.77,
                "value_at_risk_H": 1200.0,
            }
        ]
    )
    if include_non_high_risk_scan:
        scan_features = pd.concat(
            [
                scan_features,
                pd.DataFrame(
                    [
                        {
                            "risk_entity_id": "entity_non_high",
                            "candidate_id": "entity_non_high|H6",
                            "entity_id": "entity_non_high",
                            "tenant_id": "tenant_a",
                            "manufacturer_code": "m1",
                            "hospital_code": "h2",
                            "drug_group": "d2",
                            "report_month": "2026-07",
                            "days_since_last_purchase": 95,
                            "historical_interval_median": 35,
                            "historical_interval_mad": 8,
                            "purchase_count_total": 9,
                            "quantity_ratio": 0.7,
                            "frequency_ratio": 0.45,
                            "purchase_frequency_baseline": 2.0,
                            "churn_probability_H": 0.25,
                            "value_at_risk_H": 200.0,
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
    return {
        "risk_entities": risk_entities,
        "scan_features": scan_features,
        "report_month": "2026-07",
        "run_date": "2026-07-08",
        "source_raw_batch_id": "raw_fixture",
        "source_result_batch_id": "batch_fixture",
    }


def write_minimal_detector_batch(tmp_path: Path) -> Path:
    tables = build_daily_detector_tables(**build_detector_fixture())
    batch = tmp_path / "batch"
    batch.mkdir()
    risk_entities = build_detector_fixture()["risk_entities"]
    standard_empty = {
        "risk_cards": pd.DataFrame(
            [
                {
                    "risk_card_id": "card_entity_high",
                    "risk_entity_id": "entity_high",
                    "candidate_id": "entity_high|H6",
                    "card_type": "primary_risk",
                    "card_title": "Monthly risk review",
                    "card_level": "orange",
                    "source_module": "risk_algorithm_core",
                    "is_primary": True,
                }
            ]
        ),
        "risk_card_evidence": pd.DataFrame(
            [
                {
                    "evidence_id": "ev_card_entity_high",
                    "risk_card_id": "card_entity_high",
                    "risk_entity_id": "entity_high",
                    "candidate_id": "entity_high|H6",
                    "evidence_type": "selection_reason",
                    "evidence_text": "Selected for monthly purchasing risk review.",
                    "visibility_level": "business_visible",
                }
            ]
        ),
        "risk_entity_timeline": pd.DataFrame(),
        "hospital_aggregates": pd.DataFrame(),
        "drug_aggregates": pd.DataFrame(),
        "monthly_reports": pd.DataFrame(
            [
                {
                    "monthly_report_id": "monthly_2026-07",
                    "report_type": "monthly",
                    "report_month": "2026-07",
                    "title": "2026-07 monthly risk clue review",
                    "summary_text": "fixture",
                }
            ]
        ),
        "proof_cases": pd.DataFrame(),
        "work_order_reserved": pd.DataFrame(),
        "entity_display_lookup": pd.DataFrame(
            [
                {
                    "tenant_id": "tenant_a",
                    "report_month": "2026-07",
                    "manufacturer_code": "m1",
                    "manufacturer_display_name": "m1",
                    "hospital_code": "h1",
                    "hospital_display_name": "h1",
                    "drug_code": "d1",
                    "drug_group": "d1",
                    "drug_display_name": "d1",
                    "product_line_code": "",
                    "product_line_name": "",
                    "region_code": "",
                    "region_display_name": "",
                    "display_key": "tenant_a|2026-07|m1|h1|d1",
                    "display_name_source": "fixture",
                    "display_name_quality": "code_fallback",
                    "source_raw_batch_id": "raw_fixture",
                    "updated_at": "2026-07-08T00:00:00+00:00",
                }
            ]
        ),
    }
    all_tables = {"risk_entities": risk_entities, **standard_empty, **tables}
    for name, frame in all_tables.items():
        write_production_parquet(frame, batch / f"{name}.parquet")
    manifest = {
        "batch_id": "batch_fixture",
        "report_type": "monthly",
        "report_month": "2026-07",
        "report_date": "2026-07-08",
        "score_cutoff_month": "2026-07",
        "primary_horizon": "H6",
        "available_horizons": ["H6"],
        "schema_version": "risk_result_batch_monthly_v1",
        "data_backend": "parquet",
        "allowed_usage": ["internal_diagnostic"],
        "forbidden_usage": ["auto_dispatch"],
        "customer_facing_probability_service_allowed": False,
        "auto_dispatch_allowed": False,
        "proof_case_report_allowed": False,
        "detector_tables": {
            "detector_catalog": "detector_catalog.parquet",
            "detector_config_profiles": "detector_config_profiles.parquet",
            "detector_run_config_snapshot": "detector_run_config_snapshot.parquet",
            "daily_detector_runs": "daily_detector_runs.parquet",
            "daily_detector_results": "daily_detector_results.parquet",
            "daily_detector_clues": "daily_detector_clues.parquet",
            "high_risk_detector_evidence": "high_risk_detector_evidence.parquet",
        },
        "detector_config_version": "daily_detector_rules_v1",
        "detector_score_probability_interpretation": "detector_score_is_not_probability",
        "detector_default_scope": "monthly_high_risk_entities",
        "caveats": ["fixture"],
    }
    (batch / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return batch
