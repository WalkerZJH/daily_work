from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from risk_result_contracts import validate_result_batch, write_production_parquet

BATCH_ROOT = REPO / "data" / "project_result_batches"
BASELINE_PATH = REPO / "reports" / "current_production_state_baseline.json"
REPORT_JSON = REPO / "reports" / "parquet_only_migration_report.json"
REPORT_MD = REPO / "reports" / "parquet_only_migration_report.md"

FORMAL_TABLES = {
    "risk_entities",
    "risk_entity_horizon_profiles",
    "risk_cards",
    "risk_card_evidence",
    "risk_entity_timeline",
    "hospital_aggregates",
    "drug_aggregates",
    "monthly_reports",
    "proof_cases",
    "work_order_reserved",
    "entity_display_lookup",
    "detector_catalog",
    "daily_detector_runs",
    "daily_detector_clues",
    "high_risk_detector_evidence",
}

REPORT_OR_PROFILING_TABLES = {
    "normalization_report",
    "feature_quality_report",
    "feature_parity_runtime_report",
    "selection_report",
    "detector_quality_gate",
    "disabled_detector_notes",
}


def rel(path: Path) -> str:
    return str(path.relative_to(REPO)).replace("\\", "/")


def parquet_rows(path: Path) -> int:
    return int(pq.ParquetFile(path).metadata.num_rows)


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def convert_csv_to_parquet(csv_path: Path) -> dict[str, Any]:
    parquet_path = csv_path.with_suffix(".parquet")
    frame = read_csv(csv_path)
    write_production_parquet(frame, parquet_path)
    return {
        "csv_path": rel(csv_path),
        "parquet_path": rel(parquet_path),
        "row_count": int(len(frame)),
        "columns": list(frame.columns),
        "action": "converted_csv_to_parquet",
    }


def update_manifest(batch_dir: Path) -> dict[str, Any]:
    manifest_path = batch_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["data_backend"] = "parquet"
    if isinstance(manifest.get("horizon_profile_table"), dict):
        manifest["horizon_profile_table"]["path"] = "risk_entity_horizon_profiles.parquet"
        manifest["horizon_profile_table"]["row_count"] = parquet_rows(batch_dir / "risk_entity_horizon_profiles.parquet")
    if isinstance(manifest.get("entity_display_lookup"), dict):
        manifest["entity_display_lookup"]["path"] = "entity_display_lookup.parquet"
        manifest["entity_display_lookup"]["row_count"] = parquet_rows(batch_dir / "entity_display_lookup.parquet")
    if isinstance(manifest.get("detector_tables"), dict):
        manifest["detector_tables"] = {
            "detector_catalog": "detector_catalog.parquet",
            "daily_detector_runs": "daily_detector_runs.parquet",
            "daily_detector_clues": "daily_detector_clues.parquet",
            "high_risk_detector_evidence": "high_risk_detector_evidence.parquet",
        }
    counts: dict[str, int] = {}
    for parquet_path in sorted(batch_dir.glob("*.parquet")):
        counts[parquet_path.stem] = parquet_rows(parquet_path)
    manifest["result_table_row_counts"] = {
        **{key: value for key, value in counts.items() if key in FORMAL_TABLES},
        **{key: value for key, value in counts.items() if key not in FORMAL_TABLES},
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "manifest_path": rel(manifest_path),
        "data_backend": manifest.get("data_backend"),
        "result_table_row_counts": manifest["result_table_row_counts"],
    }


def migrate_batch(batch_dir: Path) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    for csv_path in sorted(batch_dir.glob("*.csv")):
        parquet_path = csv_path.with_suffix(".parquet")
        table_name = csv_path.stem
        category = "formal_table" if table_name in FORMAL_TABLES else "report_or_profiling" if table_name in REPORT_OR_PROFILING_TABLES else "other_csv"
        if parquet_path.exists():
            actions.append(
                {
                    "csv_path": rel(csv_path),
                    "parquet_path": rel(parquet_path),
                    "category": category,
                    "parquet_row_count": parquet_rows(parquet_path),
                    "action": "kept_existing_parquet_duplicate",
                }
            )
            continue
        actions.append({**convert_csv_to_parquet(csv_path), "category": category})
    for table in sorted(FORMAL_TABLES):
        parquet_path = batch_dir / f"{table}.parquet"
        if not parquet_path.exists():
            blockers.append({"table": table, "issue": "missing_formal_parquet_table", "path": rel(parquet_path)})
    if blockers:
        return {"batch_dir": rel(batch_dir), "actions": actions, "blockers": blockers, "csv_deleted": []}
    manifest_update = update_manifest(batch_dir)
    deleted: list[str] = []
    for csv_path in sorted(batch_dir.glob("*.csv")):
        csv_path.unlink()
        deleted.append(rel(csv_path))
    validate_result_batch(batch_dir)
    return {
        "batch_dir": rel(batch_dir),
        "actions": actions,
        "blockers": blockers,
        "manifest_update": manifest_update,
        "csv_deleted": deleted,
    }


def migrate_root_registry() -> dict[str, Any]:
    csv_path = BATCH_ROOT / "available_observation_contexts.csv"
    parquet_path = BATCH_ROOT / "available_observation_contexts.parquet"
    if not csv_path.exists():
        return {"action": "no_root_registry_csv"}
    if not parquet_path.exists():
        result = convert_csv_to_parquet(csv_path)
    else:
        result = {
            "csv_path": rel(csv_path),
            "parquet_path": rel(parquet_path),
            "parquet_row_count": parquet_rows(parquet_path),
            "action": "kept_existing_parquet_duplicate",
        }
    csv_path.unlink()
    result["csv_deleted"] = rel(csv_path)
    return result


def write_reports(report: dict[str, Any]) -> None:
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Parquet-only migration report",
        "",
        f"- generated_at: {report['generated_at']}",
        f"- batch_root: `{report['batch_root']}`",
        f"- batches: {len(report['batches'])}",
        f"- root_registry_action: {report['root_registry'].get('action')}",
        "",
        "## Batch actions",
    ]
    for batch in report["batches"]:
        lines.extend(
            [
                "",
                f"### {batch['batch_dir']}",
                f"- actions: {len(batch.get('actions', []))}",
                f"- blockers: {len(batch.get('blockers', []))}",
                f"- csv_deleted: {len(batch.get('csv_deleted', []))}",
            ]
        )
        for blocker in batch.get("blockers", []):
            lines.append(f"- blocker: {blocker}")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    if not BASELINE_PATH.exists():
        raise FileNotFoundError(f"Baseline must exist before migration: {BASELINE_PATH}")
    batches = [m.parent for m in sorted(BATCH_ROOT.glob("report_month=*/batch_id=*/manifest.json"))]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "batch_root": rel(BATCH_ROOT),
        "baseline": rel(BASELINE_PATH),
        "root_registry": migrate_root_registry(),
        "batches": [migrate_batch(batch_dir) for batch_dir in batches],
    }
    write_reports(report)
    if any(batch.get("blockers") for batch in report["batches"]):
        return 2
    print(REPORT_JSON)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
