"""Validate generated frontend page payload JSON against project schemas."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
VERSION = "entity_complete_v2_coverage_expansion"
DEFAULT_BATCH_DIR = (
    ROOT
    / "algo_main"
    / "data"
    / VERSION
    / "13_formal_algorithm_core_raw_to_batch"
    / "formal_result_batches"
    / "report_month=2025-12"
    / "batch_id=2025-12-monthly-risk-algorithm-formal-v2-raw"
)
REPORT_DIR = ROOT / "algo_main" / "reports" / VERSION / "22_frontend_payload_delivery"
SCHEMA_PATH = ROOT / "project" / "app" / "schemas" / "frontend_pages.py"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-dir", default=str(DEFAULT_BATCH_DIR))
    args = parser.parse_args()
    batch_dir = Path(args.batch_dir).resolve()
    payload_dir = batch_dir / "page_payloads"
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    schema = load_schema_module()
    rows = []
    rows.extend(validate_file(payload_dir / "frontend_workbench_payload.json", schema.WorkbenchPayload))
    rows.extend(validate_file(payload_dir / "frontend_risk_entities_payload.json", schema.RiskEntitiesPayload))
    rows.extend(validate_file(payload_dir / "frontend_oneshot_payload.json", schema.OneshotPayload))
    rows.extend(validate_file(payload_dir / "frontend_monthly_reports_payload.json", schema.MonthlyReportsPayload))
    rows.extend(validate_file(payload_dir / "frontend_proof_cases_payload.json", schema.ProofCasesPayload))
    manifest_path = payload_dir / "frontend_payload_manifest.json"
    if path_exists(manifest_path):
        with open(long_path(manifest_path), encoding="utf-8") as fh:
            manifest = json.load(fh)
        for item in manifest.get("detail_payloads", []):
            rows.extend(validate_file(payload_dir / item["detail_payload_file"], schema.RiskEntityDetailPayload))
    df = pd.DataFrame(rows)
    df.to_csv(REPORT_DIR / "frontend_payload_schema_validation.csv", index=False, encoding="utf-8")
    write_report(df)
    if not df.empty and not df["validation_status"].eq("pass").all():
        raise SystemExit("Frontend payload schema validation failed")


def validate_file(path: Path, schema_class: type) -> list[dict[str, Any]]:
    try:
        with open(long_path(path), encoding="utf-8") as fh:
            payload = json.load(fh)
        schema_class.model_validate(payload)
        return [
            {
                "payload_file": path.name,
                "schema_class": schema_class.__name__,
                "validation_status": "pass",
                "error_count": 0,
                "error_summary": "",
            }
        ]
    except Exception as exc:
        return [
            {
                "payload_file": path.name,
                "schema_class": schema_class.__name__,
                "validation_status": "fail",
                "error_count": 1,
                "error_summary": str(exc).replace("\n", " ")[:500],
            }
        ]


def load_schema_module():
    spec = importlib.util.spec_from_file_location("frontend_pages_schema", SCHEMA_PATH)
    if not spec or not spec.loader:
        raise RuntimeError(f"Cannot load schema: {SCHEMA_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    for obj in vars(module).values():
        if isinstance(obj, type) and getattr(obj, "__module__", "") == module.__name__ and hasattr(obj, "model_rebuild"):
            obj.model_rebuild(_types_namespace=vars(module))
    return module


def write_report(df: pd.DataFrame) -> None:
    passed = bool(not df.empty and df["validation_status"].eq("pass").all())
    text = "# Frontend Payload Schema Validation\n\n"
    text += f"- schema_source: `{SCHEMA_PATH}`\n"
    text += f"- payload_count: {len(df)}\n"
    text += f"- validation_passed: {passed}\n\n"
    text += df.to_markdown(index=False) + "\n"
    (REPORT_DIR / "frontend_payload_schema_validation.md").write_text(text, encoding="utf-8")


def long_path(path: Path) -> str:
    resolved = str(path.resolve())
    if os.name == "nt" and not resolved.startswith("\\\\?\\"):
        return "\\\\?\\" + resolved
    return resolved


def path_exists(path: Path) -> bool:
    return os.path.exists(long_path(path))


if __name__ == "__main__":
    main()
