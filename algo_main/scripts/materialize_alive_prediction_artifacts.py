#!/usr/bin/env python
"""Materialize stable alive prediction facts/features/labels/train sets.

The default strategy is reuse-first: stable artifacts, then legacy cache copy,
then rebuild only when required and not in dry-run mode.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

import pandas as pd
import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from alg.artifacts.metadata import build_artifact_metadata, read_metadata, write_metadata
from alg.artifacts.paths import (
    get_alive_labels_path,
    get_candidate_entities_dir,
    get_fact_entity_month_path,
    get_fact_purchase_event_path,
    get_feature_table_path,
    get_train_set_dir,
)
from alg.cache.cache_manager import write_artifact
from alg.facts.demand_profile_builder import build_entity_demand_profile
from alg.facts.entity_month_builder import build_fact_entity_month
from alg.facts.purchase_event_builder import build_fact_purchase_event
from alg.features.alive_prediction_feature_builder import build_alive_prediction_feature_table
from alg.features.cutoff_dataset_builder import build_candidate_entities
from alg.labels.alive_label_builder import build_alive_labels

import migrate_alive_prediction_cache as legacy_migration


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def parse_bool(value: str) -> bool:
    return str(value).lower() in {"1", "true", "yes", "y", "on"}


def month_ends(start: str, end: str) -> list[pd.Timestamp]:
    return [period.to_timestamp("M") for period in pd.period_range(start=start, end=end, freq="M")]


def read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def artifact_exists(path: Path) -> bool:
    return path.exists() and bool(read_metadata(path))


def _legacy_plan_for(target: Path, *, mode: str = "copy") -> pd.DataFrame:
    root = project_root()
    source_dir = root / "data/cache/alive_prediction_sanity"
    plan = legacy_migration.build_migration_plan(source_dir, root / "data", mode=mode)
    if "target_path" not in plan.columns:
        return pd.DataFrame()
    return plan[plan["target_path"].map(lambda value: Path(str(value)).resolve() == target.resolve())].copy()


def _maybe_migrate_from_legacy(target: Path, *, dry_run: bool, overwrite: bool) -> str:
    matches = _legacy_plan_for(target)
    if matches.empty or "action" not in matches.columns:
        return "legacy_cache_not_found"
    executable = matches[matches["action"] == "copy_planned"]
    if executable.empty:
        return "legacy_cache_not_found"
    if dry_run:
        source = executable.iloc[0]["source_path"]
        print(f"[legacy cache found] {source}", flush=True)
        print(f"[migrate copy planned] {source} -> {target}", flush=True)
        return "legacy_copy_planned"
    executed = legacy_migration.execute_plan(executable, mode="copy", confirm=True, overwrite=overwrite)
    status = str(executed.iloc[0]["action"])
    print(f"[migrate copy] {executed.iloc[0]['source_path']} -> {target}: {status}", flush=True)
    return status


def _write_if_needed(df: pd.DataFrame, path: Path, metadata: dict[str, Any], *, overwrite: bool, dry_run: bool) -> str:
    if artifact_exists(path) and not overwrite:
        print(f"[artifact exists] {path}", flush=True)
        return "reused_existing"
    if dry_run:
        print(f"[dry-run write planned] {path}", flush=True)
        return "write_planned"
    return write_artifact(df, path, metadata=metadata, overwrite=overwrite)


def materialize_facts(args: argparse.Namespace, config: dict[str, Any], summary: list[dict[str, str]]) -> tuple[Path, Path]:
    root = project_root()
    drug_group_source = args.drug_group_source
    event_path = get_fact_purchase_event_path(root=root / "data", drug_group_source=drug_group_source)
    entity_month_path = get_fact_entity_month_path(root=root / "data", drug_group_source=drug_group_source)
    for artifact_path in [event_path, entity_month_path]:
        if artifact_exists(artifact_path) and not args.refresh:
            print(f"[artifact exists] {artifact_path}", flush=True)
            summary.append({"artifact": artifact_path.name, "path": str(artifact_path), "status": "reused_existing"})
        else:
            status = _maybe_migrate_from_legacy(artifact_path, dry_run=args.dry_run, overwrite=args.overwrite)
            summary.append({"artifact": artifact_path.name, "path": str(artifact_path), "status": status})
    if (artifact_exists(event_path) and artifact_exists(entity_month_path)) or args.dry_run:
        return event_path, entity_month_path

    model_base_path = root / "data/03_cleaned/bs_agent_dingdan_model_base.parquet"
    if not model_base_path.exists():
        print(f"[rebuild required] missing model_base: {model_base_path}", flush=True)
        return event_path, entity_month_path
    model_base = pd.read_parquet(model_base_path)
    events = build_fact_purchase_event(model_base, drug_group_source=drug_group_source)
    entity_month = build_fact_entity_month(events)
    _write_if_needed(
        events,
        event_path,
        build_artifact_metadata(artifact_name="fact_purchase_event", artifact_type="facts", df=events),
        overwrite=args.overwrite,
        dry_run=args.dry_run,
    )
    _write_if_needed(
        entity_month,
        entity_month_path,
        build_artifact_metadata(artifact_name="fact_entity_month", artifact_type="facts", df=entity_month),
        overwrite=args.overwrite,
        dry_run=args.dry_run,
    )
    return event_path, entity_month_path


def materialize_features(args: argparse.Namespace, config: dict[str, Any], summary: list[dict[str, str]]) -> dict[str, Path]:
    root = project_root()
    kwargs = {
        "root": root / "data",
        "drug_group_source": args.drug_group_source,
        "candidate_policy": args.candidate_policy,
        "max_monitor_gap_months": args.max_monitor_gap_months,
        "start_cutoff": args.start_cutoff,
        "end_cutoff": args.end_cutoff,
    }
    feature_dir = get_candidate_entities_dir(**kwargs)
    paths = {
        "candidate_entities": feature_dir / "candidate_entities.parquet",
        "entity_demand_profile": feature_dir / "entity_demand_profile.parquet",
        "alive_labels": get_alive_labels_path(**kwargs, horizons=args.horizons),
        "feature_table": get_feature_table_path(**kwargs, include_status_history=args.include_status_history),
    }
    for name, path in paths.items():
        if artifact_exists(path) and not args.refresh:
            print(f"[artifact exists] {path}", flush=True)
            status = "reused_existing"
        else:
            status = _maybe_migrate_from_legacy(path, dry_run=args.dry_run, overwrite=args.overwrite)
        summary.append({"artifact": name, "path": str(path), "status": status})
    if all(artifact_exists(path) for path in paths.values()) or args.dry_run:
        return paths

    event_path = get_fact_purchase_event_path(root=root / "data", drug_group_source=args.drug_group_source)
    entity_month_path = get_fact_entity_month_path(root=root / "data", drug_group_source=args.drug_group_source)
    if not event_path.exists() or not entity_month_path.exists():
        print("[rebuild required] missing facts for feature materialization", flush=True)
        return paths
    events = pd.read_parquet(event_path)
    entity_month = pd.read_parquet(entity_month_path)
    cutoff_months = month_ends(args.start_cutoff, args.end_cutoff)
    candidates, _candidate_report = build_candidate_entities(
        events,
        cutoff_months=cutoff_months,
        policy=args.candidate_policy,
        max_monitor_gap_months=args.max_monitor_gap_months,
    )
    demand_profile = build_entity_demand_profile(entity_month, cutoff_months=cutoff_months, cold_start=config.get("cold_start", {}))
    labels = build_alive_labels(events, candidates, horizons=tuple(args.horizons))
    features = build_alive_prediction_feature_table(
        entity_month,
        candidates,
        demand_profile=demand_profile,
        include_status_history=args.include_status_history,
        horizons=tuple(args.horizons),
    )
    objects = {
        "candidate_entities": candidates,
        "entity_demand_profile": demand_profile,
        "alive_labels": labels,
        "feature_table": features,
    }
    for name, df in objects.items():
        _write_if_needed(
            df,
            paths[name],
            build_artifact_metadata(
                artifact_name=name,
                artifact_type="features",
                df=df,
                extra={
                    "drug_group_source": args.drug_group_source,
                    "candidate_policy": args.candidate_policy,
                    "max_monitor_gap_months": args.max_monitor_gap_months,
                    "cutoff_start": args.start_cutoff,
                    "cutoff_end": args.end_cutoff,
                    "horizons": args.horizons,
                    "include_status_history": args.include_status_history,
                },
            ),
            overwrite=args.overwrite,
            dry_run=args.dry_run,
        )
    return paths


def materialize_train_sets(args: argparse.Namespace, summary: list[dict[str, str]]) -> None:
    root = project_root()
    feature_path = get_feature_table_path(
        root=root / "data",
        drug_group_source=args.drug_group_source,
        candidate_policy=args.candidate_policy,
        max_monitor_gap_months=args.max_monitor_gap_months,
        start_cutoff=args.start_cutoff,
        end_cutoff=args.end_cutoff,
        include_status_history=args.include_status_history,
    )
    labels_path = get_alive_labels_path(
        root=root / "data",
        drug_group_source=args.drug_group_source,
        candidate_policy=args.candidate_policy,
        max_monitor_gap_months=args.max_monitor_gap_months,
        start_cutoff=args.start_cutoff,
        end_cutoff=args.end_cutoff,
        horizons=args.horizons,
    )
    for horizon in args.horizons:
        train_dir = get_train_set_dir(
            root=root / "data",
            drug_group_source=args.drug_group_source,
            candidate_policy=args.candidate_policy,
            max_monitor_gap_months=args.max_monitor_gap_months,
            scope="recurring_only",
            horizon=horizon,
        )
        train_path = train_dir / "train_set.parquet"
        test_path = train_dir / "test_set.parquet"
        if args.dry_run:
            print(f"[dry-run train-set planned] {train_path}", flush=True)
            summary.append({"artifact": f"train_set_H{horizon}", "path": str(train_path), "status": "write_planned"})
            continue
        if not feature_path.exists() or not labels_path.exists():
            print(f"[rebuild required] missing feature/label artifacts for H{horizon}", flush=True)
            continue
        features = pd.read_parquet(feature_path)
        labels = pd.read_parquet(labels_path)
        label_cols = ["manufacturer_code", "hospital_code", "drug_group", "cutoff_month", f"label_die_H{horizon}"]
        dataset = features.merge(labels[label_cols], on=["manufacturer_code", "hospital_code", "drug_group", "cutoff_month"], how="left")
        one_shot_attention = (
            dataset["one_shot_high_value_silence_flag"].astype(bool)
            if "one_shot_high_value_silence_flag" in dataset
            else pd.Series(False, index=dataset.index)
        )
        recurring = dataset[
            (dataset["purchase_count_asof_cutoff"] >= 3)
            & (dataset["active_month_count_asof_cutoff"] >= 2)
            & (~one_shot_attention)
        ].copy()
        train_dir.mkdir(parents=True, exist_ok=True)
        recurring.to_parquet(train_path, index=False)
        recurring.iloc[0:0].to_parquet(test_path, index=False)
        metadata = build_artifact_metadata(artifact_name=f"train_set_H{horizon}", artifact_type="train_sets", df=recurring)
        write_metadata(train_path, metadata)
        write_metadata(test_path, build_artifact_metadata(artifact_name=f"test_set_H{horizon}", artifact_type="train_sets", df=recurring.iloc[0:0]))
        summary.append({"artifact": f"train_set_H{horizon}", "path": str(train_path), "status": "written"})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize alive prediction artifacts.")
    parser.add_argument("--config", default="configs/features/alive_prediction_feature_view.yaml")
    parser.add_argument("--start-cutoff", default="2024-01")
    parser.add_argument("--end-cutoff", default="2024-12")
    parser.add_argument("--horizons", nargs="+", type=int, default=[3, 6, 12])
    parser.add_argument("--candidate-policy", default="monitorable")
    parser.add_argument("--max-monitor-gap-months", type=int, default=12)
    parser.add_argument("--drug-group-source", default="drug_code")
    parser.add_argument("--include-status-history", type=parse_bool, default=False)
    parser.add_argument("--layers", nargs="+", default=["facts", "features", "labels", "train_sets"])
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = project_root()
    config = read_yaml(root / args.config)
    summary: list[dict[str, str]] = []
    if "facts" in args.layers:
        materialize_facts(args, config, summary)
    if "features" in args.layers or "labels" in args.layers:
        materialize_features(args, config, summary)
    if "train_sets" in args.layers:
        materialize_train_sets(args, summary)
    for row in summary:
        print(f"[artifact-summary] {row['artifact']} {row['status']} {row['path']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
