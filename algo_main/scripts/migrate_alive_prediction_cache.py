#!/usr/bin/env python
"""Plan or copy legacy alive prediction sanity caches into stable data layers.

Default behavior is a dry run. It never deletes source files.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
from typing import Any

import pandas as pd

from alg.artifacts.metadata import build_artifact_metadata, metadata_path, read_metadata, write_metadata
from alg.artifacts.paths import (
    get_alive_labels_path,
    get_candidate_entities_dir,
    get_fact_entity_month_path,
    get_fact_purchase_event_path,
    get_feature_table_path,
    get_output_dir,
)


FACT_ARTIFACTS = {"fact_purchase_event", "fact_entity_month"}
KNOWN_ARTIFACTS = {
    "fact_purchase_event",
    "fact_entity_month",
    "candidate_entities",
    "entity_demand_profile",
    "alive_labels",
    "alive_prediction_features",
    "feature_null_report",
}


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def parse_legacy_name(path: Path) -> dict[str, Any] | None:
    if path.suffix != ".parquet":
        return None
    parts = path.stem.split("__")
    if len(parts) != 8:
        return None
    artifact, drug_group_source, start_cutoff, end_cutoff, policy, gap_text, horizons, status = parts
    if not gap_text.startswith("gap"):
        return None
    return {
        "artifact": artifact,
        "drug_group_source": drug_group_source,
        "start_cutoff": start_cutoff,
        "end_cutoff": end_cutoff,
        "candidate_policy": policy,
        "max_monitor_gap_months": int(gap_text.removeprefix("gap")),
        "horizons": horizons,
        "include_status_history": status == "status1",
        "status": status,
    }


def legacy_row_count(path: Path) -> int | None:
    meta = read_metadata(path)
    if "row_count" in meta:
        return int(meta["row_count"])
    try:
        import pyarrow.parquet as pq

        return int(pq.ParquetFile(path).metadata.num_rows)
    except Exception:
        try:
            return int(len(pd.read_parquet(path)))
        except Exception:
            return None


def target_for_legacy(info: dict[str, Any], target_root: Path) -> Path | None:
    artifact = info["artifact"]
    common = {
        "root": target_root,
        "drug_group_source": info["drug_group_source"],
    }
    if artifact == "fact_purchase_event":
        return get_fact_purchase_event_path(**common)
    if artifact == "fact_entity_month":
        return get_fact_entity_month_path(**common)
    feature_kwargs = {
        **common,
        "version": "v1",
        "candidate_policy": info["candidate_policy"],
        "max_monitor_gap_months": info["max_monitor_gap_months"],
        "start_cutoff": info["start_cutoff"],
        "end_cutoff": info["end_cutoff"],
    }
    feature_dir = get_candidate_entities_dir(**feature_kwargs)
    if artifact == "candidate_entities":
        return feature_dir / "candidate_entities.parquet"
    if artifact == "entity_demand_profile":
        return feature_dir / "entity_demand_profile.parquet"
    if artifact == "alive_labels":
        horizon_values = [int(value) for value in info["horizons"].removeprefix("H").split("_")]
        return get_alive_labels_path(**feature_kwargs, horizons=horizon_values)
    if artifact == "alive_prediction_features":
        return get_feature_table_path(**feature_kwargs, include_status_history=info["include_status_history"])
    if artifact == "feature_null_report":
        return (
            get_output_dir(root=target_root, output_type="sanity_reports")
            / f"cutoff_{info['start_cutoff']}_{info['end_cutoff']}"
            / "feature_null_report.parquet"
        )
    return None


def _metadata_match(source: Path, target: Path, source_row_count: int | None) -> bool:
    if not target.exists():
        return False
    target_meta = read_metadata(target)
    if not target_meta:
        return False
    if source_row_count is not None and target_meta.get("row_count") not in {source_row_count, str(source_row_count)}:
        return False
    return True


def _artifact_type(artifact: str) -> str:
    if artifact.startswith("fact_"):
        return "facts"
    if artifact == "feature_null_report":
        return "outputs"
    return "features"


def _write_target_meta(source: Path, target: Path, info: dict[str, Any], row_count: int | None) -> None:
    columns: list[str] = []
    try:
        columns = list(pd.read_parquet(target, columns=[]).columns)
    except Exception:
        pass
    metadata = build_artifact_metadata(
        artifact_name=info["artifact"],
        artifact_type=_artifact_type(info["artifact"]),
        df=None,
        source_artifacts=[str(source)],
        source_hashes={"legacy_source_size": str(source.stat().st_size)},
        extra={
            "row_count": row_count,
            "columns": columns,
            "legacy_source_path": str(source),
            "drug_group_source": info["drug_group_source"],
            "candidate_policy": info.get("candidate_policy"),
            "max_monitor_gap_months": info.get("max_monitor_gap_months"),
            "cutoff_start": info.get("start_cutoff"),
            "cutoff_end": info.get("end_cutoff"),
            "horizons": info.get("horizons"),
            "include_status_history": info.get("include_status_history"),
        },
    )
    write_metadata(target, metadata)


def build_migration_plan(source_dir: Path, target_root: Path, *, mode: str, overwrite: bool = False) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    parquet_files = sorted(source_dir.glob("*.parquet"))
    grouped_facts: dict[tuple[str, str], list[tuple[Path, dict[str, Any]]]] = {}
    non_fact: list[tuple[Path, dict[str, Any] | None]] = []

    for path in parquet_files:
        info = parse_legacy_name(path)
        if info is None or info["artifact"] not in KNOWN_ARTIFACTS:
            non_fact.append((path, info))
            continue
        if info["artifact"] in FACT_ARTIFACTS:
            grouped_facts.setdefault((info["artifact"], info["drug_group_source"]), []).append((path, info))
        else:
            non_fact.append((path, info))

    selected: list[tuple[Path, dict[str, Any], str]] = []
    for (_artifact, _drug), items in grouped_facts.items():
        items_with_size = sorted(items, key=lambda item: (item[0].stat().st_size, item[0].stat().st_mtime), reverse=True)
        selected_path, selected_info = items_with_size[0]
        duplicate_sources = [str(path) for path, _ in items_with_size[1:]]
        selected.append((selected_path, selected_info, f"duplicate_sources={json.dumps(duplicate_sources, ensure_ascii=False)}"))
        for duplicate_path, duplicate_info in items_with_size[1:]:
            rows.append(
                {
                    "source_path": str(duplicate_path),
                    "target_path": str(target_for_legacy(duplicate_info, target_root)),
                    "action": "already_exists",
                    "status": "skipped",
                    "reason": f"duplicate_fact_source_selected={selected_path}",
                    "source_row_count": legacy_row_count(duplicate_path),
                    "target_exists": False,
                    "metadata_match": False,
                }
            )

    for path, info in non_fact:
        if info is None or info["artifact"] not in KNOWN_ARTIFACTS:
            rows.append(
                {
                    "source_path": str(path),
                    "target_path": "",
                    "action": "skipped_unknown_artifact",
                    "status": "skipped",
                    "reason": "unknown legacy artifact filename",
                    "source_row_count": legacy_row_count(path),
                    "target_exists": False,
                    "metadata_match": False,
                }
            )
        else:
            selected.append((path, info, ""))

    for source, info, extra_reason in selected:
        target = target_for_legacy(info, target_root)
        row_count = legacy_row_count(source)
        source_meta_missing = not metadata_path(source).exists()
        if target is None:
            action = "skipped_unknown_artifact"
            status = "skipped"
            reason = "no target mapping"
            target_exists = False
            metadata_match = False
        else:
            target_exists = target.exists()
            metadata_match = _metadata_match(source, target, row_count)
            if target_exists and metadata_match:
                action = "already_exists"
                status = "ok"
                reason = "target exists and metadata matches"
            elif target_exists and not overwrite:
                action = "skipped_conflict"
                status = "conflict"
                reason = "target exists and metadata does not match"
            elif source_meta_missing:
                action = "skipped_missing_metadata"
                status = "needs_review"
                reason = "legacy sidecar metadata missing"
            else:
                action = f"{mode}_planned"
                status = "ok"
                reason = "ready"
        if extra_reason:
            reason = f"{reason}; {extra_reason}"
        rows.append(
            {
                "source_path": str(source),
                "target_path": str(target) if target else "",
                "action": action,
                "status": status,
                "reason": reason,
                "source_row_count": row_count,
                "target_exists": target_exists,
                "metadata_match": metadata_match,
            }
        )
    return pd.DataFrame(rows)


def execute_plan(plan: pd.DataFrame, *, mode: str, confirm: bool, overwrite: bool) -> pd.DataFrame:
    if not confirm:
        return plan
    executed = plan.copy()
    for idx, row in executed.iterrows():
        if row["action"] != f"{mode}_planned":
            continue
        source = Path(row["source_path"])
        target = Path(row["target_path"])
        if target.exists() and not overwrite:
            executed.loc[idx, "action"] = "skipped_conflict"
            executed.loc[idx, "status"] = "conflict"
            executed.loc[idx, "reason"] = "target appeared before execution"
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if mode == "copy":
            shutil.copy2(source, target)
            executed.loc[idx, "action"] = "copy_done"
        elif mode == "move":
            shutil.move(str(source), str(target))
            executed.loc[idx, "action"] = "move_done"
        else:  # pragma: no cover - argparse prevents this
            raise ValueError(mode)
        info = parse_legacy_name(target if mode == "move" else source)
        if info is not None:
            _write_target_meta(source, target, info, row.get("source_row_count"))
        executed.loc[idx, "status"] = "ok"
        executed.loc[idx, "target_exists"] = True
    return executed


def write_reports(plan: pd.DataFrame, reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    plan_path = reports_dir / "alive_prediction_cache_migration_plan.csv"
    report_path = reports_dir / "alive_prediction_cache_migration_report.md"
    plan.to_csv(plan_path, index=False, encoding="utf-8-sig")
    lines = [
        "# Alive Prediction Cache Migration Report",
        "",
        "This report is generated without deleting legacy cache files.",
        "",
        "## Status Counts",
        plan["status"].value_counts(dropna=False).to_markdown() if not plan.empty else "No files found.",
        "",
        "## Action Counts",
        plan["action"].value_counts(dropna=False).to_markdown() if not plan.empty else "No files found.",
        "",
        "## Plan",
        plan.to_markdown(index=False) if not plan.empty else "No files found.",
        "",
        "Suggested cleanup, not performed: rows marked duplicate_fact_source are candidates for later manual review only. This script did not delete them.",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan/copy legacy alive prediction cache artifacts.")
    parser.add_argument("--source-dir", default="data/cache/alive_prediction_sanity")
    parser.add_argument("--target-root", default="data")
    parser.add_argument("--reports-dir", default="reports")
    parser.add_argument("--mode", choices=["copy", "move"], default="copy")
    parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = project_root()
    source_dir = root / args.source_dir
    target_root = root / args.target_root
    reports_dir = root / args.reports_dir
    plan = build_migration_plan(source_dir, target_root, mode=args.mode, overwrite=args.overwrite)
    if args.confirm and not args.dry_run:
        plan = execute_plan(plan, mode=args.mode, confirm=True, overwrite=args.overwrite)
    write_reports(plan, reports_dir)
    print(f"[migration] source_dir={source_dir}", flush=True)
    print(f"[migration] target_root={target_root}", flush=True)
    print(f"[migration] dry_run={args.dry_run} confirm={args.confirm} mode={args.mode}", flush=True)
    print(f"[migration] wrote {reports_dir / 'alive_prediction_cache_migration_plan.csv'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
