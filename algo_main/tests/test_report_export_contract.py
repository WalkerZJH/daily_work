from __future__ import annotations

from pathlib import Path
import json

import pandas as pd


PACKAGE_ROOT = Path("data/entity_complete_v2_coverage_expansion/10_frontend_worklist_model_package")
BATCH_DIR = PACKAGE_ROOT / "risk_result_batches/batch_id=2025-12-frontend-worklist-v1"


def test_result_batch_manifest_and_tables_exist() -> None:
    manifest = json.loads((BATCH_DIR / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["report_type"] == "monthly"
    assert manifest["package_scope"] == "frontend_worklist"
    assert manifest["is_bounded"] is True
    assert manifest["customer_facing_probability_service_allowed"] is False
    assert manifest["auto_dispatch_allowed"] is False
    assert manifest["proof_case_report_allowed"] is False
    for name in ["risk_entities.parquet", "risk_cards.parquet", "risk_card_evidence.parquet", "daily_reports.parquet"]:
        assert (BATCH_DIR / name).exists()


def test_daily_reports_are_monthly() -> None:
    reports = pd.read_parquet(BATCH_DIR / "daily_reports.parquet")

    assert len(reports) == 1
    assert reports["report_type"].eq("monthly").all()


def test_export_manifest_exists_without_formal_pdf() -> None:
    manifest = json.loads((PACKAGE_ROOT / "export_manifest.json").read_text(encoding="utf-8"))

    assert "future_pdf" in manifest["export_formats_supported"]
    assert manifest["export_status"] == "structure_ready_no_pdf_generated"
    assert not list(PACKAGE_ROOT.rglob("*.pdf"))
