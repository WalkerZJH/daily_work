import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BATCH_DIR = (
    ROOT
    / "algo_main"
    / "data"
    / "entity_complete_v2_coverage_expansion"
    / "13_formal_algorithm_core_raw_to_batch"
    / "formal_result_batches"
    / "report_month=2025-12"
    / "batch_id=2025-12-monthly-risk-algorithm-formal-v2-raw"
)
DATA_DIR = ROOT / "algo_main" / "data" / "entity_complete_v2_coverage_expansion" / "14_pre_frontend_backend_integration_gate"


def test_result_batch_validates_against_contracts() -> None:
    from risk_model_core.validation import validate_batch
    from risk_result_contracts import validate_result_batch

    validate_result_batch(BATCH_DIR)
    validate_batch(BATCH_DIR)


def test_result_batch_manifest_is_monthly_and_safe() -> None:
    manifest = json.loads((BATCH_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["report_type"] == "monthly"
    assert manifest["report_month"] == "2025-12"
    assert manifest["model_artifact_id"] == "xgboost_small_without_choice_set_20260707043129"
    assert manifest["feature_group"] == "all_safe_features_without_choice_set"
    assert manifest["auto_dispatch_allowed"] is False
    assert manifest["customer_facing_probability_service_allowed"] is False
    assert manifest["proof_case_report_allowed"] is False


def test_result_batch_required_tables_are_present_and_nonempty_where_expected() -> None:
    counts = pd.read_csv(DATA_DIR / "result_batch_table_counts.csv")
    assert set(counts["table"]) >= {
        "risk_entities",
        "risk_cards",
        "risk_card_evidence",
        "monthly_reports",
        "proof_cases",
        "work_order_reserved",
    }
    nonempty = counts.set_index("table")["rows"]
    assert nonempty["risk_entities"] > 0
    assert nonempty["risk_cards"] > 0
    assert nonempty["risk_card_evidence"] > 0
    assert nonempty["monthly_reports"] > 0
