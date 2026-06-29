#!/usr/bin/env python
"""Generate local sanity reports for alive prediction.

This script does not train models and does not save model artifacts. It reads
the local model_base parquet, builds fact/label/feature sanity tables, caches
large intermediate Parquet files, and writes review reports under reports/.

Suggested local runtime budget is 20 minutes. The first run builds caches and
can be slower; later cache hits should be significantly faster.

PowerShell examples:

    $env:PYTHONPATH='src'
    python scripts\\run_alive_prediction_sanity_reports.py `
      --min-rows 50000 `
      --start-cutoff 2024-10 `
      --end-cutoff 2024-12 `
      --output-dir reports/alive_prediction_2024Q4 `
      --cache-intermediate

    $env:PYTHONPATH='src'
    python scripts\\run_alive_prediction_sanity_reports.py `
      --min-rows 50000 `
      --start-cutoff 2024-10 `
      --end-cutoff 2024-12 `
      --output-dir reports/alive_prediction_2024Q4 `
      --cache-intermediate `
      --refresh-cache
"""

from __future__ import annotations

import argparse
import json
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pandas as pd
import yaml

from alg.facts.demand_profile_builder import build_entity_demand_profile
from alg.facts.entity_month_builder import build_fact_entity_month
from alg.facts.purchase_event_builder import build_fact_purchase_event
from alg.features.alive_prediction_feature_builder import build_alive_prediction_feature_table
from alg.features.cutoff_dataset_builder import build_candidate_entities
from alg.labels.alive_label_builder import build_alive_labels
from alg.experiments.baseline_rules import (
    add_one_shot_high_value_silence_flags,
    add_recurring_candidate_flag,
    build_model_probability_topk_placeholder,
    build_one_shot_attention_list,
    build_rule_baseline_scores,
    evaluate_rule_baseline_smoke,
)
from alg.metrics.report import (
    build_entity_profile_report,
    build_feature_null_report,
    build_label_distribution_report,
    build_leakage_guardrail_report,
)
from alg.utils.months import add_months


@contextmanager
def timed_step(name: str, timings: dict[str, float]):
    start = time.perf_counter()
    print(f"[alive-sanity] start {name}", flush=True)
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        timings[name] = elapsed
        print(f"[alive-sanity] done {name}: {elapsed:.2f}s", flush=True)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _month_ends(start: str, end: str) -> list[pd.Timestamp]:
    return [period.to_timestamp("M") for period in pd.period_range(start=start, end=end, freq="M")]


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _label_distribution_by_cutoff(labels: pd.DataFrame, horizons: tuple[int, ...]) -> pd.DataFrame:
    rows = []
    for cutoff, group in labels.groupby("cutoff_month", dropna=False):
        row = {"cutoff_month": cutoff, "entity_count": int(len(group))}
        for horizon in horizons:
            col = f"label_die_H{horizon}"
            if col in group:
                row[f"{col}_positive_rate"] = float(group[col].mean())
                row[f"{col}_positive_count"] = int(group[col].sum())
        rows.append(row)
    return pd.DataFrame(rows)


def _demand_pattern_report(demand_profile: pd.DataFrame) -> str:
    lines = ["# Demand Pattern Profile", ""]
    if "demand_pattern_type_asof_cutoff" in demand_profile:
        lines.append("## Demand Pattern Counts")
        lines.append(demand_profile["demand_pattern_type_asof_cutoff"].value_counts(dropna=False).to_markdown())
        lines.append("")
    if "cold_start_flag" in demand_profile:
        lines.append(f"- cold_start_sample_rate: {float(demand_profile['cold_start_flag'].mean())}")
    for column in [
        "active_month_count_asof_cutoff",
        "purchase_count_asof_cutoff",
        "months_observed_asof_cutoff",
        "adi_asof_cutoff",
        "cv2_quantity_asof_cutoff",
    ]:
        if column in demand_profile:
            lines.append("")
            lines.append(f"## {column}")
            lines.append(demand_profile[column].describe().to_markdown())
    return "\n".join(lines)


def _value_feature_summary(features: pd.DataFrame) -> str:
    value_cols = [
        column
        for column in features.columns
        if column.startswith("historical_avg_monthly_") or column.startswith("value_at_risk_")
    ]
    if not value_cols:
        return "# Value Feature Summary\n\nNo value feature columns found."
    return "# Value Feature Summary\n\n" + features[value_cols].describe().to_markdown()


def _join_features_labels(features: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    keys = ["manufacturer_code", "hospital_code", "drug_group", "cutoff_month"]
    label_cols = keys + [column for column in labels.columns if column.startswith("label_")]
    return features.merge(labels[label_cols], on=keys, how="left")


def _label_rates_by_group(df: pd.DataFrame, group_cols: list[str], horizons: tuple[int, ...]) -> pd.DataFrame:
    rows = []
    for group_key, group in df.groupby(group_cols, dropna=False):
        if len(group_cols) == 1:
            group_key = (group_key,)
        row = dict(zip(group_cols, group_key))
        row["entity_count"] = int(len(group))
        for horizon in horizons:
            col = f"label_die_H{horizon}"
            if col in group:
                row[f"{col}_positive_rate"] = float(group[col].mean())
        rows.append(row)
    return pd.DataFrame(rows)


def _purchase_count_bucket(value: float) -> str:
    if value == 1:
        return "1"
    if value == 2:
        return "2"
    if 3 <= value <= 5:
        return "3-5"
    if 6 <= value <= 10:
        return "6-10"
    return ">=11"


def _active_month_bucket(value: float) -> str:
    if value == 1:
        return "1"
    if value == 2:
        return "2"
    if 3 <= value <= 5:
        return "3-5"
    if 6 <= value <= 12:
        return "6-12"
    return ">=13"


def _recurring_subset_report(df: pd.DataFrame, horizons: tuple[int, ...]) -> pd.DataFrame:
    rows = []
    for cutoff, group in df.groupby("cutoff_month", dropna=False):
        recurring = group[group["recurring_candidate"]]
        row = {
            "cutoff_month": cutoff,
            "entity_count_all": int(len(group)),
            "entity_count_recurring": int(len(recurring)),
            "recurring_rate": float(len(recurring) / len(group)) if len(group) else 0.0,
        }
        for horizon in horizons:
            col = f"label_die_H{horizon}"
            row[f"{col}_positive_rate_all"] = float(group[col].mean()) if col in group else None
            row[f"{col}_positive_rate_recurring"] = float(recurring[col].mean()) if col in recurring and len(recurring) else None
        rows.append(row)
    return pd.DataFrame(rows)


def _one_shot_report_markdown(rule_scored: pd.DataFrame) -> str:
    one_shot = rule_scored[rule_scored["one_shot_flag"]]
    high_value_one_shot = one_shot[one_shot["one_shot_high_value_flag"]]
    attention = rule_scored[rule_scored["one_shot_high_value_silence_flag"]]
    lines = ["# One-Shot High-Value Silence Report", ""]
    total = max(len(rule_scored), 1)
    one_shot_count = len(one_shot)
    lines.extend(
        [
            f"- one_shot_entity_count: {one_shot_count}",
            f"- one_shot_rate: {one_shot_count / total}",
            f"- high_value_one_shot_count: {len(high_value_one_shot)}",
            f"- high_value_one_shot_rate: {len(high_value_one_shot) / max(one_shot_count, 1)}",
            f"- one_shot_high_value_silence_count: {len(attention)}",
            f"- one_shot_high_value_silence_rate: {len(attention) / total}",
            "",
            "One-shot high-value silence entities are recalled by a business rule; they are not model_probability_topk rows and do not have calibrated churn_probability from the probability model.",
        ]
    )
    if not attention.empty:
        lines.extend(
            [
                "",
                "## Top manufacturer_code",
                attention["manufacturer_code"].value_counts().head(20).to_markdown(),
                "",
                "## Top drug_group",
                attention["drug_group"].value_counts().head(20).to_markdown(),
                "",
                "## value_at_risk_amount_nonnegative_H12_asof_cutoff",
                attention["value_at_risk_amount_nonnegative_H12_asof_cutoff"].describe().to_markdown(),
            ]
        )
    return "\n".join(lines)


def _full_year_diagnosis(
    summary: dict,
    candidate_report: pd.DataFrame,
    label_by_cutoff: pd.DataFrame,
    feature_null: pd.DataFrame,
    demand_profile: pd.DataFrame,
    rule_scored: pd.DataFrame,
    recurring_report: pd.DataFrame,
) -> str:
    lines = ["# Alive Prediction 2024 Full-Year Sanity Diagnosis", ""]
    lines.extend(
        [
            f"- model_base_rows: {summary['model_base_rows']}",
            f"- purchase_month_min: {summary['purchase_month_min']}",
            f"- purchase_month_max: {summary['purchase_month_max']}",
            f"- cutoff_range: {summary['start_cutoff']} to {summary['end_cutoff']}",
            f"- label_window_closed: {summary['label_window_closed']}",
            f"- candidate_policy: {summary['candidate_policy']}",
            f"- max_monitor_gap_months: {summary['max_monitor_gap_months']}",
            f"- drug_group_source: {summary['drug_group_source']}",
            f"- cache_hit_count: {summary['cache_hit_count']}",
            f"- cache_miss_count: {summary['cache_miss_count']}",
            f"- cache_written_count: {summary['cache_written_count']}",
            f"- demand_profile_bottleneck: {summary.get('timing_build_entity_demand_profile')} seconds",
            "",
            "当前主任务高度稀疏，不能只用总体 die rate 判断模型可行性；需要分层观察 one-shot、cold_start、intermittent/lumpy 与 recurring 子集。",
            "",
            "## Candidate Trend",
            candidate_report.to_markdown(index=False),
            "",
            "## Label Trend",
            label_by_cutoff.to_markdown(index=False),
            "",
            "## Demand Pattern Distribution",
            demand_profile["demand_pattern_type_asof_cutoff"].value_counts(dropna=False).to_markdown()
            if "demand_pattern_type_asof_cutoff" in demand_profile
            else "No demand pattern column.",
            "",
            "## Top Feature Null Issues",
            feature_null.sort_values("null_rate", ascending=False).head(20).to_markdown(index=False),
            "",
            "## Value At Risk Negative Flags",
            f"- negative_value_at_risk_amount_flag_rate: {float(rule_scored['negative_value_at_risk_amount_flag'].mean())}",
            f"- negative_value_at_risk_quantity_flag_rate: {float(rule_scored['negative_value_at_risk_quantity_flag'].mean())}",
            "",
            "## One-Shot Summary",
            f"- one_shot_rate: {float(rule_scored['one_shot_flag'].mean())}",
            f"- high_value_one_shot_rate: {float((rule_scored['one_shot_flag'] & rule_scored['one_shot_high_value_flag']).mean())}",
            f"- one_shot_high_value_silence_count: {int(rule_scored['one_shot_high_value_silence_flag'].sum())}",
            "",
            "## Recurring Subset",
            recurring_report.to_markdown(index=False),
            "",
            "## Rule Baseline Readiness",
            "The data is ready for rule baseline smoke testing. Logistic Regression / LightGBM small / CatBoost small should wait until one-shot and recurring subsets are reported separately.",
        ]
    )
    return "\n".join(lines)


def _file_meta(path: Path) -> dict:
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "mtime": stat.st_mtime,
        "size": stat.st_size,
    }


def _cache_meta_path(path: Path) -> Path:
    return path.with_suffix(".meta.json")


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _metadata_matches(actual: dict, expected: dict) -> bool:
    return all(actual.get(key) == value for key, value in expected.items())


def _cache_name(
    stem: str,
    drug_group_source: str,
    start_cutoff: str,
    end_cutoff: str,
    candidate_policy: str,
    max_monitor_gap_months: int,
    horizons: tuple[int, ...],
    include_status_history: bool,
) -> str:
    horizon_text = "H" + "_".join(str(horizon) for horizon in horizons)
    status_text = "status1" if include_status_history else "status0"
    return (
        f"{stem}__{drug_group_source}__{start_cutoff}__{end_cutoff}__"
        f"{candidate_policy}__gap{max_monitor_gap_months}__{horizon_text}__{status_text}.parquet"
    )


def _load_or_build_dataframe(
    name: str,
    path: Path,
    expected_meta: dict,
    builder: Callable[[], pd.DataFrame],
    cache_intermediate: bool,
    refresh_cache: bool,
    cache_stats: dict[str, int],
    manifest_entries: dict,
) -> pd.DataFrame:
    meta_path = _cache_meta_path(path)
    if cache_intermediate and refresh_cache:
        print(f"[cache refresh] {name}: {path}", flush=True)
    if cache_intermediate and not refresh_cache and path.exists() and meta_path.exists():
        actual_meta = _read_json(meta_path)
        if _metadata_matches(actual_meta, expected_meta):
            print(f"[cache hit] {name}: {path}", flush=True)
            cache_stats["hit"] += 1
            df = pd.read_parquet(path)
            manifest_entries[name] = {"path": str(path), "meta_path": str(meta_path), "status": "hit", "row_count": int(len(df))}
            return df
        print(f"[cache miss] {name}: metadata mismatch", flush=True)
    elif cache_intermediate and not refresh_cache:
        print(f"[cache miss] {name}: missing cache", flush=True)
    else:
        print(f"[cache disabled] {name}" if not cache_intermediate else f"[cache refresh] {name}", flush=True)
    cache_stats["miss"] += 1
    df = builder()
    if cache_intermediate:
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)
        payload = {
            **expected_meta,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "row_count": int(len(df)),
            "cache_path": str(path),
        }
        _write_json(meta_path, payload)
        print(f"[cache write] {name}: {path}", flush=True)
        cache_stats["written"] += 1
        manifest_entries[name] = {"path": str(path), "meta_path": str(meta_path), "status": "written", "row_count": int(len(df))}
    else:
        manifest_entries[name] = {"path": None, "meta_path": None, "status": "not_cached", "row_count": int(len(df))}
    return df


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate alive prediction sanity reports from local model_base.")
    parser.add_argument("--model-base", default="data/03_cleaned/bs_agent_dingdan_model_base.parquet")
    parser.add_argument("--output-dir", default="reports/alive_prediction")
    parser.add_argument("--start-cutoff", default="2024-10")
    parser.add_argument("--end-cutoff", default="2024-12")
    parser.add_argument("--min-rows", type=int, default=50_000)
    parser.add_argument("--include-status-history", action="store_true")
    parser.add_argument("--cache-intermediate", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--cache-dir", default="data/cache/alive_prediction_sanity")
    return parser.parse_args()


def _assert_label_window_closed(cutoff_months: list[pd.Timestamp], horizons: tuple[int, ...], purchase_month_max: pd.Timestamp) -> tuple[pd.Timestamp, bool]:
    max_required = add_months(max(cutoff_months), max(horizons))
    closed = max_required <= purchase_month_max
    if not closed:
        raise RuntimeError(
            f"Label window is not closed: required up to {max_required}, but purchase_month_max={purchase_month_max}"
        )
    return max_required, closed


def _assert_feature_label_keys_match(features: pd.DataFrame, labels: pd.DataFrame) -> None:
    keys = ["manufacturer_code", "hospital_code", "drug_group", "cutoff_month"]
    feature_keys = set(map(tuple, features[keys].to_numpy()))
    label_keys = set(map(tuple, labels[keys].to_numpy()))
    if feature_keys != label_keys:
        raise RuntimeError(
            f"Feature/label key mismatch: label_minus_feature={len(label_keys - feature_keys)}, "
            f"feature_minus_label={len(feature_keys - label_keys)}"
        )


def main() -> int:
    timings: dict[str, float] = {}
    total_start = time.perf_counter()
    args = _parse_args()
    root = _project_root()
    config_path = root / "configs/features/alive_prediction_feature_view.yaml"
    rule_config_path = root / "configs/experiments/alive_prediction_rule_baseline.yaml"
    model_base_path = root / args.model_base
    output_dir = root / args.output_dir
    cache_dir = root / args.cache_dir
    cache_stats = {"hit": 0, "miss": 0, "written": 0}
    manifest_entries: dict = {}

    with timed_step("read_model_base", timings):
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        rule_config = yaml.safe_load(rule_config_path.read_text(encoding="utf-8"))
        model_base = pd.read_parquet(model_base_path)
        if len(model_base) < args.min_rows:
            raise RuntimeError(f"model_base rows {len(model_base)} is smaller than required min_rows {args.min_rows}")

    horizons = tuple(config["targets"]["horizons_months"])
    cutoff_months = _month_ends(args.start_cutoff, args.end_cutoff)
    candidate_policy = config["candidate_policy"]["default"]
    max_monitor_gap_months = int(config["candidate_policy"]["max_monitor_gap_months"])
    drug_group_source = config["entity"]["primary_drug_group_source"]
    cold_start = config["cold_start"]
    source_meta = _file_meta(model_base_path)
    config_meta = _file_meta(config_path)
    expected_meta = {
        "source_model_base_path": source_meta["path"],
        "source_model_base_mtime": source_meta["mtime"],
        "source_model_base_size": source_meta["size"],
        "config_path": config_meta["path"],
        "config_mtime": config_meta["mtime"],
        "drug_group_source": drug_group_source,
        "start_cutoff": args.start_cutoff,
        "end_cutoff": args.end_cutoff,
        "candidate_policy": candidate_policy,
        "max_monitor_gap_months": max_monitor_gap_months,
        "horizons": list(horizons),
        "include_status_history": bool(args.include_status_history),
    }
    cache_suffix = {
        "drug_group_source": drug_group_source,
        "start_cutoff": args.start_cutoff,
        "end_cutoff": args.end_cutoff,
        "candidate_policy": candidate_policy,
        "max_monitor_gap_months": max_monitor_gap_months,
        "horizons": horizons,
        "include_status_history": bool(args.include_status_history),
    }
    def cache_path(stem: str) -> Path:
        return cache_dir / _cache_name(stem, **cache_suffix)

    with timed_step("build_fact_purchase_event", timings):
        events = _load_or_build_dataframe(
            "fact_purchase_event",
            cache_path("fact_purchase_event"),
            expected_meta,
            lambda: build_fact_purchase_event(model_base, drug_group_source=drug_group_source),
            args.cache_intermediate,
            args.refresh_cache,
            cache_stats,
            manifest_entries,
        )

    purchase_month_min = events["purchase_month"].min()
    purchase_month_max = events["purchase_month"].max()
    max_required_label_month, label_window_closed = _assert_label_window_closed(cutoff_months, horizons, purchase_month_max)

    with timed_step("build_fact_entity_month", timings):
        entity_month = _load_or_build_dataframe(
            "fact_entity_month",
            cache_path("fact_entity_month"),
            expected_meta,
            lambda: build_fact_entity_month(events),
            args.cache_intermediate,
            args.refresh_cache,
            cache_stats,
            manifest_entries,
        )

    with timed_step("build_candidate_entities", timings):
        candidates = _load_or_build_dataframe(
            "candidate_entities",
            cache_path("candidate_entities"),
            expected_meta,
            lambda: build_candidate_entities(
                events,
                cutoff_months=cutoff_months,
                policy=candidate_policy,
                max_monitor_gap_months=max_monitor_gap_months,
            )[0],
            args.cache_intermediate,
            args.refresh_cache,
            cache_stats,
            manifest_entries,
        )
        candidate_report = _load_or_build_dataframe(
            "candidate_report",
            cache_path("candidate_report"),
            expected_meta,
            lambda: build_candidate_entities(
                events,
                cutoff_months=cutoff_months,
                policy=candidate_policy,
                max_monitor_gap_months=max_monitor_gap_months,
            )[1],
            args.cache_intermediate,
            args.refresh_cache,
            cache_stats,
            manifest_entries,
        )

    with timed_step("build_entity_demand_profile", timings):
        demand_profile = _load_or_build_dataframe(
            "entity_demand_profile",
            cache_path("entity_demand_profile"),
            expected_meta,
            lambda: build_entity_demand_profile(entity_month, cutoff_months=cutoff_months, cold_start=cold_start),
            args.cache_intermediate,
            args.refresh_cache,
            cache_stats,
            manifest_entries,
        )

    with timed_step("build_alive_labels", timings):
        labels = _load_or_build_dataframe(
            "alive_labels",
            cache_path("alive_labels"),
            expected_meta,
            lambda: build_alive_labels(events, candidates, horizons=horizons),
            args.cache_intermediate,
            args.refresh_cache,
            cache_stats,
            manifest_entries,
        )

    with timed_step("build_alive_prediction_feature_table", timings):
        features = _load_or_build_dataframe(
            "alive_prediction_features",
            cache_path("alive_prediction_features"),
            expected_meta,
            lambda: build_alive_prediction_feature_table(
                entity_month,
                candidates,
                demand_profile=demand_profile,
                include_status_history=args.include_status_history,
                horizons=horizons,
            ),
            args.cache_intermediate,
            args.refresh_cache,
            cache_stats,
            manifest_entries,
        )
    _assert_feature_label_keys_match(features, labels)
    joined = _join_features_labels(features, labels)
    joined = add_recurring_candidate_flag(joined, **rule_config["recurring_candidate"])
    rule_scored = add_one_shot_high_value_silence_flags(joined, rule_config["one_shot_high_value_silence"])
    rule_scored = build_rule_baseline_scores(rule_scored)

    with timed_step("build_feature_null_report", timings):
        feature_null = _load_or_build_dataframe(
            "feature_null_report",
            cache_path("feature_null_report"),
            expected_meta,
            lambda: build_feature_null_report(features),
            args.cache_intermediate,
            args.refresh_cache,
            cache_stats,
            manifest_entries,
        )

    with timed_step("build_label_distribution_by_cutoff", timings):
        label_by_cutoff = _load_or_build_dataframe(
            "label_distribution_by_cutoff",
            cache_path("label_distribution_by_cutoff"),
            expected_meta,
            lambda: _label_distribution_by_cutoff(labels, horizons),
            args.cache_intermediate,
            args.refresh_cache,
            cache_stats,
            manifest_entries,
        )

    with timed_step("write_reports", timings):
        output_dir.mkdir(parents=True, exist_ok=True)
        candidate_report.to_csv(output_dir / "candidate_counts_by_cutoff.csv", index=False, encoding="utf-8-sig")
        label_by_cutoff.to_csv(output_dir / "label_distribution_by_cutoff.csv", index=False, encoding="utf-8-sig")
        feature_null.to_csv(output_dir / "feature_null_report.csv", index=False, encoding="utf-8-sig")

        demand_col = "demand_pattern_type_asof_cutoff"
        _label_rates_by_group(rule_scored, ["cutoff_month", demand_col], horizons).to_csv(
            output_dir / "label_distribution_by_demand_pattern.csv", index=False, encoding="utf-8-sig"
        )
        _label_rates_by_group(rule_scored, ["cutoff_month", "cold_start_flag"], horizons).to_csv(
            output_dir / "label_distribution_by_cold_start.csv", index=False, encoding="utf-8-sig"
        )
        bucketed = rule_scored.copy()
        bucketed["purchase_count_bucket"] = bucketed["purchase_count_asof_cutoff"].map(_purchase_count_bucket)
        bucketed["active_month_count_bucket"] = bucketed["active_month_count_asof_cutoff"].map(_active_month_bucket)
        _label_rates_by_group(bucketed, ["cutoff_month", "purchase_count_bucket"], horizons).to_csv(
            output_dir / "label_distribution_by_purchase_count_bucket.csv", index=False, encoding="utf-8-sig"
        )
        _label_rates_by_group(bucketed, ["cutoff_month", "active_month_count_bucket"], horizons).to_csv(
            output_dir / "label_distribution_by_active_month_bucket.csv", index=False, encoding="utf-8-sig"
        )
        recurring_report = _recurring_subset_report(rule_scored, horizons)
        recurring_report.to_csv(output_dir / "label_distribution_recurring_subset.csv", index=False, encoding="utf-8-sig")

        one_shot_by_cutoff = rule_scored.groupby("cutoff_month", dropna=False).agg(
            entity_count=("one_shot_flag", "size"),
            one_shot_entity_count=("one_shot_flag", "sum"),
            high_value_one_shot_count=("one_shot_high_value_flag", lambda s: int((s & rule_scored.loc[s.index, "one_shot_flag"]).sum())),
            one_shot_high_value_silence_count=("one_shot_high_value_silence_flag", "sum"),
        ).reset_index()
        one_shot_by_cutoff["one_shot_rate"] = one_shot_by_cutoff["one_shot_entity_count"] / one_shot_by_cutoff["entity_count"]
        one_shot_by_cutoff["high_value_one_shot_rate"] = one_shot_by_cutoff["high_value_one_shot_count"] / one_shot_by_cutoff["one_shot_entity_count"].replace(0, pd.NA)
        one_shot_by_cutoff["one_shot_high_value_silence_rate"] = one_shot_by_cutoff["one_shot_high_value_silence_count"] / one_shot_by_cutoff["entity_count"]
        one_shot_by_cutoff.to_csv(output_dir / "one_shot_high_value_silence_by_cutoff.csv", index=False, encoding="utf-8-sig")

        one_shot_by_manufacturer = rule_scored.groupby("manufacturer_code", dropna=False).agg(
            entity_count=("one_shot_flag", "size"),
            one_shot_high_value_silence_count=("one_shot_high_value_silence_flag", "sum"),
            one_shot_business_priority_score_sum=("one_shot_business_priority_score", "sum"),
        ).reset_index()
        one_shot_by_manufacturer["one_shot_high_value_silence_rate"] = (
            one_shot_by_manufacturer["one_shot_high_value_silence_count"] / one_shot_by_manufacturer["entity_count"]
        )
        one_shot_by_manufacturer.sort_values("one_shot_high_value_silence_count", ascending=False).to_csv(
            output_dir / "one_shot_high_value_silence_by_manufacturer.csv", index=False, encoding="utf-8-sig"
        )

        _write_text(output_dir / "one_shot_high_value_silence_report.md", _one_shot_report_markdown(rule_scored))

        model_probability_topk = build_model_probability_topk_placeholder(rule_scored)
        one_shot_attention = build_one_shot_attention_list(rule_scored)
        ranking_metrics, value_metrics = evaluate_rule_baseline_smoke(rule_scored, horizons=horizons)
        ranking_metrics.to_csv(output_dir / "rule_baseline_metrics_by_cutoff.csv", index=False, encoding="utf-8-sig")
        manufacturer_metrics = (
            ranking_metrics.groupby(["manufacturer_code", "horizon", "k"], dropna=False)
            .mean(numeric_only=True)
            .reset_index()
            if not ranking_metrics.empty
            else pd.DataFrame()
        )
        manufacturer_metrics.to_csv(output_dir / "rule_baseline_metrics_by_manufacturer.csv", index=False, encoding="utf-8-sig")
        value_metrics.to_csv(output_dir / "rule_baseline_value_metrics_by_cutoff.csv", index=False, encoding="utf-8-sig")
        _write_text(
            output_dir / "rule_baseline_metric_report.md",
            "\n".join(
                [
                    "# Rule Baseline Metric Report",
                    "",
                    "The rule baseline is a non-probability baseline evaluated on recurring candidates only.",
                    f"- recurring_rows: {len(model_probability_topk)}",
                    f"- one_shot_attention_rows: {len(one_shot_attention)}",
                    "",
                    "## Ranking Metrics Preview",
                    ranking_metrics.head(30).to_markdown(index=False) if not ranking_metrics.empty else "No ranking metrics.",
                    "",
                    "## Value Metrics Preview",
                    value_metrics.head(30).to_markdown(index=False) if not value_metrics.empty else "No value metrics.",
                ]
            ),
        )
        _write_text(
            output_dir / "rule_baseline_topk_review.md",
            "\n".join(
                [
                    "# Rule Baseline TopK Review",
                    "",
                    "No row-level real business details are included here. Use local ignored report/cache artifacts for review if needed.",
                    f"- model_probability_topk_placeholder_rows: {len(model_probability_topk)}",
                    f"- one_shot_high_value_attention_list_rows: {len(one_shot_attention)}",
                    "- model_probability_topk and one_shot_high_value_attention_list are separate outputs.",
                ]
            ),
        )

        _write_text(output_dir / "entity_profile_report.md", build_entity_profile_report(candidate_report, events))
        _write_text(output_dir / "label_distribution_report.md", build_label_distribution_report(labels, horizons=horizons))
        _write_text(output_dir / "demand_pattern_profile.md", _demand_pattern_report(demand_profile))
        _write_text(output_dir / "value_feature_summary.md", _value_feature_summary(features))
        _write_text(
            output_dir / "leakage_guardrail_report.md",
            build_leakage_guardrail_report(list(features.columns), args.include_status_history)
            + "\n"
            + f"- full_history_scope_note: This run uses full model_base history but only evaluates cutoff_months from {args.start_cutoff} to {args.end_cutoff} for local runtime control.",
        )

        timings["total_runtime"] = time.perf_counter() - total_start
        summary = {
            "model_base_rows": int(len(model_base)),
            "purchase_event_rows": int(len(events)),
            "entity_month_rows": int(len(entity_month)),
            "candidate_rows": int(len(candidates)),
            "feature_rows": int(len(features)),
            "cutoff_count": int(len(cutoff_months)),
            "start_cutoff": args.start_cutoff,
            "end_cutoff": args.end_cutoff,
            "purchase_month_min": str(purchase_month_min),
            "purchase_month_max": str(purchase_month_max),
            "max_required_label_month": str(max_required_label_month),
            "label_window_closed": bool(label_window_closed),
            "candidate_policy": candidate_policy,
            "max_monitor_gap_months": max_monitor_gap_months,
            "drug_group_source": drug_group_source,
            "include_status_history": bool(args.include_status_history),
            "output_dir": str(output_dir),
            "cache_intermediate": bool(args.cache_intermediate),
            "refresh_cache": bool(args.refresh_cache),
            "cache_dir": str(cache_dir),
            "cache_hit_count": cache_stats["hit"],
            "cache_miss_count": cache_stats["miss"],
            "cache_written_count": cache_stats["written"],
            "runtime_budget_note": "Suggested local sanity report runtime budget is 20 minutes; first run builds caches, later runs should be faster.",
            "scope_note": f"This run uses full model_base history but only evaluates cutoff_months from {args.start_cutoff} to {args.end_cutoff} for local runtime control.",
            "one_shot_rate": float(rule_scored["one_shot_flag"].mean()),
            "one_shot_high_value_silence_count": int(rule_scored["one_shot_high_value_silence_flag"].sum()),
            "recurring_candidate_rate": float(rule_scored["recurring_candidate"].mean()),
        }
        for name, elapsed in timings.items():
            summary[f"timing_{name}"] = elapsed
        _write_text(output_dir / "sanity_run_summary.md", "# Alive Prediction Sanity Run Summary\n\n" + pd.Series(summary).to_markdown())
        _write_text(
            output_dir / "full_year_sanity_diagnosis.md",
            _full_year_diagnosis(summary, candidate_report, label_by_cutoff, feature_null, demand_profile, rule_scored, recurring_report),
        )

        manifest = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": expected_meta,
            "cache_stats": cache_stats,
            "entries": manifest_entries,
            "timings": timings,
        }
        _write_json(cache_dir / "cache_manifest.json", manifest)

    timings["total_runtime"] = time.perf_counter() - total_start
    for name, elapsed in timings.items():
        summary[f"timing_{name}"] = elapsed
    _write_text(output_dir / "sanity_run_summary.md", "# Alive Prediction Sanity Run Summary\n\n" + pd.Series(summary).to_markdown())
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "metadata": expected_meta,
        "cache_stats": cache_stats,
        "entries": manifest_entries,
        "timings": timings,
    }
    _write_json(cache_dir / "cache_manifest.json", manifest)

    print(
        {
            "model_base_rows": int(len(model_base)),
            "candidate_rows": int(len(candidates)),
            "feature_rows": int(len(features)),
            "output_dir": str(output_dir),
            "cache_hit_count": cache_stats["hit"],
            "cache_miss_count": cache_stats["miss"],
            "cache_written_count": cache_stats["written"],
            "total_runtime": timings["total_runtime"],
        },
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
