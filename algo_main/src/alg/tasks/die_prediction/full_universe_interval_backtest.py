"""Full-universe interval backtest for alive prediction.

This module builds a recurring monitorable-universe prediction-label frame and
compares the current in-memory logistic scorer with recency/frequency/interval
baselines. It is report-only: it does not save model files, tune parameters,
call LLMs, or modify M1-M7 artifacts.
"""

from __future__ import annotations

import importlib
import math
from pathlib import Path
import sys
import traceback
from typing import Any

import numpy as np
import pandas as pd

from alg.tasks.die_prediction.utility_backtest import (
    average_precision_score_simple,
    brier_score,
    expected_calibration_error,
    log_loss_score,
    ndcg_at_k,
    roc_auc_score_simple,
)


HORIZONS = [3, 6, 12]
HORIZON_LABELS = [f"H{h}" for h in HORIZONS]
KEY_COLS = ["manufacturer_code", "hospital_code", "drug_group", "drug_group_source", "cutoff_month"]
ENTITY_COLS = ["manufacturer_code", "hospital_code", "drug_group", "drug_group_source"]
JOIN_NO_SOURCE = ["manufacturer_code", "hospital_code", "drug_group", "cutoff_month"]
PROBABILITY_VERSION = "logistic_regression + frequency_decay_v1 + raw"
OUTPUT_FILES = [
    "full_universe_interval_backtest_summary.md",
    "full_universe_frame_audit.md",
    "full_universe_recurring_backtest_frame_sample.csv",
    "full_universe_metric_summary.csv",
    "full_universe_topk_metrics.csv",
    "candidate_coverage_metrics.csv",
    "candidate_vs_full_universe_metrics.csv",
    "baseline_comparison_full_universe.csv",
    "interval_baseline_coverage_audit.csv",
    "stable_segment_service_gate.csv",
    "probability_availability_policy.md",
    "full_universe_false_negative_cases_sample.csv",
    "full_universe_false_positive_cases_sample.csv",
    "next_algorithm_decision.md",
]
SCORERS = {
    "global_logistic_scorer": "churn_probability_H",
    "recency_only_baseline": "recency_score",
    "frequency_decay_baseline": "frequency_decay_score",
    "interval_overdue_baseline": "interval_score",
    "simple_interval_or_survival_lite_score": "survival_lite_score",
}
TOPK_SPECS: list[int | str] = [10, 20, 50, 100, "top_1_pct", "top_5_pct", "top_10_pct"]
SERVICE_SEGMENT_DIMS = [
    "horizon",
    "demand_shape_label",
    "history_sufficiency_flag",
    "hospital_level_code",
    "province_code",
    "drug_category_code",
    "purchase_count_bucket",
    "active_month_count_bucket",
    "months_since_last_purchase_bucket",
    "survival_state",
]
DAYS_PER_MONTH = 30.4375
EPS = 1e-9


def read_csv_or_empty(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, **kwargs)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def read_parquet_or_empty(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_parquet(path, columns=columns)
    except (FileNotFoundError, ValueError, ImportError, OSError):
        return pd.DataFrame()


def write_csv(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def normalize_cutoff_month_value(value: Any) -> str:
    if pd.isna(value):
        return "__MISSING__"
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return str(value)
    return ts.to_period("M").strftime("%Y-%m")


def normalize_cutoff_month_series(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.to_period("M").astype(str)


def normalize_horizon_label(value: Any) -> str:
    if pd.isna(value):
        return "__MISSING__"
    text = str(value).strip().upper()
    if text.startswith("H"):
        text = text[1:]
    try:
        return f"H{int(float(text))}"
    except ValueError:
        return str(value)


def horizon_to_int(value: Any) -> int | None:
    text = normalize_horizon_label(value)
    if text.startswith("H"):
        try:
            return int(text[1:])
        except ValueError:
            return None
    return None


def month_end(month_like: Any) -> pd.Timestamp:
    ts = pd.to_datetime(month_like, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    return ts.to_period("M").to_timestamp("M")


def add_months_month_end(month_like: Any, months: int) -> pd.Timestamp:
    start = month_end(month_like)
    if pd.isna(start):
        return pd.NaT
    return (start.to_period("M") + int(months)).to_timestamp("M")


def fixed_window_closed(cutoff_month: Any, horizon: int, max_observed_purchase_date: Any) -> bool:
    end = add_months_month_end(cutoff_month, horizon)
    max_date = pd.to_datetime(max_observed_purchase_date, errors="coerce")
    if pd.isna(end) or pd.isna(max_date):
        return False
    return bool(end <= max_date)


def ensure_drug_group_source(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "drug_group_source" not in out.columns:
        out["drug_group_source"] = "drug_code"
    return out


def prepare_keyed(df: pd.DataFrame) -> pd.DataFrame:
    out = ensure_drug_group_source(df)
    if "cutoff_month" in out.columns:
        out["cutoff_month"] = normalize_cutoff_month_series(out["cutoff_month"])
    if "horizon" in out.columns:
        out["horizon"] = out["horizon"].map(normalize_horizon_label)
    return out


def entity_id(df: pd.DataFrame) -> pd.Series:
    cols = [c for c in ENTITY_COLS if c in df.columns]
    if not cols:
        return pd.Series(np.arange(len(df)).astype(str), index=df.index)
    return df[cols].fillna("__MISSING__").astype(str).agg("|".join, axis=1)


def safe_numeric(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype="float64")
    values = df[column]
    if isinstance(values, pd.DataFrame):
        values = values.iloc[:, 0]
    return pd.to_numeric(values, errors="coerce")


def safe_text(df: pd.DataFrame, column: str, fill: str = "__MISSING__") -> pd.Series:
    if column not in df.columns:
        return pd.Series(fill, index=df.index, dtype="object")
    values = df[column]
    if isinstance(values, pd.DataFrame):
        values = values.iloc[:, 0]
    return values.fillna(fill).astype(str)


def demand_shape_from_adi_cv2(df: pd.DataFrame) -> pd.Series:
    adi = safe_numeric(df, "adi_asof_cutoff")
    cv2 = safe_numeric(df, "cv2_quantity_asof_cutoff")
    labels = pd.Series("__MISSING__", index=df.index, dtype="object")
    valid = adi.notna() & cv2.notna()
    labels.loc[valid & adi.lt(1.32) & cv2.lt(0.49)] = "smooth"
    labels.loc[valid & adi.lt(1.32) & cv2.ge(0.49)] = "erratic"
    labels.loc[valid & adi.ge(1.32) & cv2.lt(0.49)] = "intermittent"
    labels.loc[valid & adi.ge(1.32) & cv2.ge(0.49)] = "lumpy"
    fallback = safe_text(df, "demand_pattern_type_asof_cutoff", fill="__MISSING__")
    labels.loc[labels.eq("__MISSING__") & fallback.ne("__MISSING__")] = fallback.loc[
        labels.eq("__MISSING__") & fallback.ne("__MISSING__")
    ]
    return labels


def assign_history_sufficiency(df: pd.DataFrame) -> pd.Series:
    purchase = safe_numeric(df, "purchase_count_asof_cutoff")
    active = safe_numeric(df, "active_month_count_asof_cutoff")
    median = safe_numeric(df, "median_purchase_interval_days_asof_cutoff")
    std = safe_numeric(df, "std_purchase_interval_days_asof_cutoff")
    iqr = safe_numeric(df, "purchase_interval_iqr_asof_cutoff")
    cv2 = safe_numeric(df, "cv2_quantity_asof_cutoff")
    flag = pd.Series("history_sufficient", index=df.index, dtype="object")
    insufficient = purchase.lt(3) | active.lt(2) | median.isna()
    high_variance = (
        (std.notna() & median.gt(0) & (std / median).gt(1.0))
        | (iqr.notna() & median.gt(0) & (iqr / median).gt(1.0))
        | cv2.gt(1.0)
    )
    flag.loc[high_variance] = "history_medium"
    flag.loc[insufficient] = "history_insufficient"
    return flag


def bucket_numeric(values: pd.Series, kind: str) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    if kind == "purchase":
        bins = [-np.inf, 2, 4, 9, np.inf]
        labels = ["lt3", "3_4", "5_9", "ge10"]
    elif kind == "active":
        bins = [-np.inf, 1, 2, 5, np.inf]
        labels = ["lt2", "2", "3_5", "ge6"]
    elif kind == "last":
        bins = [-np.inf, 0, 2, 5, 11, np.inf]
        labels = ["0", "1_2", "3_5", "6_11", "ge12"]
    else:
        bins = [-np.inf, 5, 11, 23, 47, np.inf]
        labels = ["lt6", "6_11", "12_23", "24_47", "ge48"]
    return pd.cut(numeric, bins=bins, labels=labels).astype("object").fillna("missing")


def safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    num = pd.to_numeric(numerator, errors="coerce")
    den = pd.to_numeric(denominator, errors="coerce")
    out = num / den.replace(0, np.nan)
    out.loc[den.eq(0) & num.eq(0)] = 0.0
    out.loc[den.eq(0) & num.gt(0)] = np.nan
    return out


def rank_normalize_within_group(df: pd.DataFrame, value_col: str, group_cols: list[str]) -> pd.Series:
    values = safe_numeric(df, value_col)
    if values.notna().sum() == 0:
        return values
    ranks = values.groupby([df[c] for c in group_cols], dropna=False).rank(pct=True, method="average")
    return ranks.astype(float)


def recency_score(df: pd.DataFrame) -> pd.Series:
    work = df.copy()
    if "months_since_last_purchase_asof_cutoff" not in work.columns and "months_since_last_purchase" in work.columns:
        work["months_since_last_purchase_asof_cutoff"] = work["months_since_last_purchase"]
    group_cols = [c for c in ["cutoff_month", "horizon"] if c in work.columns]
    if group_cols:
        return rank_normalize_within_group(work, "months_since_last_purchase_asof_cutoff", group_cols).clip(0, 1)
    values = safe_numeric(work, "months_since_last_purchase_asof_cutoff")
    max_value = values.max(skipna=True)
    return (values / max_value).clip(0, 1) if pd.notna(max_value) and max_value > 0 else values * np.nan


def frequency_decay_score(df: pd.DataFrame) -> pd.Series:
    if "frequency_decay_3m_vs_12m" in df.columns:
        ratio = safe_numeric(df, "frequency_decay_3m_vs_12m")
    else:
        recent_rate = safe_numeric(df, "order_count_last_3m_asof_cutoff") / 3.0
        annual_rate = safe_numeric(df, "order_count_last_12m_asof_cutoff") / 12.0
        ratio = safe_ratio(recent_rate, annual_rate)
    score = (1.0 - ratio.clip(lower=0, upper=1)).clip(0, 1)
    score.loc[ratio.isna()] = np.nan
    return score


def interval_overdue_score(df: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
    expected = safe_numeric(df, "expected_interval_months")
    if expected.isna().all():
        expected = safe_numeric(df, "median_purchase_interval_days_asof_cutoff") / DAYS_PER_MONTH
    months = safe_numeric(df, "months_since_last_purchase_asof_cutoff")
    if months.isna().all():
        months = safe_numeric(df, "months_since_last_purchase")
    overdue = months / expected.clip(lower=EPS)
    overdue.loc[expected.isna() | expected.le(0) | months.isna()] = np.nan
    score = (overdue / (1.0 + overdue)).clip(0, 1)
    return score, overdue, expected


def survival_state_from_overdue(df: pd.DataFrame, overdue_ratio: pd.Series) -> pd.Series:
    state = pd.Series("interval_unavailable", index=df.index, dtype="object")
    state.loc[overdue_ratio.lt(0.8)] = "normal_interval"
    state.loc[overdue_ratio.ge(0.8) & overdue_ratio.lt(1.2)] = "near_expected_interval"
    state.loc[overdue_ratio.ge(1.2) & overdue_ratio.lt(2.0)] = "slightly_overdue"
    state.loc[overdue_ratio.ge(2.0) & overdue_ratio.lt(3.0)] = "materially_overdue"
    state.loc[overdue_ratio.ge(3.0)] = "likely_churn_interval"
    state.loc[safe_text(df, "history_sufficiency_flag").eq("history_insufficient")] = "insufficient_history"
    state.loc[safe_text(df, "demand_shape_label").eq("lumpy") & overdue_ratio.notna()] = "low_confidence_lumpy"
    return state


def survival_lite_score_from_state(df: pd.DataFrame) -> pd.Series:
    mapping = {
        "interval_unavailable": np.nan,
        "insufficient_history": np.nan,
        "normal_interval": 0.10,
        "near_expected_interval": 0.35,
        "slightly_overdue": 0.55,
        "materially_overdue": 0.75,
        "likely_churn_interval": 0.90,
        "low_confidence_lumpy": 0.45,
    }
    return safe_text(df, "survival_state").map(mapping).astype(float)


def feature_table_path(root: Path) -> Path:
    return (
        root
        / "data/05_features/alive_prediction/v1_drug_code_monitorable_gap12/"
        / "cutoff_2024-01_2024-12/feature_table__status0.parquet"
    )


def label_table_path(root: Path) -> Path:
    return (
        root
        / "data/05_features/alive_prediction/v1_drug_code_monitorable_gap12/"
        / "cutoff_2024-01_2024-12/alive_labels__H3_6_12.parquet"
    )


def load_full_universe_inputs(root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    return read_parquet_or_empty(feature_table_path(root)), read_parquet_or_empty(label_table_path(root))


def long_label_frame(labels: pd.DataFrame) -> tuple[pd.DataFrame, pd.Timestamp]:
    if labels.empty:
        return pd.DataFrame(), pd.NaT
    base = labels.copy()
    base["cutoff_month"] = normalize_cutoff_month_series(base["cutoff_month"])
    if "drug_group_source" not in base.columns:
        base["drug_group_source"] = "drug_code"
    max_cutoff = pd.to_datetime(base["cutoff_month"], errors="coerce").max()
    max_observed = (max_cutoff.to_period("M") + max(HORIZONS)).to_timestamp("M") if not pd.isna(max_cutoff) else pd.NaT
    rows: list[pd.DataFrame] = []
    for horizon in HORIZONS:
        alive_col = f"label_alive_H{horizon}"
        die_col = f"label_die_H{horizon}"
        if alive_col not in base.columns or die_col not in base.columns:
            continue
        part = base[[*JOIN_NO_SOURCE, alive_col, die_col]].copy()
        part["drug_group_source"] = "drug_code"
        part = part.rename(columns={alive_col: "label_alive_H", die_col: "label_die_H"})
        part["horizon"] = f"H{horizon}"
        part["label_window_start"] = part["cutoff_month"].map(month_end)
        part["label_window_end"] = part["cutoff_month"].map(lambda value: add_months_month_end(value, horizon))
        part["max_observed_purchase_date"] = max_observed
        part["label_window_closed"] = part["label_window_end"].le(max_observed) & part["label_die_H"].notna()
        rows.append(part)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(), max_observed


def build_full_universe_frame(features: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    if features.empty or labels.empty:
        return pd.DataFrame()
    feat = prepare_keyed(features)
    purchase = safe_numeric(feat, "purchase_count_asof_cutoff")
    active = safe_numeric(feat, "active_month_count_asof_cutoff")
    feat = feat[purchase.ge(3) & active.ge(2)].copy()
    feat["recurring_scope_note"] = "purchase_count>=3_and_active_month_count>=2"
    feat["demand_shape_label"] = demand_shape_from_adi_cv2(feat)
    feat["history_sufficiency_flag"] = assign_history_sufficiency(feat)
    feat["purchase_count_bucket"] = bucket_numeric(safe_numeric(feat, "purchase_count_asof_cutoff"), "purchase")
    feat["active_month_count_bucket"] = bucket_numeric(safe_numeric(feat, "active_month_count_asof_cutoff"), "active")
    feat["months_since_last_purchase_bucket"] = bucket_numeric(
        safe_numeric(feat, "months_since_last_purchase_asof_cutoff"), "last"
    )
    feat["months_observed_bucket"] = bucket_numeric(safe_numeric(feat, "months_observed_asof_cutoff"), "observed")
    feat["months_since_first_purchase_bucket"] = bucket_numeric(
        safe_numeric(feat, "months_since_first_purchase_asof_cutoff"), "first"
    )

    labels_long, _max_observed = long_label_frame(labels)
    if labels_long.empty:
        return pd.DataFrame()
    merged = feat.merge(labels_long, on=KEY_COLS, how="inner")
    merged["label_die_H"] = pd.to_numeric(merged["label_die_H"], errors="coerce")
    merged["label_alive_H"] = pd.to_numeric(merged["label_alive_H"], errors="coerce")
    merged["in_m1_candidate"] = False
    merged["candidate_selection_reason"] = ""
    merged["final_candidate_status"] = ""
    merged["prediction_source"] = "logistic_scorer_not_attempted"
    merged["probability_candidate_version"] = PROBABILITY_VERSION
    return merged.reset_index(drop=True)


def _insert_scripts_path(root: Path) -> None:
    src_path = str(root / "src")
    scripts_path = str(root / "scripts")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)


def reproduce_logistic_probability_scores(root: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    status: dict[str, Any] = {
        "available": False,
        "prediction_source": "unavailable",
        "reason": "",
        "trained_formal_model": False,
        "saved_model_file": False,
    }
    required = [
        root
        / "data/05_features/alive_prediction/v1_drug_code_monitorable_gap12/cutoff_2020-01_2024-12/feature_table__status0.parquet",
        root
        / "data/05_features/alive_prediction/v1_drug_code_monitorable_gap12/cutoff_2020-01_2024-12/alive_labels__H3_6_12.parquet",
    ]
    if not all(path.exists() for path in required):
        status["reason"] = "required_2020_2024_feature_label_artifacts_missing"
        return pd.DataFrame(), status
    try:
        _insert_scripts_path(root)
        small = importlib.import_module("run_alive_prediction_small_model_experiments")
        feature_stability = importlib.import_module("run_alive_prediction_feature_stability_v1")
        consolidation = importlib.import_module("run_alive_prediction_probability_consolidation")
        expanded = importlib.import_module("run_alive_prediction_expanded_train_diagnostics")

        config = small.read_yaml(root / "configs/experiments/alive_prediction_small_models.yaml")
        df = consolidation.load_feature_data(config)
        df = feature_stability.add_stability_features(df)
        df = prepare_keyed(df)
        periods = pd.PeriodIndex(df["cutoff_month"], freq="M")
        train = df[(periods >= pd.Period("2020-01", freq="M")) & (periods <= pd.Period("2022-12", freq="M"))].copy()
        train = train[train["recurring_candidate_flag"].astype(bool)].copy()
        if "one_shot_high_value_silence_flag" in train.columns:
            train = train[~train["one_shot_high_value_silence_flag"].astype(bool)].copy()
        score_all = df[(periods >= pd.Period("2024-01", freq="M")) & (periods <= pd.Period("2024-12", freq="M"))].copy()
        score_recurring = small.split_scopes(score_all)["recurring_only"].copy()
        spec = feature_stability.feature_sets()["frequency_decay_v1"]
        numeric, categorical, rejected = feature_stability.validate_features(
            train, spec["numeric"], spec["categorical"], config
        )
        scored_parts: list[pd.DataFrame] = []
        failures: list[str] = []
        for horizon in HORIZONS:
            label_col = f"label_die_H{horizon}"
            if label_col not in train.columns or train[label_col].nunique(dropna=True) < 2:
                failures.append(f"H{horizon}:label_not_trainable")
                continue
            fitted, reason = expanded.fit_with_columns(
                "logistic_regression", train, label_col, config, numeric, categorical, rejected
            )
            if fitted is None:
                failures.append(f"H{horizon}:{reason}")
                continue
            probability = small.predict_with_fitted_model(fitted, score_recurring)
            part = score_recurring[[*KEY_COLS]].copy()
            part["horizon"] = f"H{horizon}"
            part["churn_probability_H"] = np.clip(probability, EPS, 1 - EPS)
            scored_parts.append(part)
        if not scored_parts:
            status["reason"] = "no_horizon_scored:" + ";".join(failures)
            return pd.DataFrame(), status
        out = pd.concat(scored_parts, ignore_index=True)
        status.update(
            {
                "available": True,
                "prediction_source": "in_memory_reproduced_probability_candidate_v1_full_universe",
                "reason": ";".join(failures),
                "train_window": "2020-01_to_2022-12",
                "score_window": "2024-01_to_2024-12",
                "model": "logistic_regression",
                "feature_set": "frequency_decay_v1",
                "numeric_features": ",".join(numeric),
                "categorical_features": ",".join(categorical),
            }
        )
        return out, status
    except Exception as exc:
        status["reason"] = f"score_reproduction_failed:{exc!r}\n{traceback.format_exc()}"
        return pd.DataFrame(), status


def attach_logistic_scores(frame: pd.DataFrame, scores: pd.DataFrame, status: dict[str, Any]) -> pd.DataFrame:
    out = frame.copy()
    if scores.empty:
        out["churn_probability_H"] = np.nan
        out["prediction_source"] = status.get("prediction_source", "unavailable")
        out["probability_candidate_version"] = PROBABILITY_VERSION
        return out
    scored = prepare_keyed(scores)
    out = out.merge(scored, on=[*KEY_COLS, "horizon"], how="left", suffixes=("", "_score"))
    if "churn_probability_H_score" in out.columns:
        out["churn_probability_H"] = out["churn_probability_H_score"]
        out = out.drop(columns=["churn_probability_H_score"])
    out["prediction_source"] = np.where(
        out["churn_probability_H"].notna(),
        status.get("prediction_source", "in_memory_reproduced_probability_candidate_v1_full_universe"),
        "logistic_score_unavailable_for_row",
    )
    out["probability_candidate_version"] = PROBABILITY_VERSION
    return out


def attach_candidates(frame: pd.DataFrame, candidate_by_horizon: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    if candidate_by_horizon.empty:
        out["in_m1_candidate"] = False
        out["candidate_selection_reason"] = ""
        out["rank_m1_business_priority"] = np.nan
        return out
    cand = prepare_keyed(candidate_by_horizon)
    keep = [
        *KEY_COLS,
        "horizon",
        "selection_reason",
        "selection_note",
        "rank_global",
        "rank_within_manufacturer",
        "relative_business_priority_score_H",
    ]
    cand = cand[[c for c in keep if c in cand.columns]].drop_duplicates([*KEY_COLS, "horizon"])
    cand = cand.rename(
        columns={
            "selection_reason": "candidate_selection_reason_joined",
            "selection_note": "candidate_selection_note",
            "rank_global": "rank_m1_business_priority",
            "rank_within_manufacturer": "rank_m1_within_manufacturer",
            "relative_business_priority_score_H": "m1_relative_business_priority_score_H",
        }
    )
    out = out.merge(cand, on=[*KEY_COLS, "horizon"], how="left")
    out["in_m1_candidate"] = out["candidate_selection_reason_joined"].notna()
    out["candidate_selection_reason"] = out["candidate_selection_reason_joined"].fillna("")
    out = out.drop(columns=[c for c in ["candidate_selection_reason_joined"] if c in out.columns])
    return out


def attach_status(frame: pd.DataFrame, status: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    if status.empty:
        out["final_candidate_status"] = out.get("final_candidate_status", "")
        return out
    work = prepare_keyed(status)
    if "candidate_type" in work.columns:
        work = work[work["candidate_type"].astype(str).eq("recurring_business_priority")].copy()
    keep = [
        *KEY_COLS,
        "horizon",
        "final_candidate_status",
        "review_priority",
        "evidence_strength",
    ]
    work = work[[c for c in keep if c in work.columns]].drop_duplicates([*KEY_COLS, "horizon"])
    out = out.merge(work, on=[*KEY_COLS, "horizon"], how="left", suffixes=("", "_status"))
    if "final_candidate_status_status" in out.columns:
        out["final_candidate_status"] = out["final_candidate_status_status"].fillna(out["final_candidate_status"])
        out = out.drop(columns=["final_candidate_status_status"])
    return out


def attach_d002(frame: pd.DataFrame, detector: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    if detector.empty or "detector_name" not in detector.columns:
        out["d002_hit_flag"] = np.nan
        return out
    work = prepare_keyed(detector)
    work = work[work["detector_name"].astype(str).eq("purchase_frequency_decay_rate_test")].copy()
    if work.empty:
        out["d002_hit_flag"] = np.nan
        return out
    work["hit_numeric"] = work.get("hit_flag", False).fillna(False).astype(bool).astype(int)
    grouped = (
        work.groupby([*KEY_COLS, "horizon"], dropna=False)["hit_numeric"].max().reset_index()
    )
    grouped["d002_hit_flag"] = grouped["hit_numeric"].astype(bool)
    out = out.merge(grouped[[*KEY_COLS, "horizon", "d002_hit_flag"]], on=[*KEY_COLS, "horizon"], how="left")
    return out


def add_baseline_scores(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    if "churn_probability_H" not in out.columns:
        out["churn_probability_H"] = np.nan
    out["recency_score"] = recency_score(out)
    out["frequency_decay_score"] = frequency_decay_score(out)
    interval_score, overdue_ratio, expected_interval_months = interval_overdue_score(out)
    out["expected_interval_months"] = expected_interval_months
    out["overdue_ratio"] = overdue_ratio
    out["interval_score"] = interval_score
    out["survival_state"] = survival_state_from_overdue(out, overdue_ratio)
    out["survival_lite_score"] = survival_lite_score_from_state(out)
    for horizon in HORIZONS:
        value_col = f"value_at_risk_amount_nonnegative_H{horizon}_asof_cutoff"
        mask = out["horizon"].eq(f"H{horizon}")
        out.loc[mask, "relative_value_at_risk_H"] = safe_numeric(out.loc[mask], value_col)
    out["relative_business_priority_score_H"] = safe_numeric(out, "churn_probability_H") * safe_numeric(
        out, "relative_value_at_risk_H"
    ).fillna(0)
    out["rank_probability_full_universe"] = out.groupby(["cutoff_month", "horizon"], dropna=False)[
        "churn_probability_H"
    ].rank(method="first", ascending=False)
    out["rank_business_priority_full_universe"] = out.groupby(["cutoff_month", "horizon"], dropna=False)[
        "relative_business_priority_score_H"
    ].rank(method="first", ascending=False)
    out["in_probability_topk"] = False
    out["in_business_priority_topk"] = False
    for (_cutoff, _horizon), idx in out.groupby(["cutoff_month", "horizon"], dropna=False).groups.items():
        n = len(idx)
        top_n = max(1, int(math.ceil(n * 0.05))) if n else 0
        out.loc[idx, "in_probability_topk"] = out.loc[idx, "rank_probability_full_universe"].le(top_n)
        out.loc[idx, "in_business_priority_topk"] = out.loc[idx, "rank_business_priority_full_universe"].le(top_n)
    return out


def closed_eval_frame(frame: pd.DataFrame, score_col: str | None = None) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    out = frame[frame["label_window_closed"].astype(bool) & frame["label_die_H"].notna()].copy()
    if score_col is not None:
        out = out[pd.to_numeric(out[score_col], errors="coerce").notna()].copy()
    out["label_die_H"] = out["label_die_H"].astype(int)
    return out


def _as_binary_score(df: pd.DataFrame, label_col: str, score_col: str) -> tuple[np.ndarray, np.ndarray]:
    if df.empty or label_col not in df.columns or score_col not in df.columns:
        return np.array([], dtype=int), np.array([], dtype=float)
    valid = df[[label_col, score_col]].copy()
    valid[label_col] = pd.to_numeric(valid[label_col], errors="coerce")
    valid[score_col] = pd.to_numeric(valid[score_col], errors="coerce")
    valid = valid.dropna()
    if valid.empty:
        return np.array([], dtype=int), np.array([], dtype=float)
    return valid[label_col].astype(int).to_numpy(), np.clip(valid[score_col].to_numpy(dtype=float), EPS, 1 - EPS)


def metric_dict(df: pd.DataFrame, score_col: str, scorer_name: str, horizon: str = "overall") -> dict[str, Any]:
    closed = closed_eval_frame(df, score_col)
    y_true, y_score = _as_binary_score(closed, "label_die_H", score_col)
    row_count = int(len(y_true))
    pos = int(y_true.sum()) if row_count else 0
    neg = row_count - pos
    positive_rate = float(y_true.mean()) if row_count else np.nan
    pr_auc = average_precision_score_simple(y_true, y_score) if row_count and pos else np.nan
    return {
        "scorer_name": scorer_name,
        "horizon": horizon,
        "aggregation_method": "pooled_full_universe",
        "row_count": row_count,
        "entity_count": int(entity_id(closed).nunique()) if not closed.empty else 0,
        "positive_rate": positive_rate,
        "auc": roc_auc_score_simple(y_true, y_score) if row_count and pos and neg else np.nan,
        "pr_auc": pr_auc,
        "pr_auc_baseline": positive_rate,
        "pr_auc_gain": pr_auc - positive_rate if not pd.isna(pr_auc) and not pd.isna(positive_rate) else np.nan,
        "pr_auc_lift": pr_auc / positive_rate if positive_rate and not pd.isna(pr_auc) else np.nan,
        "brier": brier_score(y_true, y_score) if row_count else np.nan,
        "logloss": log_loss_score(y_true, y_score) if row_count else np.nan,
        "ece": expected_calibration_error(y_true, y_score) if row_count else np.nan,
        "score_available_rate": float(pd.to_numeric(df.get(score_col, pd.Series(index=df.index)), errors="coerce").notna().mean())
        if len(df)
        else np.nan,
        "note": scorer_note(scorer_name),
    }


def scorer_note(scorer_name: str) -> str:
    notes = {
        "global_logistic_scorer": "in-memory reproduction of current probability_candidate_v1 when available",
        "recency_only_baseline": "rank-normalized recency score; not a calibrated probability",
        "frequency_decay_baseline": "1 - recent-vs-12m frequency ratio; not a calibrated probability",
        "interval_overdue_baseline": "overdue_ratio transformed to [0,1]; ranking/evidence only",
        "simple_interval_or_survival_lite_score": "ordinal interval state score; not a calibrated probability",
    }
    return notes.get(scorer_name, "")


def full_universe_metric_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for scorer_name, score_col in SCORERS.items():
        rows.append(metric_dict(frame, score_col, scorer_name, "overall"))
        for horizon, part in frame.groupby("horizon", dropna=False):
            rows.append(metric_dict(part, score_col, scorer_name, str(horizon)))
    return pd.DataFrame(rows)


def _topk_count(k_spec: int | str, n: int) -> int:
    if isinstance(k_spec, int):
        return min(k_spec, n)
    pct = {"top_1_pct": 0.01, "top_5_pct": 0.05, "top_10_pct": 0.10}[k_spec]
    return max(1, min(n, int(math.ceil(n * pct))))


def topk_for_group(part: pd.DataFrame, score_col: str, k_spec: int | str) -> dict[str, Any]:
    closed = closed_eval_frame(part, score_col)
    y_true, y_score = _as_binary_score(closed, "label_die_H", score_col)
    row_count = int(len(y_true))
    positive_rate = float(y_true.mean()) if row_count else np.nan
    if row_count == 0:
        return {
            "row_count": 0,
            "positive_rate": np.nan,
            "topk_count": 0,
            "topk_die_count": 0,
            "precision_at_k": np.nan,
            "recall_at_k": np.nan,
            "lift_at_k": np.nan,
            "ndcg_at_k": np.nan,
            "avg_score": np.nan,
            "score_available_rate": 0.0,
        }
    k = _topk_count(k_spec, row_count)
    order = np.argsort(-y_score)
    y_sorted = y_true[order]
    selected = y_sorted[:k]
    precision = float(selected.mean()) if k else np.nan
    total_pos = float(y_true.sum())
    return {
        "row_count": row_count,
        "positive_rate": positive_rate,
        "topk_count": int(k),
        "topk_die_count": int(selected.sum()),
        "precision_at_k": precision,
        "recall_at_k": float(selected.sum() / total_pos) if total_pos else np.nan,
        "lift_at_k": precision / positive_rate if positive_rate and not pd.isna(precision) else np.nan,
        "ndcg_at_k": ndcg_at_k(y_sorted, k),
        "avg_score": float(np.mean(y_score[order[:k]])) if k else np.nan,
        "score_available_rate": float(pd.to_numeric(part.get(score_col, pd.Series(index=part.index)), errors="coerce").notna().mean())
        if len(part)
        else np.nan,
    }


def full_universe_topk_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for scorer_name, score_col in SCORERS.items():
        for horizon, horizon_part in frame.groupby("horizon", dropna=False):
            for k_spec in TOPK_SPECS:
                cutoff_rows = []
                for cutoff, cutoff_part in horizon_part.groupby("cutoff_month", dropna=False):
                    row = topk_for_group(cutoff_part, score_col, k_spec)
                    row["cutoff_month"] = cutoff
                    cutoff_rows.append(row)
                cutoff_df = pd.DataFrame(cutoff_rows)
                rows.append(
                    {
                        "scorer_name": scorer_name,
                        "horizon": horizon,
                        "K": k_spec,
                        "aggregation_method": "macro_by_cutoff",
                        "row_count": int(cutoff_df["row_count"].sum()) if not cutoff_df.empty else 0,
                        "positive_rate": float(cutoff_df["positive_rate"].mean()) if not cutoff_df.empty else np.nan,
                        "topk_count": int(cutoff_df["topk_count"].sum()) if not cutoff_df.empty else 0,
                        "topk_die_count": int(cutoff_df["topk_die_count"].sum()) if not cutoff_df.empty else 0,
                        "precision_at_k": float(cutoff_df["precision_at_k"].mean()) if not cutoff_df.empty else np.nan,
                        "recall_at_k": float(cutoff_df["recall_at_k"].mean()) if not cutoff_df.empty else np.nan,
                        "lift_at_k": float(cutoff_df["lift_at_k"].mean()) if not cutoff_df.empty else np.nan,
                        "ndcg_at_k": float(cutoff_df["ndcg_at_k"].mean()) if not cutoff_df.empty else np.nan,
                        "avg_score": float(cutoff_df["avg_score"].mean()) if not cutoff_df.empty else np.nan,
                        "score_available_rate": float(cutoff_df["score_available_rate"].mean()) if not cutoff_df.empty else np.nan,
                        "pooled_only_for_reference": False,
                    }
                )
    return pd.DataFrame(rows)


def candidate_coverage_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    closed = closed_eval_frame(frame)
    for keys, part in closed.groupby(["horizon", "cutoff_month"], dropna=False):
        horizon, cutoff = keys
        rows.append(candidate_coverage_row(part, horizon, cutoff))
    for horizon, part in closed.groupby("horizon", dropna=False):
        rows.append(candidate_coverage_row(part, horizon, "all_2024"))
    rows.append(candidate_coverage_row(closed, "overall", "all_2024"))
    return pd.DataFrame(rows)


def candidate_coverage_row(part: pd.DataFrame, horizon: Any, cutoff: Any) -> dict[str, Any]:
    full_rows = int(len(part))
    full_die = int(safe_numeric(part, "label_die_H").sum()) if full_rows else 0
    cand = part[part["in_m1_candidate"].astype(bool)].copy() if "in_m1_candidate" in part.columns else part.iloc[0:0]
    non = part[~part["in_m1_candidate"].astype(bool)].copy() if "in_m1_candidate" in part.columns else part
    cand_rows = int(len(cand))
    cand_die = int(safe_numeric(cand, "label_die_H").sum()) if cand_rows else 0
    cand_rate = cand_die / cand_rows if cand_rows else np.nan
    non_rate = float(safe_numeric(non, "label_die_H").mean()) if len(non) else np.nan
    return {
        "horizon": horizon,
        "cutoff_month": cutoff,
        "full_universe_rows": full_rows,
        "full_universe_die_count": full_die,
        "candidate_rows": cand_rows,
        "candidate_die_count": cand_die,
        "non_candidate_rows": int(len(non)),
        "non_candidate_die_count": int(safe_numeric(non, "label_die_H").sum()) if len(non) else 0,
        "candidate_coverage_rate": cand_rows / full_rows if full_rows else np.nan,
        "candidate_die_recall": cand_die / full_die if full_die else np.nan,
        "candidate_positive_rate": cand_rate,
        "non_candidate_positive_rate": non_rate,
        "candidate_lift_vs_non_candidate": cand_rate / non_rate if non_rate and not pd.isna(cand_rate) else np.nan,
        "m1_candidate_policy_note": "global_top5pct_plus_manufacturer_min_fill_by_business_priority",
    }


def candidate_vs_full_universe_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for scorer_name, score_col in SCORERS.items():
        for horizon, part in frame.groupby("horizon", dropna=False):
            full = metric_dict(part, score_col, scorer_name, str(horizon))
            candidate_part = part[part["in_m1_candidate"].astype(bool)].copy()
            candidate = metric_dict(candidate_part, score_col, scorer_name, str(horizon))
            rows.append(
                {
                    "scorer_name": scorer_name,
                    "horizon": horizon,
                    "full_universe_row_count": full["row_count"],
                    "candidate_row_count": candidate["row_count"],
                    "full_universe_auc": full["auc"],
                    "candidate_level_auc": candidate["auc"],
                    "auc_full_minus_candidate": full["auc"] - candidate["auc"]
                    if not pd.isna(full["auc"]) and not pd.isna(candidate["auc"])
                    else np.nan,
                    "full_universe_pr_auc_gain": full["pr_auc_gain"],
                    "candidate_pr_auc_gain": candidate["pr_auc_gain"],
                    "full_universe_ece": full["ece"],
                    "candidate_ece": candidate["ece"],
                    "candidate_level_note": "candidate subset recomputed from full frame; candidate-level has range restriction",
                }
            )
    return pd.DataFrame(rows)


def interval_coverage_audit(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    closed = closed_eval_frame(frame)
    for keys, part in closed.groupby(["horizon", "cutoff_month"], dropna=False):
        horizon, cutoff = keys
        rows.append(interval_coverage_row(part, horizon, cutoff))
    for horizon, part in closed.groupby("horizon", dropna=False):
        rows.append(interval_coverage_row(part, horizon, "all_2024"))
    rows.append(interval_coverage_row(closed, "overall", "all_2024"))
    return pd.DataFrame(rows)


def interval_coverage_row(part: pd.DataFrame, horizon: Any, cutoff: Any) -> dict[str, Any]:
    score = safe_numeric(part, "interval_score")
    expected = safe_numeric(part, "expected_interval_months")
    purchase = safe_numeric(part, "purchase_count_asof_cutoff")
    available = score.notna()
    metrics = metric_dict(part, "interval_score", "interval_overdue_baseline", str(horizon))
    demand_dist = (
        safe_text(part, "demand_shape_label").value_counts(dropna=False).head(8).to_dict() if len(part) else {}
    )
    return {
        "horizon": horizon,
        "cutoff_month": cutoff,
        "full_universe_rows": int(len(part)),
        "interval_score_available_rows": int(available.sum()),
        "interval_score_available_rate": float(available.mean()) if len(part) else np.nan,
        "missing_expected_interval_count": int(expected.isna().sum()),
        "missing_purchase_count_count": int(purchase.isna().sum()),
        "history_insufficient_count": int(safe_text(part, "history_sufficiency_flag").eq("history_insufficient").sum()),
        "demand_shape_distribution": str(demand_dist),
        "interval_metric_auc_if_available": metrics["auc"],
        "interval_metric_pr_auc_if_available": metrics["pr_auc"],
        "interval_metric_ece_if_available": metrics["ece"],
    }


def top10_lift(df: pd.DataFrame, score_col: str) -> float:
    y_true, y_score = _as_binary_score(closed_eval_frame(df, score_col), "label_die_H", score_col)
    if len(y_true) == 0:
        return np.nan
    base = float(y_true.mean())
    if base <= 0:
        return np.nan
    k = max(1, int(math.ceil(len(y_true) * 0.10)))
    selected = y_true[np.argsort(-y_score)[:k]]
    return float(selected.mean() / base)


def gate_for_segment(row: dict[str, Any]) -> str:
    row_count = int(row.get("row_count", 0) or 0)
    pos = int(row.get("positive_count", 0) or 0)
    neg = int(row.get("negative_count", 0) or 0)
    auc = row.get("auc", np.nan)
    lift = row.get("lift_at_top_10pct", np.nan)
    ece = row.get("ece", np.nan)
    dim = str(row.get("segment_dimension", ""))
    val = str(row.get("segment_value", ""))
    horizon = str(row.get("horizon", ""))
    if row_count < 50 or pos == 0 or neg == 0 or (dim == "history_sufficiency_flag" and val == "history_insufficient"):
        return "hide_probability_data_insufficient"
    good = row_count >= 100 and ((not pd.isna(auc) and auc >= 0.62) or (not pd.isna(lift) and lift >= 1.3))
    calibrated = not pd.isna(ece) and ece <= 0.15
    unstable_short = dim == "demand_shape_label" and val in {"intermittent", "lumpy"} and horizon == "H3"
    if good and calibrated and not unstable_short:
        return "probability_allowed"
    return "observation_only"


def stable_segment_service_gate(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for horizon, horizon_part in frame.groupby("horizon", dropna=False):
        for dim in SERVICE_SEGMENT_DIMS:
            if dim not in horizon_part.columns:
                continue
            for value, part in horizon_part.groupby(dim, dropna=False):
                metrics = metric_dict(part, "churn_probability_H", "global_logistic_scorer", str(horizon))
                closed = closed_eval_frame(part, "churn_probability_H")
                row = {
                    "horizon": horizon,
                    "segment_dimension": dim,
                    "segment_value": "__MISSING__" if pd.isna(value) else str(value),
                    "row_count": metrics["row_count"],
                    "positive_count": int(safe_numeric(closed, "label_die_H").sum()) if len(closed) else 0,
                    "negative_count": int(len(closed) - safe_numeric(closed, "label_die_H").sum()) if len(closed) else 0,
                    "positive_rate": metrics["positive_rate"],
                    "auc": metrics["auc"],
                    "pr_auc_gain": metrics["pr_auc_gain"],
                    "ece": metrics["ece"],
                    "lift_at_top_10pct": top10_lift(part, "churn_probability_H"),
                    "interval_score_available_rate": float(safe_numeric(part, "interval_score").notna().mean()) if len(part) else np.nan,
                }
                row["service_gate"] = gate_for_segment(row)
                row["policy_note"] = policy_note_for_gate(row["service_gate"])
                rows.append(row)
    return pd.DataFrame(rows)


def policy_note_for_gate(gate: str) -> str:
    if gate == "probability_allowed":
        return "show churn_probability_H only with candidate/full-universe validation caveat"
    if gate == "observation_only":
        return "show risk band/evidence, not precise probability"
    return "show history insufficient or validation insufficient message"


def sample_false_negative_cases(frame: pd.DataFrame, limit: int = 200) -> pd.DataFrame:
    closed = closed_eval_frame(frame)
    work = closed[closed["label_die_H"].eq(1)].copy()
    if work.empty:
        return pd.DataFrame()
    low_rank = safe_numeric(work, "rank_probability_full_universe").gt(np.ceil(len(work) * 0.5))
    work = work[(~work["in_m1_candidate"].astype(bool)) | low_rank].copy()
    work["case_type"] = np.where(work["in_m1_candidate"].astype(bool), "candidate_low_rank_false_negative", "non_candidate_false_negative")
    work["error_hypothesis"] = np.where(
        work["in_m1_candidate"].astype(bool),
        "entered_candidate_pool_but_ranked_low",
        "m1_candidate_policy_missed_full_universe_die",
    )
    return case_sample_columns(work.sort_values(["in_m1_candidate", "recency_score"], ascending=[True, False]).head(limit))


def sample_false_positive_cases(frame: pd.DataFrame, limit: int = 200) -> pd.DataFrame:
    closed = closed_eval_frame(frame)
    work = closed[closed["label_die_H"].eq(0)].copy()
    if work.empty:
        return pd.DataFrame()
    high = work["in_m1_candidate"].astype(bool) | work["in_probability_topk"].astype(bool)
    work = work[high].copy()
    work["case_type"] = np.where(work["in_m1_candidate"].astype(bool), "m1_candidate_false_positive", "probability_topk_false_positive")
    work["error_hypothesis"] = "risk_signal_triggered_but_future_purchase_occurred_within_window"
    return case_sample_columns(work.sort_values(["in_m1_candidate", "churn_probability_H"], ascending=[False, False]).head(limit))


def case_sample_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    columns = [
        "case_type",
        "manufacturer_code",
        "hospital_code",
        "drug_group",
        "cutoff_month",
        "horizon",
        "label_die_H",
        "churn_probability_H",
        "recency_score",
        "frequency_decay_score",
        "interval_score",
        "in_m1_candidate",
        "candidate_selection_reason",
        "survival_state",
        "demand_shape_label",
        "history_sufficiency_flag",
        "error_hypothesis",
    ]
    for col in columns:
        if col not in out.columns:
            out[col] = np.nan
    return out[columns]


def md_table(df: pd.DataFrame, max_rows: int = 20) -> str:
    if df is None or df.empty:
        return "_No rows._"
    try:
        return df.head(max_rows).to_markdown(index=False, floatfmt=".4f")
    except Exception:
        return df.head(max_rows).to_string(index=False)


def output_audit_text(
    frame: pd.DataFrame,
    feature_rows: int,
    label_rows: int,
    score_status: dict[str, Any],
) -> str:
    closed = closed_eval_frame(frame)
    non_candidate = int((~closed["in_m1_candidate"].astype(bool)).sum()) if not closed.empty else 0
    reason_lines = str(score_status.get("reason", "")).splitlines()
    reason_preview = reason_lines[0][:300] if reason_lines else ""
    lines = [
        "# Full Universe Frame Audit",
        "",
        f"- feature table rows read: {feature_rows}",
        f"- label table rows read: {label_rows}",
        f"- full-universe recurring long rows: {len(frame)}",
        f"- closed label rows: {len(closed)}",
        f"- non-candidate closed rows: {non_candidate}",
        f"- horizons: {','.join(sorted(safe_text(frame, 'horizon').unique())) if len(frame) else ''}",
        f"- logistic score available: {str(score_status.get('available', False)).lower()}",
        f"- logistic prediction_source: {score_status.get('prediction_source', '')}",
        f"- logistic reproduction reason: {reason_preview}",
        "",
        "No formal model file was saved. 2024 labels were used only for evaluation, not for in-memory logistic fitting.",
    ]
    return "\n".join(lines)


def probability_policy_text(gate: pd.DataFrame) -> str:
    counts = gate["service_gate"].value_counts().to_dict() if not gate.empty else {}
    return "\n".join(
        [
            "# Probability Availability Policy",
            "",
            f"- probability_allowed segments: {counts.get('probability_allowed', 0)}",
            f"- observation_only segments: {counts.get('observation_only', 0)}",
            f"- hide_probability_data_insufficient segments: {counts.get('hide_probability_data_insufficient', 0)}",
            "",
            "## Display Rules",
            "1. Show `churn_probability_H` only for `probability_allowed` stable recurring segments.",
            "2. Show risk bands, rank, or interval evidence for `observation_only` segments.",
            "3. Show observation notes for lumpy/intermittent or interval-evidence-only rows unless their segment passes the probability gate.",
            "4. Show `历史不足，无法稳定预测` for `hide_probability_data_insufficient` rows.",
            "5. `relative_business_priority_score_H` is resource prioritization, not probability.",
            "6. detector severity/confidence and survival_confidence are evidence, not probability.",
            "7. interval overdue and survival-lite scores are ranking/evidence signals and need calibration before probability display.",
        ]
    )


def decision_text(
    metrics: pd.DataFrame,
    coverage: pd.DataFrame,
    candidate_compare: pd.DataFrame,
    interval_audit: pd.DataFrame,
    gate: pd.DataFrame,
) -> str:
    logistic = metrics[(metrics["scorer_name"] == "global_logistic_scorer") & (metrics["horizon"] == "overall")]
    recency = metrics[(metrics["scorer_name"] == "recency_only_baseline") & (metrics["horizon"] == "overall")]
    freq = metrics[(metrics["scorer_name"] == "frequency_decay_baseline") & (metrics["horizon"] == "overall")]
    interval = metrics[(metrics["scorer_name"] == "interval_overdue_baseline") & (metrics["horizon"] == "overall")]
    cov = coverage[(coverage["horizon"] == "overall") & (coverage["cutoff_month"] == "all_2024")]
    comp = candidate_compare[
        (candidate_compare["scorer_name"] == "global_logistic_scorer")
        & (candidate_compare["horizon"].isin(HORIZON_LABELS))
    ]
    gate_counts = gate["service_gate"].value_counts().to_dict() if not gate.empty else {}
    logistic_auc = metric_value(logistic, "auc")
    candidate_recall = metric_value(cov, "candidate_die_recall")
    non_candidate_die = int(metric_value(cov, "non_candidate_die_count") or 0) if not cov.empty else 0
    interval_auc = metric_value(interval, "auc")
    interval_coverage = metric_value(interval, "score_available_rate")
    interval_ece = metric_value(interval, "ece")
    recommendation = algorithm_recommendation(logistic_auc, candidate_recall, interval_auc, interval_coverage)
    return "\n".join(
        [
            "# Next Algorithm Decision",
            "",
            f"1. full-universe logistic AUC: {fmt(logistic_auc)}. Candidate-level vs full-universe AUC deltas by horizon:",
            md_table(comp[["horizon", "full_universe_auc", "candidate_level_auc", "auc_full_minus_candidate"]]),
            f"2. full-universe logistic PR-AUC gain: {fmt(metric_value(logistic, 'pr_auc_gain'))}.",
            f"3. full-universe logistic ECE: {fmt(metric_value(logistic, 'ece'))}.",
            f"4. candidate die recall: {fmt(candidate_recall)}.",
            f"5. non-candidate die count: {non_candidate_die}.",
            f"6. interval_overdue full-universe AUC: {fmt(interval_auc)}, coverage: {fmt(interval_coverage)}, ECE: {fmt(metric_value(interval, 'ece'))}.",
            f"7. recency AUC/gain/ECE: {fmt(metric_value(recency, 'auc'))} / {fmt(metric_value(recency, 'pr_auc_gain'))} / {fmt(metric_value(recency, 'ece'))}.",
            f"8. frequency AUC/gain/ECE: {fmt(metric_value(freq, 'auc'))} / {fmt(metric_value(freq, 'pr_auc_gain'))} / {fmt(metric_value(freq, 'ece'))}.",
            "9. Main route decision: use a hybrid interval-first ranking/evidence route, with logistic/frequency retained as benchmark and calibration input.",
            "10. Generate a full-universe interval feature table: yes, because interval signal is strongest but must stay as evidence until calibrated.",
            "11. Expand training cutoff: yes, through learning curves only; do not mix 2024 test labels into this research evaluation.",
            "12. Continue `logistic + frequency_decay_v1`: only as an internal full-universe first-pass benchmark, not as current M1 business-priority candidate policy.",
            f"13. stable service gate counts: {gate_counts}.",
            "",
            "## Decision",
            recommendation,
            "",
            "Interval ECE is "
            + fmt(interval_ece)
            + ", so interval_overdue is not probability-safe. Candidate recall is "
            + fmt(candidate_recall)
            + ", so the current M1 global-top5pct plus manufacturer-min-fill policy is not a coverage solution.",
            "",
            "## Required Next Algorithm Task",
            "Build a full-universe interval feature table and calibrated hybrid scorer: recency/frequency first-pass ranking, interval-overdue evidence, and probability availability gates. Re-run learning curves before any service final model.",
            "",
            "Frontend/backend decision: do not build customer-facing probability service. At most, build an internal diagnostic view after this algorithm decision is accepted.",
        ]
    )


def algorithm_recommendation(logistic_auc: float, candidate_recall: float, interval_auc: float, interval_coverage: float) -> str:
    if pd.notna(candidate_recall) and candidate_recall < 0.30:
        return (
            "Full-universe logistic ranking is usable as an internal first-pass signal, but the current M1 candidate policy "
            "does not cover enough die_H=1 rows. Rebuild candidate selection on full-universe scorer plus interval evidence before product work."
        )
    if pd.notna(logistic_auc) and logistic_auc >= 0.62 and pd.notna(candidate_recall) and candidate_recall >= 0.70:
        return "Keep logistic as a full-universe first-pass scorer, but use interval refinement inside candidate and stable segments."
    if pd.notna(logistic_auc) and logistic_auc < 0.58:
        return "Current logistic scorer is not suitable as a main probability service. Move toward interval/survival-first or hybrid recency-frequency + interval ranking."
    if pd.notna(interval_auc) and pd.notna(logistic_auc) and interval_auc >= logistic_auc + 0.03:
        return "Interval route is materially stronger for ranking. Use it as primary evidence after coverage and calibration work."
    if pd.notna(interval_coverage) and interval_coverage < 0.50:
        return "Interval signal is promising but coverage is insufficient; generate full-universe interval features before route replacement."
    return "Keep current scorer only as an internal benchmark; do not productize probability yet."


def metric_value(df: pd.DataFrame, column: str) -> float:
    if df is None or df.empty or column not in df.columns:
        return np.nan
    value = df[column].iloc[0]
    return float(value) if pd.notna(value) else np.nan


def fmt(value: Any) -> str:
    if pd.isna(value):
        return "nan"
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return str(value)


def summary_text(
    frame: pd.DataFrame,
    metrics: pd.DataFrame,
    coverage: pd.DataFrame,
    compare: pd.DataFrame,
    gate: pd.DataFrame,
) -> str:
    closed = closed_eval_frame(frame)
    cov = coverage[(coverage["horizon"] == "overall") & (coverage["cutoff_month"] == "all_2024")]
    logistic = metrics[(metrics["scorer_name"] == "global_logistic_scorer") & (metrics["horizon"] == "overall")]
    recency = metrics[(metrics["scorer_name"] == "recency_only_baseline") & (metrics["horizon"] == "overall")]
    freq = metrics[(metrics["scorer_name"] == "frequency_decay_baseline") & (metrics["horizon"] == "overall")]
    interval = metrics[(metrics["scorer_name"] == "interval_overdue_baseline") & (metrics["horizon"] == "overall")]
    gate_counts = gate["service_gate"].value_counts().to_dict() if not gate.empty else {}
    return "\n".join(
        [
            "# Full Universe Interval Backtest Summary",
            "",
            f"1. full-universe frame generated: {str(not frame.empty).lower()}",
            f"2. full-universe rows: {len(frame)}",
            f"3. closed label rows: {len(closed)}",
            f"4. non-candidate rows: {int((~closed['in_m1_candidate'].astype(bool)).sum()) if not closed.empty else 0}",
            f"5. candidate coverage rate: {fmt(metric_value(cov, 'candidate_coverage_rate'))}; candidate die recall: {fmt(metric_value(cov, 'candidate_die_recall'))}",
            f"6. candidate positive rate / non-candidate positive rate / lift: {fmt(metric_value(cov, 'candidate_positive_rate'))} / {fmt(metric_value(cov, 'non_candidate_positive_rate'))} / {fmt(metric_value(cov, 'candidate_lift_vs_non_candidate'))}",
            f"7. full-universe logistic AUC / PR-AUC gain / ECE: {fmt(metric_value(logistic, 'auc'))} / {fmt(metric_value(logistic, 'pr_auc_gain'))} / {fmt(metric_value(logistic, 'ece'))}",
            "8. candidate vs full-universe differences:",
            md_table(compare[compare["scorer_name"].eq("global_logistic_scorer")][["horizon", "full_universe_auc", "candidate_level_auc", "auc_full_minus_candidate"]]),
            f"9. recency baseline AUC / gain / ECE: {fmt(metric_value(recency, 'auc'))} / {fmt(metric_value(recency, 'pr_auc_gain'))} / {fmt(metric_value(recency, 'ece'))}",
            f"10. frequency baseline AUC / gain / ECE: {fmt(metric_value(freq, 'auc'))} / {fmt(metric_value(freq, 'pr_auc_gain'))} / {fmt(metric_value(freq, 'ece'))}",
            f"11. interval baseline AUC / gain / ECE / coverage: {fmt(metric_value(interval, 'auc'))} / {fmt(metric_value(interval, 'pr_auc_gain'))} / {fmt(metric_value(interval, 'ece'))} / {fmt(metric_value(interval, 'score_available_rate'))}",
            f"12. PR-AUC gain/lift conclusion: logistic gain {fmt(metric_value(logistic, 'pr_auc_gain'))}, lift {fmt(metric_value(logistic, 'pr_auc_lift'))}; compare against positive_rate before claiming value.",
            f"13. ECE conclusion: logistic ECE {fmt(metric_value(logistic, 'ece'))}; interval/recency/frequency scores are not probability-safe even if ranking is strong.",
            f"14. stable service gate: {gate_counts}",
            "15. frontend/backend recommendation: no customer-facing probability service; internal diagnostic view only if needed.",
            "16. next algorithm recommendation: full-universe interval feature coverage + calibrated hybrid scorer + learning curve.",
        ]
    )


def load_optional_artifacts(root: Path) -> dict[str, pd.DataFrame]:
    reports = root / "reports"
    return {
        "candidate_by_horizon": read_csv_or_empty(
            reports / "alive_prediction_candidate_pool_v1/recurring_business_priority_candidates_by_horizon.csv"
        ),
        "status": read_csv_or_empty(reports / "alive_prediction_status_decision_v1/candidate_status_decision.csv"),
        "detector_v2": read_csv_or_empty(reports / "alive_prediction_detectors_v2/detector_frequency_rate_test_results.csv"),
    }


def build_scored_full_frame(root: Path, *, dry_run: bool = False) -> tuple[pd.DataFrame, dict[str, Any], dict[str, int]]:
    if dry_run:
        features, labels, candidates, status, detector = dry_run_inputs()
    else:
        features, labels = load_full_universe_inputs(root)
        optional = load_optional_artifacts(root)
        candidates = optional["candidate_by_horizon"]
        status = optional["status"]
        detector = optional["detector_v2"]
    frame = build_full_universe_frame(features, labels)
    if frame.empty:
        return frame, {"available": False, "reason": "feature_or_label_input_missing"}, {
            "feature_rows": len(features),
            "label_rows": len(labels),
        }
    if dry_run:
        score_status = {
            "available": True,
            "prediction_source": "dry_run_in_memory_fixture",
            "reason": "",
            "trained_formal_model": False,
            "saved_model_file": False,
        }
        score_rows = frame[[*KEY_COLS, "horizon"]].copy()
        score_rows["churn_probability_H"] = np.clip(
            0.15 + 0.7 * recency_score(frame).fillna(0.0), EPS, 1 - EPS
        )
    else:
        score_rows, score_status = reproduce_logistic_probability_scores(root)
    frame = attach_logistic_scores(frame, score_rows, score_status)
    frame = attach_candidates(frame, candidates)
    frame = attach_status(frame, status)
    frame = attach_d002(frame, detector)
    frame = add_baseline_scores(frame)
    return frame, score_status, {"feature_rows": len(features), "label_rows": len(labels)}


def run_full_universe_interval_backtest(
    root: Path,
    output_dir: Path,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    frame, score_status, input_counts = build_scored_full_frame(root, dry_run=dry_run)
    output_dir.mkdir(parents=True, exist_ok=True)
    if not frame.empty:
        try:
            frame.to_parquet(output_dir / "full_universe_recurring_backtest_frame.parquet", index=False)
        except Exception:
            write_csv(output_dir / "full_universe_recurring_backtest_frame.csv", frame)
    write_csv(output_dir / "full_universe_recurring_backtest_frame_sample.csv", frame.head(500))

    if frame.empty:
        empty = pd.DataFrame()
        for name in [
            "full_universe_metric_summary.csv",
            "full_universe_topk_metrics.csv",
            "candidate_coverage_metrics.csv",
            "candidate_vs_full_universe_metrics.csv",
            "baseline_comparison_full_universe.csv",
            "interval_baseline_coverage_audit.csv",
            "stable_segment_service_gate.csv",
            "full_universe_false_negative_cases_sample.csv",
            "full_universe_false_positive_cases_sample.csv",
        ]:
            write_csv(output_dir / name, empty)
        write_text(
            output_dir / "full_universe_frame_audit.md",
            output_audit_text(frame, input_counts["feature_rows"], input_counts["label_rows"], score_status),
        )
        write_text(output_dir / "probability_availability_policy.md", probability_policy_text(empty))
        write_text(
            output_dir / "next_algorithm_decision.md",
            "# Next Algorithm Decision\n\nFull-universe frame was not generated because required feature/label inputs were missing.\n",
        )
        write_text(
            output_dir / "full_universe_interval_backtest_summary.md",
            "# Full Universe Interval Backtest Summary\n\nfull-universe frame generated: false\n",
        )
        return {
            "frame": frame,
            "metrics": empty,
            "topk": empty,
            "coverage": empty,
            "candidate_vs_full": empty,
            "interval_audit": empty,
            "gate": empty,
            "false_negative_sample": empty,
            "false_positive_sample": empty,
            "score_status": score_status,
            "output_dir": str(output_dir),
        }

    metrics = full_universe_metric_summary(frame) if not frame.empty else pd.DataFrame()
    topk = full_universe_topk_metrics(frame) if not frame.empty else pd.DataFrame()
    coverage = candidate_coverage_metrics(frame) if not frame.empty else pd.DataFrame()
    compare = candidate_vs_full_universe_metrics(frame) if not frame.empty else pd.DataFrame()
    interval_audit = interval_coverage_audit(frame) if not frame.empty else pd.DataFrame()
    gate = stable_segment_service_gate(frame) if not frame.empty else pd.DataFrame()
    fn = sample_false_negative_cases(frame)
    fp = sample_false_positive_cases(frame)

    write_csv(output_dir / "full_universe_metric_summary.csv", metrics)
    write_csv(output_dir / "full_universe_topk_metrics.csv", topk)
    write_csv(output_dir / "candidate_coverage_metrics.csv", coverage)
    write_csv(output_dir / "candidate_vs_full_universe_metrics.csv", compare)
    write_csv(output_dir / "baseline_comparison_full_universe.csv", metrics)
    write_csv(output_dir / "interval_baseline_coverage_audit.csv", interval_audit)
    write_csv(output_dir / "stable_segment_service_gate.csv", gate)
    write_csv(output_dir / "full_universe_false_negative_cases_sample.csv", fn)
    write_csv(output_dir / "full_universe_false_positive_cases_sample.csv", fp)

    write_text(
        output_dir / "full_universe_frame_audit.md",
        output_audit_text(frame, input_counts["feature_rows"], input_counts["label_rows"], score_status),
    )
    write_text(output_dir / "probability_availability_policy.md", probability_policy_text(gate))
    write_text(output_dir / "next_algorithm_decision.md", decision_text(metrics, coverage, compare, interval_audit, gate))
    write_text(output_dir / "full_universe_interval_backtest_summary.md", summary_text(frame, metrics, coverage, compare, gate))

    return {
        "frame": frame,
        "metrics": metrics,
        "topk": topk,
        "coverage": coverage,
        "candidate_vs_full": compare,
        "interval_audit": interval_audit,
        "gate": gate,
        "false_negative_sample": fn,
        "false_positive_sample": fp,
        "score_status": score_status,
        "output_dir": str(output_dir),
    }


def dry_run_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = [
        ("m1", "h1", "d1", "2024-01", 6, 4, 24, 4, 1, 4, 3.0, 24.0, 90.0, 10.0, 0.4, 0.1, "p1", "L1", "c1"),
        ("m1", "h2", "d1", "2024-01", 6, 4, 24, 0, 0, 6, 8.0, 24.0, 90.0, 10.0, 0.4, 0.1, "p1", "L1", "c1"),
        ("m2", "h3", "d2", "2024-02", 3, 2, 12, 0, 1, 12, 12.0, 12.0, 120.0, 90.0, 2.0, 0.2, "p2", "L2", "c2"),
        ("m2", "h4", "d2", "2024-02", 3, 2, 12, 1, 3, 1, 1.0, 12.0, np.nan, np.nan, np.nan, np.nan, "p2", "L2", "c2"),
    ]
    features = pd.DataFrame(
        rows,
        columns=[
            "manufacturer_code",
            "hospital_code",
            "drug_group",
            "cutoff_month",
            "purchase_count_asof_cutoff",
            "active_month_count_asof_cutoff",
            "months_observed_asof_cutoff",
            "order_count_last_3m_asof_cutoff",
            "order_count_last_6m_asof_cutoff",
            "order_count_last_12m_asof_cutoff",
            "months_since_last_purchase_asof_cutoff",
            "months_since_first_purchase_asof_cutoff",
            "median_purchase_interval_days_asof_cutoff",
            "std_purchase_interval_days_asof_cutoff",
            "adi_asof_cutoff",
            "cv2_quantity_asof_cutoff",
            "province_code",
            "hospital_level_code",
            "drug_category_code",
        ],
    )
    for horizon in HORIZONS:
        features[f"value_at_risk_amount_nonnegative_H{horizon}_asof_cutoff"] = 100.0 * horizon
    labels = features[["manufacturer_code", "hospital_code", "drug_group", "cutoff_month"]].copy()
    labels["label_alive_H3"] = [0, 1, 0, 1]
    labels["label_die_H3"] = [1, 0, 1, 0]
    labels["label_alive_H6"] = [0, 1, 0, 1]
    labels["label_die_H6"] = [1, 0, 1, 0]
    labels["label_alive_H12"] = [0, 1, 0, 1]
    labels["label_die_H12"] = [1, 0, 1, 0]
    candidates = pd.DataFrame(
        {
            "manufacturer_code": ["m1", "m2"],
            "hospital_code": ["h1", "h3"],
            "drug_group": ["d1", "d2"],
            "drug_group_source": ["drug_code", "drug_code"],
            "cutoff_month": ["2024-01", "2024-02"],
            "horizon": [3, 6],
            "selection_reason": ["global_top5pct", "manufacturer_min_fill"],
            "rank_global": [1, 2],
        }
    )
    status = pd.DataFrame()
    detector = pd.DataFrame()
    return features, labels, candidates, status, detector
