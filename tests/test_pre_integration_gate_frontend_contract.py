import json
import subprocess
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "algo_main" / "reports" / "entity_complete_v2_coverage_expansion" / "20_pre_frontend_backend_integration_gate"
DATA_DIR = ROOT / "algo_main" / "data" / "entity_complete_v2_coverage_expansion" / "14_pre_frontend_backend_integration_gate"


def test_frontend_and_backend_contract_matrices_exist_with_wip_flags() -> None:
    frontend = pd.read_csv(REPORT_DIR / "frontend_page_payload_matrix.csv")
    backend = pd.read_csv(REPORT_DIR / "backend_api_contract_matrix.csv")
    assert "frontend_wip_present" in frontend.columns
    assert "project_wip_present" in backend.columns
    assert frontend["frontend_wip_present"].astype(bool).any()
    assert backend["project_wip_present"].astype(bool).any()
    assert "working tree" in (REPORT_DIR / "frontend_contract_readiness_review.md").read_text(encoding="utf-8")
    assert "working tree" in (REPORT_DIR / "backend_api_readiness_review.md").read_text(encoding="utf-8")


def test_project_frontend_wip_is_recorded_and_unchanged() -> None:
    start = json.loads((DATA_DIR / "project_frontend_wip_start_snapshot.json").read_text(encoding="utf-8"))
    end = json.loads((DATA_DIR / "project_frontend_wip_end_snapshot.json").read_text(encoding="utf-8"))
    for key in ["project_frontend_status", "project_frontend_diff_name_status", "project_frontend_untracked"]:
        assert start[key] == end[key]
    assert start["project_wip_present"] is True
    assert start["frontend_wip_present"] is True


def test_staged_changes_do_not_include_project_or_frontend() -> None:
    result = subprocess.run(["git", "diff", "--cached", "--name-status"], cwd=ROOT, text=True, capture_output=True, check=True)
    staged = result.stdout
    assert "project/" not in staged
    assert "front_end/" not in staged
