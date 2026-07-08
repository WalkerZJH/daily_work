import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "algo_main" / "data" / "entity_complete_v2_coverage_expansion" / "14_pre_frontend_backend_integration_gate"
REPORT_DIR = ROOT / "algo_main" / "reports" / "entity_complete_v2_coverage_expansion" / "20_pre_frontend_backend_integration_gate"
FORMAL_REPORT_DIR = ROOT / "algo_main" / "reports" / "entity_complete_v2_coverage_expansion" / "19_formal_algorithm_core_raw_to_batch"


def test_algorithm_core_smoke_run_uses_artifact_mode() -> None:
    smoke = json.loads((DATA_DIR / "algorithm_core_smoke_run_summary.json").read_text(encoding="utf-8"))
    assert smoke["returncode"] == 0
    assert smoke["summary"]["model_artifact_id"] == "xgboost_small_without_choice_set_20260707043129"
    assert smoke["summary"]["dry_run_rule_baseline"] is False
    assert smoke["summary"]["feature_rows"] == 106647
    assert smoke["summary"]["selected_candidate_rows"] == 1291


def test_algorithm_core_runtime_review_records_required_parity() -> None:
    review = (REPORT_DIR / "algorithm_core_runtime_review.md").read_text(encoding="utf-8")
    assert "raw-to-feature parity: PASS" in review
    assert "score parity: PASS" in review
    assert "result-batch parity: CONDITIONAL_PASS" in review
    assert "formal algorithm batch vs frontend projection" in review


def test_result_batch_parity_has_no_core_blocker() -> None:
    parity = pd.read_csv(FORMAL_REPORT_DIR / "full_result_batch_parity.csv")
    assert not parity["status"].astype(str).str.lower().eq("blocked").any()
    warning_reasons = "\n".join(parity["blocker_reason"].fillna("").astype(str))
    assert "frontend projection" in warning_reasons
