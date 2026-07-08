from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "algo_main" / "reports" / "entity_complete_v2_coverage_expansion" / "20_pre_frontend_backend_integration_gate"
DATA_DIR = ROOT / "algo_main" / "data" / "entity_complete_v2_coverage_expansion" / "14_pre_frontend_backend_integration_gate"
FORMAL_REPORT_DIR = ROOT / "algo_main" / "reports" / "entity_complete_v2_coverage_expansion" / "19_formal_algorithm_core_raw_to_batch"


def test_source_of_truth_gate_reports_exist() -> None:
    assert (FORMAL_REPORT_DIR / "source_of_truth_flow_map.md").exists()
    assert (REPORT_DIR / "source_of_truth_readiness_review.md").exists()
    assert (REPORT_DIR / "preexisting_project_frontend_wip_snapshot.md").exists()
    assert (REPORT_DIR / "pre_frontend_backend_integration_gate.md").exists()


def test_source_of_truth_gate_is_conditional_not_blocked() -> None:
    gate_text = (REPORT_DIR / "pre_frontend_backend_integration_gate.md").read_text(encoding="utf-8")
    assert "source_of_truth_ready" in gate_text
    assert "CONDITIONAL_READY" in gate_text
    assert "formal_frontend_backend_integration_ready: CONDITIONAL_READY" in gate_text
    assert "integration_start_allowed: YES_FOR_CORE_RISK_PAGES" in gate_text


def test_raw_to_feature_parity_pass_or_conditional_pass() -> None:
    parity = pd.read_csv(FORMAL_REPORT_DIR / "raw_to_feature_parity.csv")
    assert not parity.empty
    assert set(parity["status"].astype(str).str.lower()).issubset({"pass", "conditional_pass"})
