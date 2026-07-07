from __future__ import annotations

from pathlib import Path
import json


INTERNAL_ROOT = Path("data/entity_complete_v2_coverage_expansion/10_mvc_model_package")
FRONTEND_ROOT = Path("data/entity_complete_v2_coverage_expansion/10_frontend_worklist_model_package")
FRONTEND_BATCH = FRONTEND_ROOT / "risk_result_batches/batch_id=2025-12-frontend-worklist-v1"


def test_internal_full_dump_is_not_frontend_default() -> None:
    marker = json.loads((INTERNAL_ROOT / "internal_full_status_manifest.json").read_text(encoding="utf-8"))
    frontend_manifest = json.loads((FRONTEND_BATCH / "manifest.json").read_text(encoding="utf-8"))

    assert marker["visibility"] == "internal_only"
    assert marker["not_for_frontend_default"] is True
    assert marker["frontend_default_allowed"] is False
    assert frontend_manifest["package_scope"] == "frontend_worklist"
    assert frontend_manifest["is_bounded"] is True
    assert frontend_manifest["full_status_visibility"] == "internal_only"


def test_scope_reports_exist() -> None:
    report_root = Path("reports/entity_complete_v2_coverage_expansion")

    assert (report_root / "13_mvc_model_extraction/mvc_package_scope_audit.md").exists()
    assert (report_root / "14_frontend_worklist_model_package/frontend_worklist_scope_summary.md").exists()
    assert (report_root / "14_frontend_worklist_model_package/frontend_vs_internal_package_comparison.csv").exists()

