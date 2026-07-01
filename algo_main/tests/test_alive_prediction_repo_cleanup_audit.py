from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pandas as pd


def test_repo_cleanup_audit_dry_run_generates_reports_without_deleting_files():
    root = Path(__file__).resolve().parents[1]
    sentinel = root / "scripts/run_alive_prediction_small_model_experiments.py"
    assert sentinel.is_file()
    before = sentinel.read_bytes()

    result = subprocess.run(
        [sys.executable, "scripts/audit_alive_prediction_repo_cleanup.py", "--dry-run"],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    )

    output_dir = root / "reports/repo_cleanup_alive_prediction"
    assert str(output_dir / "repo_cleanup_summary.md") in result.stdout
    for rel in [
        "repo_cleanup_summary.md",
        "script_inventory.csv",
        "report_inventory.csv",
        "cache_artifact_inventory.csv",
        "duplicate_code_candidates.csv",
        "obsolete_doc_candidates.csv",
        "obsolete_script_candidates.csv",
        "safe_delete_candidates.txt",
        "archive_candidates.txt",
        "cleanup_apply_plan.md",
    ]:
        assert (output_dir / rel).is_file(), rel

    assert sentinel.is_file()
    assert sentinel.read_bytes() == before

    scripts = pd.read_csv(output_dir / "script_inventory.csv")
    assert "scripts/run_alive_prediction_small_model_experiments.py" in scripts["path"].tolist()
    assert "deprecation_candidate" in scripts.columns

