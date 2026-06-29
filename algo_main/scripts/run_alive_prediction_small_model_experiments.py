#!/usr/bin/env python
"""Run first-round small-model smoke experiments for alive prediction.

This script trains only temporary in-memory models and writes aggregate reports.
It does not save model files or row-level prediction artifacts.
"""

from __future__ import annotations

import argparse
import fnmatch
import importlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import traceback
from typing import Any

import numpy as np
import pandas as pd
import yaml

from alg.experiments.baseline_rules import (
    add_one_shot_high_value_silence_flags,
    add_recurring_candidate_flag,
)
from alg.facts.demand_profile_builder import build_entity_demand_profile
from alg.facts.entity_month_builder import build_fact_entity_month
from alg.facts.purchase_event_builder import build_fact_purchase_event
from alg.features.alive_prediction_feature_builder import build_alive_prediction_feature_table
from alg.features.cutoff_dataset_builder import build_candidate_entities
from alg.labels.alive_label_builder import build_alive_labels
from alg.metrics.calibration import calibration_curve, probability_metrics
from alg.metrics.ranking import cutoff_topk_metrics
from alg.metrics.value_weighted import cutoff_value_metrics
from alg.artifacts.metadata import build_artifact_metadata, read_metadata, write_metadata
from alg.artifacts.paths import (
    get_alive_labels_path,
    get_fact_entity_month_path,
    get_fact_purchase_event_path,
    get_feature_table_path,
)
from alg.utils.months import to_month_end


KEY_COLS = ["manufacturer_code", "hospital_code", "drug_group", "cutoff_month"]
FORBIDDEN_SUBSTRINGS = ("raw", "name", "audit")
INTERVAL_COLUMNS = [
    "median_purchase_interval_days_asof_cutoff",
    "mean_purchase_interval_days_asof_cutoff",
    "std_purchase_interval_days_asof_cutoff",
    "purchase_interval_iqr_asof_cutoff",
]
RESERVED_FEATURES = ["seasonality_strength_asof_cutoff", "burstiness_score_asof_cutoff"]
NUMERIC_CANDIDATES = [
    "months_since_last_purchase_asof_cutoff",
    "months_since_first_purchase_asof_cutoff",
    "entity_age_months_asof_cutoff",
    "purchase_count_asof_cutoff",
    "active_month_count_asof_cutoff",
    "months_observed_asof_cutoff",
    "active_month_ratio_asof_cutoff",
    "order_count_last_3m_asof_cutoff",
    "order_count_last_6m_asof_cutoff",
    "order_count_last_12m_asof_cutoff",
    "purchase_quantity_sum_last_3m_asof_cutoff",
    "purchase_quantity_sum_last_6m_asof_cutoff",
    "purchase_quantity_sum_last_12m_asof_cutoff",
    "purchase_amount_sum_last_3m_asof_cutoff",
    "purchase_amount_sum_last_6m_asof_cutoff",
    "purchase_amount_sum_last_12m_asof_cutoff",
    "purchase_quantity_avg_last_3m_asof_cutoff",
    "purchase_quantity_avg_last_6m_asof_cutoff",
    "purchase_quantity_avg_last_12m_asof_cutoff",
    "purchase_amount_avg_last_3m_asof_cutoff",
    "purchase_amount_avg_last_6m_asof_cutoff",
    "purchase_amount_avg_last_12m_asof_cutoff",
    "median_purchase_interval_days_asof_cutoff",
    "mean_purchase_interval_days_asof_cutoff",
    "std_purchase_interval_days_asof_cutoff",
    "purchase_interval_iqr_asof_cutoff",
    "median_purchase_interval_days_missing_flag",
    "mean_purchase_interval_days_missing_flag",
    "std_purchase_interval_days_missing_flag",
    "purchase_interval_iqr_missing_flag",
    "cold_start_flag",
    "adi_asof_cutoff",
    "cv2_quantity_asof_cutoff",
    "historical_avg_monthly_amount_asof_cutoff",
    "historical_avg_monthly_quantity_asof_cutoff",
    "value_at_risk_amount_nonnegative_H3_asof_cutoff",
    "value_at_risk_amount_nonnegative_H6_asof_cutoff",
    "value_at_risk_amount_nonnegative_H12_asof_cutoff",
    "value_at_risk_quantity_nonnegative_H3_asof_cutoff",
    "value_at_risk_quantity_nonnegative_H6_asof_cutoff",
    "value_at_risk_quantity_nonnegative_H12_asof_cutoff",
]


def check_optional_dependency(module_name: str) -> dict[str, Any]:
    try:
        module = importlib.import_module(module_name)
        return {
            "ok": True,
            "module": module_name,
            "version": getattr(module, "__version__", None),
            "error": "",
            "traceback": "",
        }
    except Exception as exc:  # pragma: no cover - traceback content is environment-specific
        return {
            "ok": False,
            "module": module_name,
            "version": None,
            "error": repr(exc),
            "traceback": traceback.format_exc(),
        }


def import_class(class_path: str):
    module_name, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def collect_environment_diagnostics() -> dict[str, Any]:
    lightgbm_check = check_optional_dependency("lightgbm")
    catboost_check = check_optional_dependency("catboost")
    xgboost_check = check_optional_dependency("xgboost")
    sklearn_check = check_optional_dependency("sklearn")
    diagnostics = {
        "sys_executable": sys.executable,
        "sys_version": sys.version,
        "os_getcwd": os.getcwd(),
        "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
        "pythonpath_used_by_script": sys.path,
        "pip_executable": shutil.which("pip") or "",
        "import_check_lightgbm": lightgbm_check["ok"],
        "lightgbm_version": lightgbm_check["version"],
        "lightgbm_import_error": lightgbm_check["error"],
        "lightgbm_import_error_full_traceback": lightgbm_check["traceback"],
        "import_check_catboost": catboost_check["ok"],
        "catboost_version": catboost_check["version"],
        "catboost_import_error": catboost_check["error"],
        "catboost_import_error_full_traceback": catboost_check["traceback"],
        "xgboost_import_check": xgboost_check["ok"],
        "xgboost_version": xgboost_check["version"],
        "xgboost_import_error": xgboost_check["error"],
        "xgboost_import_error_full_traceback": xgboost_check["traceback"],
        "import_check_sklearn": sklearn_check["ok"],
        "sklearn_version": sklearn_check["version"],
        "sklearn_import_error": sklearn_check["error"],
        "sklearn_import_error_full_traceback": sklearn_check["traceback"],
        "pandas_version": pd.__version__,
        "numpy_version": np.__version__,
    }
    print(f"[env] sys.executable={diagnostics['sys_executable']}", flush=True)
    print(
        f"[env] lightgbm import {'ok' if lightgbm_check['ok'] else 'failed'}"
        + (f" version={lightgbm_check['version']}" if lightgbm_check["ok"] else ""),
        flush=True,
    )
    print(
        f"[env] catboost import {'ok' if catboost_check['ok'] else 'failed'}"
        + (f" version={catboost_check['version']}" if catboost_check["ok"] else ""),
        flush=True,
    )
    print(
        f"[env] xgboost import {'ok' if xgboost_check['ok'] else 'failed'}"
        + (f" version={xgboost_check['version']}" if xgboost_check["ok"] else ""),
        flush=True,
    )
    return diagnostics


def write_environment_diagnostics(output_dir: Path, diagnostics: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "environment_diagnostics.json").write_text(
        json.dumps(diagnostics, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    lines = ["# Environment Diagnostics", ""]
    for key, value in diagnostics.items():
        if key.endswith("_full_traceback") and value:
            lines.extend([f"## {key}", "", "```text", str(value).rstrip(), "```", ""])
        elif key != "pythonpath_used_by_script":
            lines.append(f"- {key}: {value}")
    lines.extend(["", "## pythonpath_used_by_script", "", "```text"])
    lines.extend(map(str, diagnostics.get("pythonpath_used_by_script", [])))
    lines.extend(["```", ""])
    (output_dir / "environment_diagnostics.md").write_text("\n".join(lines), encoding="utf-8")


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def month_ends(start: str, end: str) -> list[pd.Timestamp]:
    return [period.to_timestamp("M") for period in pd.period_range(start=start, end=end, freq="M")]


def cache_name(
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


def cache_paths(config: dict[str, Any], split: dict[str, str], include_status_history: bool) -> dict[str, Path]:
    root = project_root()
    cache_dir = root / config["input"]["cache_dir"]
    horizons = tuple(config["horizons_months"])
    kwargs = {
        "drug_group_source": config["entity"]["drug_group_source"],
        "start_cutoff": split["train_cutoff_start"],
        "end_cutoff": split["test_cutoff_end"],
        "candidate_policy": config["candidate_policy"]["default"],
        "max_monitor_gap_months": int(config["candidate_policy"]["max_monitor_gap_months"]),
        "horizons": horizons,
        "include_status_history": include_status_history,
    }
    return {
        "features": cache_dir / cache_name("alive_prediction_features", **kwargs),
        "labels": cache_dir / cache_name("alive_labels", **kwargs),
    }


def stable_feature_label_paths(
    config: dict[str, Any],
    split: dict[str, str],
    include_status_history: bool,
) -> dict[str, Path]:
    root = project_root()
    kwargs = {
        "root": root / "data",
        "drug_group_source": config["entity"]["drug_group_source"],
        "candidate_policy": config["candidate_policy"]["default"],
        "max_monitor_gap_months": int(config["candidate_policy"]["max_monitor_gap_months"]),
        "start_cutoff": split["train_cutoff_start"],
        "end_cutoff": split["test_cutoff_end"],
    }
    return {
        "features": get_feature_table_path(**kwargs, include_status_history=include_status_history),
        "labels": get_alive_labels_path(**kwargs, horizons=tuple(config["horizons_months"])),
    }


def artifact_has_metadata(path: Path) -> bool:
    return path.exists() and bool(read_metadata(path))


def build_or_load_feature_label_table(
    config: dict[str, Any],
    split: dict[str, str],
    *,
    refresh_cache: bool = False,
    include_status_history: bool = False,
) -> pd.DataFrame:
    """Read cached feature/label tables or build them from local model_base."""

    stable_paths = stable_feature_label_paths(config, split, include_status_history)
    if (
        config["input"].get("reuse_cached_features", True)
        and not refresh_cache
        and stable_paths["features"].exists()
        and stable_paths["labels"].exists()
    ):
        print(f"[artifact exists] feature_table={stable_paths['features']}", flush=True)
        print(f"[artifact exists] alive_labels={stable_paths['labels']}", flush=True)
        features = pd.read_parquet(stable_paths["features"])
        labels = pd.read_parquet(stable_paths["labels"])
        return join_features_labels(features, labels)

    legacy_paths = cache_paths(config, split, include_status_history)
    if (
        config["input"].get("reuse_cached_features", True)
        and not refresh_cache
        and legacy_paths["features"].exists()
        and legacy_paths["labels"].exists()
    ):
        print(f"[exploration_cache_mode] features={legacy_paths['features']}", flush=True)
        print(f"[exploration_cache_mode] labels={legacy_paths['labels']}", flush=True)
        features = pd.read_parquet(legacy_paths["features"])
        labels = pd.read_parquet(legacy_paths["labels"])
        return join_features_labels(features, labels)

    root = project_root()
    feature_config = read_yaml(root / "configs/features/alive_prediction_feature_view.yaml")
    cutoff_months = month_ends(split["train_cutoff_start"], split["test_cutoff_end"])
    horizons = tuple(config["horizons_months"])
    events, entity_month = load_or_build_base_facts(config)
    candidates, _ = build_candidate_entities(
        events,
        cutoff_months=cutoff_months,
        policy=config["candidate_policy"]["default"],
        max_monitor_gap_months=int(config["candidate_policy"]["max_monitor_gap_months"]),
    )
    demand_profile = build_entity_demand_profile(
        entity_month,
        cutoff_months=cutoff_months,
        cold_start=feature_config["cold_start"],
    )
    labels = build_alive_labels(events, candidates, horizons=horizons)
    features = build_alive_prediction_feature_table(
        entity_month,
        candidates,
        demand_profile=demand_profile,
        include_status_history=include_status_history,
        horizons=horizons,
    )
    stable_paths["features"].parent.mkdir(parents=True, exist_ok=True)
    features.to_parquet(stable_paths["features"], index=False)
    labels.to_parquet(stable_paths["labels"], index=False)
    write_metadata(
        stable_paths["features"],
        build_artifact_metadata(artifact_name="feature_table", artifact_type="features", df=features),
    )
    write_metadata(
        stable_paths["labels"],
        build_artifact_metadata(artifact_name="alive_labels", artifact_type="features", df=labels),
    )
    return join_features_labels(features, labels)


def _latest_matching_cache(cache_dir: Path, pattern: str) -> Path | None:
    matches = sorted(cache_dir.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def load_or_build_base_facts(config: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Use local model_base when available; otherwise reuse existing fact caches."""

    root = project_root()
    drug_group_source = config["entity"]["drug_group_source"]
    stable_event_path = get_fact_purchase_event_path(root=root / "data", drug_group_source=drug_group_source)
    stable_entity_month_path = get_fact_entity_month_path(root=root / "data", drug_group_source=drug_group_source)
    if stable_event_path.exists() and stable_entity_month_path.exists():
        print(f"[artifact exists] fact_purchase_event={stable_event_path}", flush=True)
        print(f"[artifact exists] fact_entity_month={stable_entity_month_path}", flush=True)
        return pd.read_parquet(stable_event_path), pd.read_parquet(stable_entity_month_path)

    model_base_path = root / config["input"]["model_base_path"]
    if model_base_path.exists():
        model_base = pd.read_parquet(model_base_path)
        events = build_fact_purchase_event(model_base, drug_group_source=drug_group_source)
        entity_month = build_fact_entity_month(events)
        stable_event_path.parent.mkdir(parents=True, exist_ok=True)
        if not stable_event_path.exists():
            events.to_parquet(stable_event_path, index=False)
            write_metadata(
                stable_event_path,
                build_artifact_metadata(artifact_name="fact_purchase_event", artifact_type="facts", df=events),
            )
        if not stable_entity_month_path.exists():
            entity_month.to_parquet(stable_entity_month_path, index=False)
            write_metadata(
                stable_entity_month_path,
                build_artifact_metadata(artifact_name="fact_entity_month", artifact_type="facts", df=entity_month),
            )
        return events, entity_month

    cache_dir = root / config["input"]["cache_dir"]
    event_path = _latest_matching_cache(cache_dir, f"fact_purchase_event__{drug_group_source}__*.parquet")
    entity_month_path = _latest_matching_cache(cache_dir, f"fact_entity_month__{drug_group_source}__*.parquet")
    if event_path is None or entity_month_path is None:
        raise FileNotFoundError(
            "Missing model_base parquet and no reusable fact caches found. "
            f"Expected model_base at {model_base_path} or fact caches under {cache_dir}."
        )
    print(
        {
            "model_base_missing": str(model_base_path),
            "using_cached_fact_purchase_event": str(event_path),
            "using_cached_fact_entity_month": str(entity_month_path),
        },
        flush=True,
    )
    return pd.read_parquet(event_path), pd.read_parquet(entity_month_path)


def join_features_labels(features: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    label_cols = KEY_COLS + [column for column in labels.columns if column.startswith("label_")]
    out = features.copy()
    out["cutoff_month"] = to_month_end(out["cutoff_month"])
    labels_small = labels[label_cols].copy()
    labels_small["cutoff_month"] = to_month_end(labels_small["cutoff_month"])
    return out.merge(labels_small, on=KEY_COLS, how="left")


def add_scope_flags(df: pd.DataFrame, config: dict[str, Any], rule_config: dict[str, Any] | None = None) -> pd.DataFrame:
    rule_config = rule_config or {"one_shot_high_value_silence": {}}
    if "recurring_candidate_flag" in df.columns:
        out = df.copy()
    else:
        out = add_recurring_candidate_flag(
            df,
            min_purchase_count_asof_cutoff=int(config["recurring_definition"]["min_purchase_count_asof_cutoff"]),
            min_active_month_count_asof_cutoff=int(config["recurring_definition"]["min_active_month_count_asof_cutoff"]),
        ).rename(columns={"recurring_candidate": "recurring_candidate_flag"})
    out["all_monitorable_flag"] = True
    if "one_shot_flag" not in out.columns:
        out["one_shot_flag"] = out["purchase_count_asof_cutoff"] == 1
    cfg = rule_config.get("one_shot_high_value_silence", {})
    if cfg:
        out = add_one_shot_high_value_silence_flags(out, cfg)
    else:
        if "one_shot_high_value_silence_flag" not in out.columns:
            out["one_shot_high_value_silence_flag"] = False
        if "one_shot_business_attention_flag" not in out.columns:
            out["one_shot_business_attention_flag"] = out["one_shot_high_value_silence_flag"]
        if "one_shot_business_priority_score" not in out.columns:
            out["one_shot_business_priority_score"] = 0.0
    return out


def split_scopes(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "all_monitorable": df.copy(),
        "recurring_only": df[df["recurring_candidate_flag"]].copy(),
        "one_shot_only": df[df["one_shot_flag"]].copy(),
    }


def assert_temporal_split_valid(split: dict[str, str]) -> None:
    train_start = pd.Period(split["train_cutoff_start"], freq="M")
    train_end = pd.Period(split["train_cutoff_end"], freq="M")
    test_start = pd.Period(split["test_cutoff_start"], freq="M")
    test_end = pd.Period(split["test_cutoff_end"], freq="M")
    if train_start > train_end or test_start > test_end:
        raise ValueError("Invalid split range: start must be <= end")
    if train_end >= test_start:
        raise ValueError("Train/test cutoff ranges must not overlap")
    if test_start <= train_end:
        raise ValueError("Test cutoff must be later than train cutoff")
    if "purge_cutoff_start" in split and "purge_cutoff_end" in split:
        purge_start = pd.Period(split["purge_cutoff_start"], freq="M")
        purge_end = pd.Period(split["purge_cutoff_end"], freq="M")
        if not (train_end < purge_start <= purge_end < test_start):
            raise ValueError("Purge gap must sit strictly between train and test cutoffs")


def cutoff_mask(df: pd.DataFrame, start: str, end: str) -> pd.Series:
    months = pd.to_datetime(df["cutoff_month"]).dt.to_period("M")
    return (months >= pd.Period(start, freq="M")) & (months <= pd.Period(end, freq="M"))


def available_cutoff_periods(df: pd.DataFrame) -> set[pd.Period]:
    return set(pd.to_datetime(df["cutoff_month"]).dt.to_period("M").dropna().unique())


def required_cutoff_periods(start: str, end: str) -> set[pd.Period]:
    return set(pd.period_range(start=start, end=end, freq="M"))


def build_trainability_report(
    df: pd.DataFrame,
    config: dict[str, Any],
    split: dict[str, str],
    horizons: list[int],
) -> pd.DataFrame:
    assert_temporal_split_valid(split)
    if "recurring_candidate_flag" not in df.columns:
        df = add_scope_flags(df, config, {"one_shot_high_value_silence": {}})
    if "one_shot_high_value_silence_flag" not in df.columns:
        df = df.copy()
        df["one_shot_high_value_silence_flag"] = False
    available = available_cutoff_periods(df)
    required_train = required_cutoff_periods(split["train_cutoff_start"], split["train_cutoff_end"])
    required_test = required_cutoff_periods(split["test_cutoff_start"], split["test_cutoff_end"])
    missing_train = sorted(required_train - available)
    missing_test = sorted(required_test - available)
    gate = config["trainability_gate"]
    rows = []
    for horizon in horizons:
        label_col = f"label_die_H{horizon}"
        train_df = df[cutoff_mask(df, split["train_cutoff_start"], split["train_cutoff_end"]) & df["recurring_candidate_flag"]]
        train_df = train_df[~train_df["one_shot_high_value_silence_flag"]]
        test_df = df[cutoff_mask(df, split["test_cutoff_start"], split["test_cutoff_end"]) & df["recurring_candidate_flag"]]
        row = {
            "horizon": horizon,
            "train_cutoff_start": split["train_cutoff_start"],
            "train_cutoff_end": split["train_cutoff_end"],
            "test_cutoff_start": split["test_cutoff_start"],
            "test_cutoff_end": split["test_cutoff_end"],
            "train_row_count": int(len(train_df)),
            "test_row_count": int(len(test_df)),
            "train_positive_count": int(train_df[label_col].sum()) if label_col in train_df else 0,
            "train_negative_count": int((1 - train_df[label_col]).sum()) if label_col in train_df else 0,
            "test_positive_count": int(test_df[label_col].sum()) if label_col in test_df else 0,
            "test_negative_count": int((1 - test_df[label_col]).sum()) if label_col in test_df else 0,
            "train_cutoff_count": int(train_df["cutoff_month"].nunique()) if len(train_df) else 0,
            "test_cutoff_count": int(test_df["cutoff_month"].nunique()) if len(test_df) else 0,
            "train_entity_count": int(train_df[["manufacturer_code", "hospital_code", "drug_group"]].drop_duplicates().shape[0]) if len(train_df) else 0,
            "test_entity_count": int(test_df[["manufacturer_code", "hospital_code", "drug_group"]].drop_duplicates().shape[0]) if len(test_df) else 0,
            "train_manufacturer_count": int(train_df["manufacturer_code"].nunique()) if len(train_df) else 0,
            "test_manufacturer_count": int(test_df["manufacturer_code"].nunique()) if len(test_df) else 0,
        }
        row["train_positive_rate"] = row["train_positive_count"] / row["train_row_count"] if row["train_row_count"] else np.nan
        row["test_positive_rate"] = row["test_positive_count"] / row["test_row_count"] if row["test_row_count"] else np.nan
        skip_reasons = []
        if missing_train:
            skip_reasons.append("missing_feature_table_for_train_cutoffs")
        if missing_test:
            skip_reasons.append("missing_feature_table_for_test_cutoffs")
        if label_col not in df.columns:
            skip_reasons.append("missing_label_column")
        if row["train_row_count"] < gate["train_row_count_min"]:
            skip_reasons.append("insufficient_train_row_count")
        if row["test_row_count"] < gate["test_row_count_min"]:
            skip_reasons.append("insufficient_test_row_count")
        if row["train_positive_count"] < gate["train_positive_count_min"]:
            skip_reasons.append("insufficient_train_positive_count")
        if row["train_negative_count"] < gate["train_negative_count_min"]:
            skip_reasons.append("insufficient_train_negative_count")
        if row["test_positive_count"] < gate["test_positive_count_min"]:
            skip_reasons.append("insufficient_test_positive_count")
        if row["test_negative_count"] < gate["test_negative_count_min"]:
            skip_reasons.append("insufficient_test_negative_count")
        if row["train_cutoff_count"] < gate["train_cutoff_count_min"]:
            skip_reasons.append("insufficient_train_cutoff_count")
        if row["test_cutoff_count"] < gate["test_cutoff_count_min"]:
            skip_reasons.append("insufficient_test_cutoff_count")
        if row["train_manufacturer_count"] < gate["train_manufacturer_count_min"]:
            skip_reasons.append("insufficient_train_manufacturer_count")
        if row["test_manufacturer_count"] < gate["test_manufacturer_count_min"]:
            skip_reasons.append("insufficient_test_manufacturer_count")
        if label_col in df.columns and (
            row["train_positive_count"] == 0
            or row["train_negative_count"] == 0
            or row["test_positive_count"] == 0
            or row["test_negative_count"] == 0
        ):
            skip_reasons.append("label_has_single_class")
        row["can_train"] = not skip_reasons
        row["skip_reason"] = ";".join(dict.fromkeys(skip_reasons))
        rows.append(row)
    return pd.DataFrame(rows)


def add_missing_flags(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for column in INTERVAL_COLUMNS:
        if column in out.columns:
            out[f"{column.removesuffix('_asof_cutoff')}_missing_flag"] = out[column].isna().astype(int)
    return out


def is_forbidden_column(column: str, config: dict[str, Any]) -> bool:
    if column in config["features"].get("exclude_columns", []):
        return True
    for pattern in config["features"].get("exclude_columns_patterns", []):
        if fnmatch.fnmatch(column, pattern):
            return True
    lower = column.lower()
    if any(token in lower for token in FORBIDDEN_SUBSTRINGS):
        return True
    if column in KEY_COLS or column.endswith("_month") or column.endswith("_time"):
        return True
    return False


def select_feature_columns(
    df: pd.DataFrame,
    config: dict[str, Any],
    model_name: str,
) -> tuple[list[str], list[str], list[str]]:
    df = add_missing_flags(df)
    missing_or_reserved = []
    numeric_cols = []
    for column in NUMERIC_CANDIDATES:
        if column not in df.columns:
            missing_or_reserved.append(column)
            continue
        if column in RESERVED_FEATURES and df[column].isna().all():
            missing_or_reserved.append(f"{column}:reserved_feature_not_used")
            continue
        if not is_forbidden_column(column, config):
            numeric_cols.append(column)
    categorical_candidates = config["features"]["low_cardinality_categorical_for_logistic"]
    if model_name != "logistic_regression" and config["features"].get("tree_use_high_cardinality", True):
        categorical_candidates = categorical_candidates + config["features"].get("high_cardinality_categorical", [])
    categorical_cols = [
        column
        for column in categorical_candidates
        if column in df.columns and not is_forbidden_column(column, config)
    ]
    assert_no_forbidden_columns(numeric_cols + categorical_cols, config)
    return numeric_cols, categorical_cols, missing_or_reserved


def assert_no_forbidden_columns(columns: list[str], config: dict[str, Any]) -> None:
    offenders = [column for column in columns if is_forbidden_column(column, config)]
    if offenders:
        raise ValueError(f"Forbidden columns selected for X: {offenders}")


def _failure(status: str, reason: str, exc: Exception | None = None) -> dict[str, str]:
    return {
        "status": status,
        "reason": reason,
        "traceback": traceback.format_exc() if exc is not None else "",
    }


def build_sklearn_estimator(model_name: str, config: dict[str, Any], numeric_cols: list[str], categorical_cols: list[str]):
    try:
        from sklearn.compose import ColumnTransformer
        from sklearn.impute import SimpleImputer
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler
    except Exception as exc:
        return None, _failure("skipped_optional_dependency", "dependency_not_installed:sklearn", exc)

    if model_name == "logistic_regression":
        try:
            LogisticRegression = import_class(config["models"][model_name]["class_path"])
        except Exception as exc:
            return None, _failure("class_import_failed", config["models"][model_name]["class_path"], exc)
        try:
            onehot = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        except TypeError:
            onehot = OneHotEncoder(handle_unknown="ignore", sparse=False)
        try:
            preprocessor = ColumnTransformer(
                transformers=[
                    ("numeric", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]), numeric_cols),
                    ("categorical", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("onehot", onehot)]), categorical_cols),
                ],
                remainder="drop",
            )
            estimator = LogisticRegression(**config["models"][model_name]["params"])
        except Exception as exc:
            return None, _failure("model_init_failed", model_name, exc)
        return Pipeline([("preprocess", preprocessor), ("model", estimator)]), ""

    tree_dependency_by_model = {
        "lightgbm_small": "lightgbm",
        "xgboost_small": "xgboost",
    }
    if model_name in tree_dependency_by_model:
        dependency_name = tree_dependency_by_model[model_name]
        dependency = check_optional_dependency(dependency_name)
        if not dependency["ok"]:
            return None, {
                "status": "skipped_optional_dependency",
                "reason": f"dependency_not_installed:{dependency_name}",
                "traceback": dependency["traceback"],
            }
        try:
            EstimatorClass = import_class(config["models"][model_name]["class_path"])
        except Exception as exc:
            return None, _failure("class_import_failed", config["models"][model_name]["class_path"], exc)

        try:
            preprocessor = ColumnTransformer(
                transformers=[
                    ("numeric", SimpleImputer(strategy="median"), numeric_cols),
                    (
                        "categorical",
                        Pipeline(
                            [
                                ("imputer", SimpleImputer(strategy="most_frequent")),
                                ("ordinal", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)),
                            ]
                        ),
                        categorical_cols,
                    ),
                ],
                remainder="drop",
            )
            estimator = EstimatorClass(**config["models"][model_name]["params"])
        except Exception as exc:
            return None, _failure("model_init_failed", model_name, exc)
        return Pipeline([("preprocess", preprocessor), ("model", estimator)]), ""

    return None, _failure("unsupported_categorical_handling", f"unsupported_sklearn_model:{model_name}")


def fit_predict_model(
    model_name: str,
    train_df: pd.DataFrame,
    eval_df: pd.DataFrame,
    label_col: str,
    config: dict[str, Any],
) -> tuple[np.ndarray | None, str, list[str], list[str], list[str]]:
    train_df = add_missing_flags(train_df)
    eval_df = add_missing_flags(eval_df)
    numeric_cols, categorical_cols, missing_features = select_feature_columns(train_df, config, model_name)
    feature_cols = numeric_cols + categorical_cols
    assert_no_forbidden_columns(feature_cols, config)
    if train_df[label_col].nunique(dropna=False) < 2 or eval_df[label_col].nunique(dropna=False) < 2:
        return None, "label_has_single_class", numeric_cols, categorical_cols, missing_features
    if model_name == "catboost_small":
        if importlib.util.find_spec("catboost") is None:
            return None, "skipped_optional_dependency:catboost", numeric_cols, categorical_cols, missing_features
        from catboost import CatBoostClassifier

        train_x = train_df[feature_cols].copy()
        eval_x = eval_df[feature_cols].copy()
        for column in numeric_cols:
            median = train_x[column].median()
            train_x[column] = train_x[column].fillna(median)
            eval_x[column] = eval_x[column].fillna(median)
        for column in categorical_cols:
            train_x[column] = train_x[column].astype("string").fillna("__MISSING__")
            eval_x[column] = eval_x[column].astype("string").fillna("__MISSING__")
        model = CatBoostClassifier(**config["models"][model_name]["params"])
        cat_features = [train_x.columns.get_loc(column) for column in categorical_cols]
        model.fit(train_x, train_df[label_col], cat_features=cat_features)
        return model.predict_proba(eval_x)[:, 1], "", numeric_cols, categorical_cols, missing_features

    estimator, skip_reason = build_sklearn_estimator(model_name, config, numeric_cols, categorical_cols)
    if estimator is None:
        return None, skip_reason["reason"], numeric_cols, categorical_cols, missing_features
    try:
        estimator.fit(train_df[feature_cols], train_df[label_col])
    except Exception:
        return None, "model_fit_failed", numeric_cols, categorical_cols, missing_features
    try:
        return estimator.predict_proba(eval_df[feature_cols])[:, 1], "", numeric_cols, categorical_cols, missing_features
    except Exception:
        return None, "model_predict_failed", numeric_cols, categorical_cols, missing_features


def fit_model_in_memory(
    model_name: str,
    train_df: pd.DataFrame,
    label_col: str,
    config: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, str] | str]:
    """Fit one temporary model on train only and return predict metadata."""

    train_df = add_missing_flags(train_df)
    numeric_cols, categorical_cols, missing_features = select_feature_columns(train_df, config, model_name)
    feature_cols = numeric_cols + categorical_cols
    assert_no_forbidden_columns(feature_cols, config)
    if train_df[label_col].nunique(dropna=False) < 2:
        return None, _failure("trainability_gate_failed", "label_has_single_class")
    if model_name == "catboost_small":
        dependency = check_optional_dependency("catboost")
        if not dependency["ok"]:
            return None, {
                "status": "skipped_optional_dependency",
                "reason": "dependency_not_installed:catboost",
                "traceback": dependency["traceback"],
            }
        try:
            CatBoostClassifier = import_class(config["models"][model_name]["class_path"])
        except Exception as exc:
            return None, _failure("class_import_failed", config["models"][model_name]["class_path"], exc)

        train_x = train_df[feature_cols].copy()
        medians = {}
        for column in numeric_cols:
            medians[column] = train_x[column].median()
            train_x[column] = train_x[column].fillna(medians[column])
        for column in categorical_cols:
            train_x[column] = train_x[column].astype("string").fillna("__MISSING__")
        try:
            params = dict(config["models"][model_name]["params"])
            params["allow_writing_files"] = False
            model = CatBoostClassifier(**params)
        except Exception as exc:
            return None, _failure("model_init_failed", model_name, exc)
        cat_features = [train_x.columns.get_loc(column) for column in categorical_cols]
        try:
            model.fit(train_x, train_df[label_col], cat_features=cat_features)
        except Exception as exc:
            return None, _failure("model_fit_failed", model_name, exc)
        return {
            "kind": "catboost",
            "model": model,
            "feature_cols": feature_cols,
            "numeric_cols": numeric_cols,
            "categorical_cols": categorical_cols,
            "missing_or_reserved_features": missing_features,
            "medians": medians,
        }, ""
    estimator, skip_reason = build_sklearn_estimator(model_name, config, numeric_cols, categorical_cols)
    if estimator is None:
        return None, skip_reason
    try:
        estimator.fit(train_df[feature_cols], train_df[label_col])
    except Exception as exc:
        return None, _failure("model_fit_failed", model_name, exc)
    return {
        "kind": "sklearn",
        "model": estimator,
        "feature_cols": feature_cols,
        "numeric_cols": numeric_cols,
        "categorical_cols": categorical_cols,
        "missing_or_reserved_features": missing_features,
    }, ""


def predict_with_fitted_model(fitted: dict[str, Any], eval_df: pd.DataFrame) -> np.ndarray:
    eval_df = add_missing_flags(eval_df)
    feature_cols = fitted["feature_cols"]
    if fitted["kind"] == "catboost":
        eval_x = eval_df[feature_cols].copy()
        for column in fitted["numeric_cols"]:
            eval_x[column] = eval_x[column].fillna(fitted["medians"].get(column))
        for column in fitted["categorical_cols"]:
            eval_x[column] = eval_x[column].astype("string").fillna("__MISSING__")
        return fitted["model"].predict_proba(eval_x)[:, 1]
    return fitted["model"].predict_proba(eval_df[feature_cols])[:, 1]


def metric_group_coverage(
    df: pd.DataFrame,
    label_col: str,
    horizon: int,
    scope: str,
    group_cols: list[str],
    min_group_rows: int,
) -> pd.DataFrame:
    rows = []
    for group_key, group in df.groupby(group_cols, dropna=False):
        if len(group_cols) == 1:
            group_key = (group_key,)
        positive = int(group[label_col].sum()) if label_col in group else 0
        negative = int(len(group) - positive)
        skip_reason = ""
        eligible = True
        if len(group) < min_group_rows:
            eligible = False
            skip_reason = "skipped_small_group"
        elif positive == 0:
            eligible = False
            skip_reason = "skipped_no_positive"
        rows.append(
            {
                **dict(zip(group_cols, group_key)),
                "horizon": horizon,
                "scope": scope,
                "row_count": int(len(group)),
                "positive_count": positive,
                "negative_count": negative,
                "eligible_for_topk": eligible,
                "skip_reason": skip_reason,
            }
        )
    return pd.DataFrame(rows)


def evaluate_predictions(
    df: pd.DataFrame,
    label_col: str,
    probability_col: str,
    value_col: str,
    horizon: int,
    model_name: str,
    scope: str,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    priority_col = f"business_priority_score_H{horizon}"
    scored = df.copy()
    scored[priority_col] = scored[probability_col] * scored[value_col].fillna(0).clip(lower=0)
    group_cols = config["metrics"]["ranking_group"]
    coverage = metric_group_coverage(
        scored,
        label_col,
        horizon,
        scope,
        group_cols,
        int(config["metrics"].get("min_group_rows_for_topk", 5)),
    )
    eligible_keys = coverage[coverage["eligible_for_topk"]][group_cols]
    if eligible_keys.empty:
        eligible = scored.iloc[0:0].copy()
    else:
        eligible = scored.merge(eligible_keys.drop_duplicates(), on=group_cols, how="inner")
    prob = probability_metrics(scored[label_col], scored[probability_col])
    prob_row = {
        "model": model_name,
        "horizon": horizon,
        "scope": scope,
        "row_count": int(len(scored)),
        "positive_rate": float(scored[label_col].mean()) if len(scored) else np.nan,
        **prob,
    }
    if eligible.empty:
        ranking = pd.DataFrame()
        value_metrics = pd.DataFrame()
    else:
        ranking = cutoff_topk_metrics(
            eligible,
            label_col=label_col,
            score_col=probability_col,
            k_values=config["metrics"]["k_values"],
            group_cols=tuple(group_cols),
        )
        ranking["model"] = model_name
        ranking["horizon"] = horizon
        ranking["scope"] = scope
        value_metrics = cutoff_value_metrics(
            eligible,
            label_col=label_col,
            probability_col=probability_col,
            priority_col=priority_col,
            value_col=value_col,
            k_values=config["metrics"]["k_values"],
            group_cols=tuple(group_cols),
        )
        value_metrics["model"] = model_name
        value_metrics["horizon"] = horizon
        value_metrics["scope"] = scope
    bins = calibration_curve(scored[label_col], scored[probability_col])
    bins["model"] = model_name
    bins["horizon"] = horizon
    bins["scope"] = scope
    return pd.DataFrame([prob_row]), ranking, value_metrics, bins


def aggregate_metric_tables(ranking: pd.DataFrame, value_metrics: pd.DataFrame, probability: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if ranking.empty:
        ranking_scope = pd.DataFrame()
        ranking_cutoff = pd.DataFrame()
        ranking_manufacturer = pd.DataFrame()
    else:
        ranking_scope = ranking.groupby(["model", "horizon", "scope", "k"], dropna=False).mean(numeric_only=True).reset_index()
        ranking_cutoff = ranking.groupby(["model", "horizon", "scope", "cutoff_month", "k"], dropna=False).mean(numeric_only=True).reset_index()
        ranking_manufacturer = ranking.groupby(["model", "horizon", "scope", "manufacturer_code", "k"], dropna=False).mean(numeric_only=True).reset_index()
    if not value_metrics.empty:
        value_scope = value_metrics.groupby(["model", "horizon", "scope", "k"], dropna=False).mean(numeric_only=True).reset_index()
        ranking_scope = ranking_scope.merge(
            value_scope,
            on=["model", "horizon", "scope", "k"],
            how="outer",
            suffixes=("", "_value"),
        )
    if not probability.empty:
        ranking_scope = ranking_scope.merge(probability, on=["model", "horizon", "scope"], how="outer")
    return ranking_cutoff, ranking_manufacturer, ranking_scope


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def dataframe_to_markdown(df: pd.DataFrame, *, index: bool = False) -> str:
    try:
        return df.to_markdown(index=index)
    except ImportError:
        return "```csv\n" + df.to_csv(index=index).rstrip() + "\n```"


def trainability_markdown(report: pd.DataFrame, split_note: str, model_status: list[dict[str, Any]]) -> str:
    lines = [
        "# Trainability Report",
        "",
        f"- split_note: {split_note}",
        "- primary_train_scope: recurring_only",
        "- one_shot_only_excluded_from_probability_training: True",
        "",
        "## Horizon Gate",
        dataframe_to_markdown(report, index=False),
        "",
        "## Model Status",
        dataframe_to_markdown(pd.DataFrame(model_status), index=False) if model_status else "No model was attempted.",
    ]
    can_any = bool(report["can_train"].any()) if not report.empty else False
    lines.extend(
        [
            "",
            f"- can_enter_logistic_regression: {can_any}",
            "- can_enter_lightgbm_small_catboost_small: only when optional dependencies are installed and the horizon gate passes.",
        ]
    )
    return "\n".join(lines)


def write_reports(
    output_dir: Path,
    trainability: pd.DataFrame,
    coverage: pd.DataFrame,
    ranking_cutoff: pd.DataFrame,
    ranking_manufacturer: pd.DataFrame,
    scope_metrics: pd.DataFrame,
    calibration_bins: pd.DataFrame,
    model_status: list[dict[str, Any]],
    split_note: str,
    config: dict[str, Any],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    trainability.to_csv(output_dir / "trainability_report_by_horizon.csv", index=False, encoding="utf-8-sig")
    coverage.to_csv(output_dir / "metric_group_coverage_report.csv", index=False, encoding="utf-8-sig")
    ranking_cutoff.to_csv(output_dir / "model_metrics_by_cutoff.csv", index=False, encoding="utf-8-sig")
    ranking_manufacturer.to_csv(output_dir / "model_metrics_by_manufacturer.csv", index=False, encoding="utf-8-sig")
    scope_metrics.to_csv(output_dir / "model_metrics_by_scope.csv", index=False, encoding="utf-8-sig")
    calibration_bins.to_csv(output_dir / "calibration_bins_by_model_horizon_scope.csv", index=False, encoding="utf-8-sig")
    _write_text(output_dir / "trainability_report.md", trainability_markdown(trainability, split_note, model_status))
    _write_text(
        output_dir / "model_experiment_summary.md",
        "\n".join(
            [
                "# Alive Prediction Small Model Experiment Summary",
                "",
                f"- experiment_name: {config['experiment_name']}",
                f"- split_note: {split_note}",
                "- train_scope: recurring_only",
                "- eval_scopes: recurring_only, all_monitorable, one_shot_only",
                "- one_shot_only predictions are diagnostic only and must not be interpreted as calibrated churn_probability.",
                "- save_model_artifacts: false",
                "- save_prediction_artifacts: false",
                "",
                "## Model Status",
                dataframe_to_markdown(pd.DataFrame(model_status), index=False) if model_status else "No model was trained.",
            ]
        ),
    )
    _write_text(
        output_dir / "model_metric_report.md",
        "# Model Metric Report\n\n" + (dataframe_to_markdown(scope_metrics, index=False) if not scope_metrics.empty else "No model metrics were generated."),
    )
    _write_text(
        output_dir / "calibration_report.md",
        "# Calibration Report\n\nOnly churn_probability_H* columns are used for Brier, LogLoss, AUC, PR_AUC, ECE, and calibration bins.\n",
    )
    _write_text(
        output_dir / "scope_comparison_report.md",
        "\n".join(
            [
                "# Scope Comparison Report",
                "",
                "Model selection should use recurring_only. all_monitorable is coverage observation. one_shot_only is diagnostic only.",
                "",
                dataframe_to_markdown(scope_metrics, index=False) if not scope_metrics.empty else "No scope metrics were generated.",
            ]
        ),
    )
    _write_text(
        output_dir / "one_shot_attention_list_note.md",
        "\n".join(
            [
                "# One-Shot Attention List Note",
                "",
                "one_shot_high_value_attention_list is a business-rule recall list.",
                "It is separate from model_probability_topk.",
                "It does not have calibrated churn_probability from the probability model.",
            ]
        ),
    )
    _write_text(
        output_dir / "topk_review.md",
        "# TopK Review\n\nThis report intentionally contains no row-level business names or raw details. Use aggregate metric reports for review.\n",
    )
    _write_text(output_dir / "model_vs_rule_baseline_report.md", build_model_vs_rule_baseline_report(output_dir, scope_metrics))


def build_model_vs_rule_baseline_report(output_dir: Path, scope_metrics: pd.DataFrame) -> str:
    root = project_root()
    rule_path = root / "reports/alive_prediction_2024/rule_baseline_metrics_by_cutoff.csv"
    value_path = root / "reports/alive_prediction_2024/rule_baseline_value_metrics_by_cutoff.csv"
    lines = [
        "# Model vs Rule Baseline Report",
        "",
        "Comparison is limited to recurring_only as the primary model-selection scope.",
    ]
    rule_summary = pd.DataFrame()
    if rule_path.exists():
        rule = pd.read_csv(rule_path)
        lines.extend(["", f"- rule_baseline_metrics_rows: {len(rule)}"])
        rule_summary = (
            rule.groupby(["horizon", "k"], dropna=False)[
                ["precision_at_k", "recall_at_k", "ndcg_at_k", "lift_at_k"]
            ]
            .mean()
            .reset_index()
        )
        rule_summary["k"] = rule_summary["k"].astype(str)
    else:
        lines.extend(["", "- rule_baseline_metrics_rows: missing"])
    value_summary = pd.DataFrame()
    if value_path.exists():
        value = pd.read_csv(value_path)
        lines.append(f"- rule_baseline_value_metrics_rows: {len(value)}")
        value_summary = (
            value.groupby(["horizon", "k"], dropna=False)[
                ["captured_value_at_k", "value_weighted_ndcg_at_k"]
            ]
            .mean()
            .reset_index()
        )
        value_summary["k"] = value_summary["k"].astype(str)
        rule_summary = rule_summary.merge(value_summary, on=["horizon", "k"], how="outer")
    else:
        lines.append("- rule_baseline_value_metrics_rows: missing")
    recurring = scope_metrics[scope_metrics.get("scope", pd.Series(dtype=str)) == "recurring_only"] if not scope_metrics.empty else pd.DataFrame()
    comparison = pd.DataFrame()
    if not recurring.empty and not rule_summary.empty:
        model_summary = recurring[
            [
                "model",
                "horizon",
                "k",
                "precision_at_k",
                "recall_at_k",
                "ndcg_at_k",
                "lift_at_k",
                "captured_value_at_k",
                "value_weighted_ndcg_at_k",
            ]
        ].copy()
        model_summary["k"] = model_summary["k"].astype(str)
        comparison = model_summary.merge(
            rule_summary,
            on=["horizon", "k"],
            how="left",
            suffixes=("_model", "_rule"),
        )
        for metric in [
            "precision_at_k",
            "recall_at_k",
            "ndcg_at_k",
            "lift_at_k",
            "captured_value_at_k",
            "value_weighted_ndcg_at_k",
        ]:
            comparison[f"{metric}_delta_model_minus_rule"] = (
                comparison[f"{metric}_model"] - comparison[f"{metric}_rule"]
            )
    lines.extend(
        [
            "",
            "## Model Minus Rule Baseline",
            dataframe_to_markdown(comparison, index=False) if not comparison.empty else "No comparison table was generated.",
            "",
            "## Small Model Recurring Metrics",
            dataframe_to_markdown(recurring, index=False) if not recurring.empty else "No recurring_only model metrics were generated.",
        ]
    )
    return "\n".join(lines)


def run_experiment(args: argparse.Namespace) -> int:
    root = project_root()
    config = read_yaml(root / args.config)
    if getattr(args, "reports_dir", None):
        config["input"]["reports_dir"] = args.reports_dir
        config["outputs"]["reports_dir"] = args.reports_dir
    output_dir = root / config["outputs"]["reports_dir"]
    diagnostics = collect_environment_diagnostics()
    write_environment_diagnostics(output_dir, diagnostics)
    rule_config = read_yaml(root / "configs/experiments/alive_prediction_rule_baseline.yaml")
    if args.smoke:
        split = dict(config["smoke_time_split"])
    elif getattr(args, "split_name", None):
        split = dict(config["time_splits"][args.split_name])
    else:
        split = dict(config["time_split"])
    split_note = split.get("note", config["time_split"].get("purge_gap_note", ""))
    include_status_history = bool(config["features"].get("status_history_features", {}).get("enabled", False))
    if args.refresh_cache:
        config["input"]["refresh_cache"] = True
    df = build_or_load_feature_label_table(
        config,
        split,
        refresh_cache=bool(config["input"].get("refresh_cache", False)),
        include_status_history=include_status_history,
    )
    df = add_scope_flags(df, config, rule_config)
    horizons = [args.horizon] if args.horizon else list(config["horizons_months"])
    model_names = args.model or [name for name, cfg in config["models"].items() if cfg.get("enabled", False)]
    if args.smoke:
        if not args.model:
            model_names = ["logistic_regression"]
        horizons = [horizon for horizon in horizons if horizon == 3] or [3]

    trainability = build_trainability_report(df, config, split, horizons)
    all_probability = []
    all_ranking = []
    all_value = []
    all_bins = []
    all_coverage = []
    model_status = []
    for horizon in horizons:
        label_col = f"label_die_H{horizon}"
        gate_row = trainability[trainability["horizon"] == horizon].iloc[0]
        if not bool(gate_row["can_train"]):
            for model_name in model_names:
                model_status.append({"model": model_name, "horizon": horizon, "status": "skipped", "reason": gate_row["skip_reason"]})
            continue
        train_df = df[cutoff_mask(df, split["train_cutoff_start"], split["train_cutoff_end"]) & df["recurring_candidate_flag"]].copy()
        train_df = train_df[~train_df["one_shot_high_value_silence_flag"]].copy()
        test_df = df[cutoff_mask(df, split["test_cutoff_start"], split["test_cutoff_end"])].copy()
        if set(pd.to_datetime(train_df["cutoff_month"]).dt.to_period("M")).intersection(set(pd.to_datetime(test_df["cutoff_month"]).dt.to_period("M"))):
            raise RuntimeError("Train and test cutoffs overlap")
        for model_name in model_names:
            fitted, fit_skip_reason = fit_model_in_memory(model_name, train_df, label_col, config)
            if fitted is None:
                failure = fit_skip_reason if isinstance(fit_skip_reason, dict) else _failure("skipped", str(fit_skip_reason))
                model_status.append(
                    {
                        "model": model_name,
                        "horizon": horizon,
                        "scope": "recurring_only",
                        "train_rows": len(train_df),
                        "eval_rows": 0,
                        "numeric_feature_count": 0,
                        "categorical_feature_count": 0,
                        "missing_or_reserved_features": "",
                        "status": failure["status"],
                        "reason": failure["reason"],
                        "traceback": failure["traceback"],
                    }
                )
                continue
            for scope, scope_df in split_scopes(test_df).items():
                if args.scope and scope != args.scope:
                    continue
                value_col = config["value_at_risk"]["amount_columns"][f"H{horizon}"]
                if scope_df[label_col].nunique(dropna=False) < 2:
                    probabilities = None
                    skip_reason = "label_has_single_class"
                    predict_traceback = ""
                else:
                    try:
                        probabilities = predict_with_fitted_model(fitted, scope_df)
                        skip_reason = ""
                        predict_traceback = ""
                    except Exception:
                        probabilities = None
                        skip_reason = "model_predict_failed"
                        predict_traceback = traceback.format_exc()
                status = {
                    "model": model_name,
                    "horizon": horizon,
                    "scope": scope,
                    "train_rows": len(train_df),
                    "eval_rows": len(scope_df),
                    "numeric_feature_count": len(fitted["numeric_cols"]),
                    "categorical_feature_count": len(fitted["categorical_cols"]),
                    "missing_or_reserved_features": ",".join(map(str, fitted["missing_or_reserved_features"][:20])),
                }
                if probabilities is None:
                    status.update({"status": "model_predict_failed" if skip_reason == "model_predict_failed" else "skipped", "reason": skip_reason, "traceback": predict_traceback})
                    model_status.append(status)
                    continue
                scored = scope_df.copy()
                prob_col = f"churn_probability_H{horizon}"
                scored[prob_col] = probabilities
                prob_metrics, ranking, value_metrics, bins = evaluate_predictions(
                    scored,
                    label_col,
                    prob_col,
                    value_col,
                    horizon,
                    model_name,
                    scope,
                    config,
                )
                coverage = metric_group_coverage(
                    scored,
                    label_col,
                    horizon,
                    scope,
                    config["metrics"]["ranking_group"],
                    int(config["metrics"].get("min_group_rows_for_topk", 5)),
                )
                coverage["model"] = model_name
                all_probability.append(prob_metrics)
                all_ranking.append(ranking)
                all_value.append(value_metrics)
                all_bins.append(bins)
                all_coverage.append(coverage)
                status.update({"status": "trained_in_memory", "reason": "", "traceback": ""})
                model_status.append(status)

    probability = pd.concat(all_probability, ignore_index=True) if all_probability else pd.DataFrame()
    ranking = pd.concat(all_ranking, ignore_index=True) if all_ranking else pd.DataFrame()
    value_metrics = pd.concat(all_value, ignore_index=True) if all_value else pd.DataFrame()
    bins = pd.concat(all_bins, ignore_index=True) if all_bins else pd.DataFrame()
    coverage = pd.concat(all_coverage, ignore_index=True) if all_coverage else pd.DataFrame()
    ranking_cutoff, ranking_manufacturer, scope_metrics = aggregate_metric_tables(ranking, value_metrics, probability)
    write_reports(output_dir, trainability, coverage, ranking_cutoff, ranking_manufacturer, scope_metrics, bins, model_status, split_note, config)
    write_environment_diagnostics(output_dir, diagnostics)
    print({"output_dir": str(output_dir), "trained_or_skipped": model_status}, flush=True)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run alive prediction small-model smoke experiments.")
    parser.add_argument("--config", default="configs/experiments/alive_prediction_small_models.yaml")
    parser.add_argument("--model", action="append", choices=["logistic_regression", "lightgbm_small", "catboost_small", "xgboost_small"])
    parser.add_argument("--horizon", type=int, choices=[3, 6, 12])
    parser.add_argument("--scope", choices=["recurring_only", "all_monitorable", "one_shot_only"])
    parser.add_argument("--split-name", choices=["train_2022_only", "train_2021_2022", "expanded_train_2020_2022"])
    parser.add_argument("--reports-dir")
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run_experiment(parse_args()))

