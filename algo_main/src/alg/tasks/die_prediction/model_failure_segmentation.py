"""Model failure segmentation and alternative baseline diagnostics.

This module is report-only. It reads existing alive-prediction artifacts and
writes diagnostic reports. It does not train models, tune thresholds, save
model files, call LLMs, or modify upstream M1-M7 outputs.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
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


ENTITY_COLS = ["manufacturer_code", "hospital_code", "drug_group", "drug_group_source"]
JOIN_COLS = ["manufacturer_code", "hospital_code", "drug_group", "drug_group_source", "cutoff_month"]
SEGMENT_DIMENSIONS = [
    "horizon",
    "cutoff_month",
    "cutoff_period_2024",
    "manufacturer_code",
    "hospital_level_code",
    "province_code",
    "drug_category_code",
    "demand_shape_label",
    "demand_shape_route",
    "history_sufficiency_flag",
    "purchase_count_bucket",
    "active_month_count_bucket",
    "months_observed_bucket",
    "months_since_last_purchase_bucket",
    "months_since_first_purchase_bucket",
    "survival_state",
    "final_candidate_status",
    "d002_hit_segment",
]
OUTPUT_FILES = [
    "model_failure_segmentation_summary.md",
    "segment_metric_matrix.csv",
    "segment_metric_matrix_by_horizon.csv",
    "stable_service_scope_recommendation.md",
    "bad_segment_diagnosis.md",
    "pr_auc_ece_diagnosis.md",
    "candidate_vs_full_universe_gap.md",
    "alternative_baseline_comparison.csv",
    "survival_baseline_feasibility.md",
    "next_model_action_decision.md",
]


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


def normalize_cutoff_month(series: pd.Series) -> pd.Series:
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


def normalize_horizon_num(value: Any) -> float:
    if pd.isna(value):
        return np.nan
    text = str(value).strip().upper()
    if text.startswith("H"):
        text = text[1:]
    try:
        return float(text)
    except ValueError:
        return np.nan


def ensure_drug_group_source(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "drug_group_source" not in out.columns:
        out["drug_group_source"] = "drug_code"
    return out


def entity_id(df: pd.DataFrame) -> pd.Series:
    cols = [c for c in ENTITY_COLS if c in df.columns]
    if not cols:
        return pd.Series(np.arange(len(df)).astype(str), index=df.index)
    return df[cols].fillna("__MISSING__").astype(str).agg("|".join, axis=1)


def _safe_numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype="float64")
    values = frame[column]
    if isinstance(values, pd.DataFrame):
        values = values.iloc[:, 0]
    return pd.to_numeric(values, errors="coerce")


def _safe_text(frame: pd.DataFrame, column: str, fill: str = "__MISSING__") -> pd.Series:
    if column not in frame.columns:
        return pd.Series(fill, index=frame.index, dtype="object")
    values = frame[column]
    if isinstance(values, pd.DataFrame):
        values = values.iloc[:, 0]
    return values.fillna(fill).astype(str)


def bucket_numeric(values: pd.Series, kind: str) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    if kind == "purchase_count":
        bins = [-np.inf, 2, 4, 9, np.inf]
        labels = ["lt3", "3_4", "5_9", "ge10"]
    elif kind == "active_month_count":
        bins = [-np.inf, 1, 2, 5, np.inf]
        labels = ["lt2", "2", "3_5", "ge6"]
    elif kind == "months_observed":
        bins = [-np.inf, 5, 11, 23, 47, np.inf]
        labels = ["lt6", "6_11", "12_23", "24_47", "ge48"]
    elif kind == "months_since_last_purchase":
        bins = [-np.inf, 0, 2, 5, 11, np.inf]
        labels = ["0", "1_2", "3_5", "6_11", "ge12"]
    elif kind == "months_since_first_purchase":
        bins = [-np.inf, 5, 11, 23, 47, np.inf]
        labels = ["lt6", "6_11", "12_23", "24_47", "ge48"]
    else:
        raise ValueError(f"unknown bucket kind: {kind}")
    out = pd.cut(numeric, bins=bins, labels=labels).astype("object")
    return out.fillna("missing")


def cutoff_period_2024(series: pd.Series) -> pd.Series:
    month = pd.to_datetime(series, errors="coerce").dt.month
    out = pd.Series("outside_2024_or_missing", index=series.index, dtype="object")
    out.loc[month.between(1, 4)] = "early_2024"
    out.loc[month.between(5, 8)] = "mid_2024"
    out.loc[month.between(9, 12)] = "late_2024"
    return out


def _prepare_key_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = ensure_drug_group_source(df)
    if "cutoff_month" in out.columns:
        out["cutoff_month"] = normalize_cutoff_month(out["cutoff_month"])
    if "horizon" in out.columns:
        out["horizon"] = out["horizon"].map(normalize_horizon_label)
        out["horizon_num"] = out["horizon"].map(normalize_horizon_num)
    return out


def feature_columns() -> list[str]:
    return [
        "manufacturer_code",
        "hospital_code",
        "drug_group",
        "cutoff_month",
        "months_since_last_purchase",
        "purchase_count_asof_cutoff",
        "active_month_count_asof_cutoff",
        "months_observed_asof_cutoff",
        "months_since_first_purchase_asof_cutoff",
        "months_since_last_purchase_asof_cutoff",
        "order_count_last_3m_asof_cutoff",
        "order_count_last_12m_asof_cutoff",
        "province_code",
        "hospital_level_code",
        "drug_category_code",
        "median_purchase_interval_days_asof_cutoff",
        "demand_pattern_type_asof_cutoff",
    ]


def find_feature_table(root: Path) -> Path | None:
    preferred = (
        root
        / "data/05_features/alive_prediction/v1_drug_code_monitorable_gap12/"
        / "cutoff_2024-01_2024-12/feature_table__status0.parquet"
    )
    if preferred.exists():
        return preferred
    candidates = sorted((root / "data/05_features/alive_prediction").rglob("feature_table__status0.parquet"))
    return candidates[-1] if candidates else None


def load_optional_feature_table(root: Path) -> pd.DataFrame:
    path = find_feature_table(root)
    if path is None:
        return pd.DataFrame()
    df = read_parquet_or_empty(path, columns=feature_columns())
    if df.empty:
        return pd.DataFrame()
    df = _prepare_key_columns(df)
    df["feature_table_source"] = str(path.relative_to(root))
    return df


def prepare_history_flags(history: pd.DataFrame) -> pd.DataFrame:
    if history.empty:
        return history
    out = _prepare_key_columns(history)
    keep = [
        *JOIN_COLS,
        "horizon",
        "purchase_count_asof_cutoff",
        "active_month_count_asof_cutoff",
        "months_observed_asof_cutoff",
        "history_sufficiency_flag",
        "history_sufficiency_reason",
    ]
    keep = [c for c in keep if c in out.columns]
    return out[keep].drop_duplicates([c for c in [*JOIN_COLS, "horizon"] if c in keep])


def prepare_survival(survival: pd.DataFrame) -> pd.DataFrame:
    if survival.empty:
        return survival
    out = _prepare_key_columns(survival)
    keep = [
        *JOIN_COLS,
        "horizon",
        "survival_state",
        "demand_shape_route",
        "history_sufficiency_flag",
        "months_since_last_purchase",
        "overdue_ratio",
        "expected_interval_months",
        "data_quality_note",
    ]
    keep = [c for c in keep if c in out.columns]
    return out[keep].drop_duplicates([c for c in [*JOIN_COLS, "horizon"] if c in keep])


def prepare_feature_table(features: pd.DataFrame) -> pd.DataFrame:
    if features.empty:
        return features
    out = _prepare_key_columns(features)
    keep = [
        *JOIN_COLS,
        "months_since_last_purchase",
        "months_since_last_purchase_asof_cutoff",
        "months_since_first_purchase_asof_cutoff",
        "purchase_count_asof_cutoff",
        "active_month_count_asof_cutoff",
        "months_observed_asof_cutoff",
        "order_count_last_3m_asof_cutoff",
        "order_count_last_12m_asof_cutoff",
        "province_code",
        "hospital_level_code",
        "drug_category_code",
        "median_purchase_interval_days_asof_cutoff",
        "demand_pattern_type_asof_cutoff",
        "feature_table_source",
    ]
    keep = [c for c in keep if c in out.columns]
    return out[keep].drop_duplicates([c for c in JOIN_COLS if c in keep])


def prepare_d002_detector(detector: pd.DataFrame) -> pd.DataFrame:
    if detector.empty or "detector_name" not in detector.columns:
        return pd.DataFrame(columns=[*JOIN_COLS, "horizon", "d002_hit_flag", "d002_data_quality_note"])
    work = _prepare_key_columns(detector)
    work = work[work["detector_name"].astype(str).eq("purchase_frequency_decay_rate_test")].copy()
    if work.empty:
        return pd.DataFrame(columns=[*JOIN_COLS, "horizon", "d002_hit_flag", "d002_data_quality_note"])
    work["hit_flag_numeric"] = work.get("hit_flag", False).fillna(False).astype(bool).astype(int)
    group_cols = [c for c in [*JOIN_COLS, "horizon"] if c in work.columns]
    out = (
        work.groupby(group_cols, dropna=False)
        .agg(
            d002_hit_flag=("hit_flag_numeric", "max"),
            d002_data_quality_note=("data_quality_note", lambda s: ";".join(sorted(set(s.dropna().astype(str).head(3))))),
        )
        .reset_index()
    )
    out["d002_hit_flag"] = out["d002_hit_flag"].astype(bool)
    return out


def enrich_recurring_frame(
    recurring: pd.DataFrame,
    *,
    history_flags: pd.DataFrame | None = None,
    survival: pd.DataFrame | None = None,
    detector: pd.DataFrame | None = None,
    features: pd.DataFrame | None = None,
) -> pd.DataFrame:
    out = _prepare_key_columns(recurring)
    if "label_window_closed" in out.columns:
        out = out[out["label_window_closed"].astype(bool)].copy()
    if "label_die_H" in out.columns:
        out = out[out["label_die_H"].notna()].copy()
        out["label_die_H"] = out["label_die_H"].astype(int)

    for source in [
        prepare_history_flags(history_flags if history_flags is not None else pd.DataFrame()),
        prepare_survival(survival if survival is not None else pd.DataFrame()),
        prepare_feature_table(features if features is not None else pd.DataFrame()),
        prepare_d002_detector(detector if detector is not None else pd.DataFrame()),
    ]:
        if source.empty:
            continue
        merge_cols = [c for c in [*JOIN_COLS, "horizon"] if c in out.columns and c in source.columns]
        if "horizon" not in source.columns:
            merge_cols = [c for c in JOIN_COLS if c in out.columns and c in source.columns]
        if not merge_cols:
            continue
        overlap = [c for c in source.columns if c in out.columns and c not in merge_cols]
        renamed = source.rename(columns={c: f"{c}__source" for c in overlap})
        out = out.merge(renamed, on=merge_cols, how="left")
        for col in overlap:
            source_col = f"{col}__source"
            if source_col in out.columns:
                out[col] = out[col].where(out[col].notna(), out[source_col])
                out = out.drop(columns=[source_col])

    out["entity_id"] = entity_id(out)
    out["cutoff_period_2024"] = cutoff_period_2024(out.get("cutoff_month", pd.Series(index=out.index, dtype="object")))

    if "demand_shape_label" not in out.columns:
        out["demand_shape_label"] = out.get("demand_pattern_type_asof_cutoff", "__MISSING__")
    out["demand_shape_label"] = _safe_text(out, "demand_shape_label")
    out["demand_shape_route"] = _safe_text(out, "demand_shape_route", fill="route_not_available")
    out["history_sufficiency_flag"] = _safe_text(out, "history_sufficiency_flag", fill="history_not_available")
    out["survival_state"] = _safe_text(out, "survival_state", fill="survival_not_available")
    out["final_candidate_status"] = _safe_text(out, "final_candidate_status", fill="status_not_available")

    for col in ["hospital_level_code", "province_code", "drug_category_code"]:
        out[col] = _safe_text(out, col, fill=f"{col}_not_available")

    out["purchase_count_bucket"] = bucket_numeric(_safe_numeric(out, "purchase_count_asof_cutoff"), "purchase_count")
    out["active_month_count_bucket"] = bucket_numeric(
        _safe_numeric(out, "active_month_count_asof_cutoff"), "active_month_count"
    )
    out["months_observed_bucket"] = bucket_numeric(_safe_numeric(out, "months_observed_asof_cutoff"), "months_observed")
    last = _safe_numeric(out, "months_since_last_purchase_asof_cutoff").fillna(
        _safe_numeric(out, "months_since_last_purchase")
    )
    out["months_since_last_purchase_effective"] = last
    out["months_since_last_purchase_bucket"] = bucket_numeric(last, "months_since_last_purchase")
    out["months_since_first_purchase_bucket"] = bucket_numeric(
        _safe_numeric(out, "months_since_first_purchase_asof_cutoff"), "months_since_first_purchase"
    )
    if "d002_hit_flag" in out.columns:
        d002_available = out["d002_hit_flag"].notna()
        d002_hit = out["d002_hit_flag"].eq(True)
        out["d002_hit_segment"] = np.where(d002_hit, "d002_hit", "d002_non_hit")
        out.loc[~d002_available, "d002_hit_segment"] = "d002_not_available"
    else:
        out["d002_hit_segment"] = "d002_not_available"
    out["data_quality_note_enriched"] = build_data_quality_note(out)
    return out.reset_index(drop=True)


def build_data_quality_note(df: pd.DataFrame) -> pd.Series:
    notes = pd.Series("", index=df.index, dtype="object")
    for col in ["hospital_level_code", "province_code", "drug_category_code"]:
        marker = f"{col}_not_available"
        notes.loc[_safe_text(df, col).eq(marker)] = (notes + f";missing_{col}").str.strip(";")
    notes.loc[_safe_text(df, "history_sufficiency_flag").eq("history_not_available")] = (
        notes + ";missing_history_sufficiency_flag"
    ).str.strip(";")
    notes.loc[_safe_text(df, "demand_shape_route").eq("route_not_available")] = (
        notes + ";missing_demand_shape_route"
    ).str.strip(";")
    return notes.replace("", "ok")


def _as_binary_and_score(df: pd.DataFrame, label_col: str, score_col: str) -> tuple[np.ndarray, np.ndarray]:
    if df.empty or label_col not in df.columns or score_col not in df.columns:
        return np.array([], dtype=int), np.array([], dtype=float)
    valid = df[[label_col, score_col]].copy()
    valid[label_col] = pd.to_numeric(valid[label_col], errors="coerce")
    valid[score_col] = pd.to_numeric(valid[score_col], errors="coerce")
    valid = valid.dropna()
    if valid.empty:
        return np.array([], dtype=int), np.array([], dtype=float)
    y_true = valid[label_col].astype(int).to_numpy()
    y_score = np.clip(valid[score_col].to_numpy(dtype=float), 1e-9, 1 - 1e-9)
    return y_true, y_score


def top10_metrics(y_true: np.ndarray, y_score: np.ndarray) -> tuple[float, float, float]:
    if len(y_true) == 0:
        return np.nan, np.nan, np.nan
    base_rate = float(y_true.mean())
    order = np.argsort(-y_score)
    y_sorted = y_true[order]
    k = max(1, int(math.ceil(len(y_sorted) * 0.10)))
    selected = y_sorted[:k]
    precision = float(selected.mean()) if k else np.nan
    lift = float(precision / base_rate) if base_rate > 0 and not pd.isna(precision) else np.nan
    return precision, lift, ndcg_at_k(y_sorted, k)


def segment_metric_dict(
    df: pd.DataFrame,
    *,
    segment_dimension: str,
    segment_value: Any,
    horizon: Any = "all",
    label_col: str = "label_die_H",
    score_col: str = "churn_probability_H",
) -> dict[str, Any]:
    y_true, y_score = _as_binary_and_score(df, label_col, score_col)
    row_count = int(len(y_true))
    entity_count = int(entity_id(df.loc[df.index]).nunique()) if not df.empty else 0
    positive_count = int(y_true.sum()) if row_count else 0
    negative_count = int(row_count - positive_count)
    positive_rate = float(y_true.mean()) if row_count else np.nan
    auc = roc_auc_score_simple(y_true, y_score) if row_count and positive_count and negative_count else np.nan
    pr_auc = average_precision_score_simple(y_true, y_score) if row_count and positive_count else np.nan
    precision, lift, ndcg = top10_metrics(y_true, y_score)
    pr_lift = float(pr_auc / positive_rate) if positive_rate and not pd.isna(pr_auc) else np.nan
    note_parts = []
    if row_count < 2 or positive_count == 0 or negative_count == 0:
        note_parts.append("single_class_or_too_few_samples")
    if "data_quality_note_enriched" in df.columns:
        top_notes = [x for x in df["data_quality_note_enriched"].dropna().astype(str).unique().tolist() if x != "ok"]
        if top_notes:
            note_parts.extend(top_notes[:3])
    note_tokens: list[str] = []
    for note in note_parts:
        note_tokens.extend([part for part in str(note).split(";") if part])
    row = {
        "horizon": horizon,
        "segment_dimension": segment_dimension,
        "segment_value": "__MISSING__" if pd.isna(segment_value) else str(segment_value),
        "row_count": row_count,
        "entity_count": entity_count,
        "positive_count": positive_count,
        "negative_count": negative_count,
        "positive_rate": positive_rate,
        "auc": auc,
        "pr_auc": pr_auc,
        "pr_auc_baseline": positive_rate,
        "pr_auc_gain": pr_auc - positive_rate if not pd.isna(pr_auc) and not pd.isna(positive_rate) else np.nan,
        "pr_auc_lift": pr_lift,
        "brier": brier_score(y_true, y_score) if row_count else np.nan,
        "logloss": log_loss_score(y_true, y_score) if row_count else np.nan,
        "ece": expected_calibration_error(y_true, y_score) if row_count else np.nan,
        "precision_at_top_10pct": precision,
        "lift_at_top_10pct": lift,
        "ndcg_at_top_10pct": ndcg,
        "avg_churn_probability": float(np.mean(y_score)) if row_count else np.nan,
        "avg_relative_business_priority_score": float(_safe_numeric(df, "relative_business_priority_score_H").mean())
        if not df.empty
        else np.nan,
        "data_quality_note": ";".join(dict.fromkeys(note_tokens)) if note_tokens else "ok",
    }
    flags = classify_segment(row)
    row.update(flags)
    return row


def classify_segment(row: dict[str, Any] | pd.Series) -> dict[str, bool]:
    get = row.get if isinstance(row, dict) else row.get
    row_count = int(get("row_count", 0) or 0)
    positive_count = int(get("positive_count", 0) or 0)
    negative_count = int(get("negative_count", 0) or 0)
    auc = get("auc", np.nan)
    lift = get("lift_at_top_10pct", np.nan)
    ece = get("ece", np.nan)
    gain = get("pr_auc_gain", np.nan)
    dimension = str(get("segment_dimension", ""))
    value = str(get("segment_value", ""))
    horizon = str(get("horizon", ""))

    has_two_classes = positive_count > 0 and negative_count > 0
    good = (
        row_count >= 100
        and has_two_classes
        and ((not pd.isna(auc) and auc >= 0.62) or (not pd.isna(lift) and lift >= 1.3))
        and (not pd.isna(ece) and ece <= 0.15)
        and (not pd.isna(gain) and gain > 0)
    )
    weak = row_count >= 100 and (
        ((not pd.isna(auc) and auc < 0.58) and (not pd.isna(lift) and lift <= 1.1))
        or (not pd.isna(ece) and ece > 0.20)
    )
    h3_lumpy_or_intermittent_poor = (
        dimension == "demand_shape_label"
        and value in {"intermittent", "lumpy"}
        and horizon == "H3"
        and ((not pd.isna(auc) and auc < 0.58) or (not pd.isna(lift) and lift <= 1.1))
    )
    not_predictable = (
        row_count < 50
        or not has_two_classes
        or (dimension == "history_sufficiency_flag" and value == "history_insufficient")
        or h3_lumpy_or_intermittent_poor
    )
    return {
        "good_segment": bool(good),
        "weak_segment": bool(weak),
        "not_predictable_segment": bool(not_predictable),
    }


def build_segment_metric_matrix(df: pd.DataFrame, dimensions: list[str] | None = None) -> pd.DataFrame:
    dims = dimensions or SEGMENT_DIMENSIONS
    rows = [segment_metric_dict(df, segment_dimension="overall", segment_value="all", horizon="all")]
    for dim in dims:
        if dim not in df.columns:
            continue
        values = _safe_text(df, dim)
        for value, part_idx in values.groupby(values, dropna=False).groups.items():
            part = df.loc[part_idx]
            rows.append(segment_metric_dict(part, segment_dimension=dim, segment_value=value, horizon="all"))
    return pd.DataFrame(rows)


def build_segment_metric_matrix_by_horizon(df: pd.DataFrame, dimensions: list[str] | None = None) -> pd.DataFrame:
    dims = [d for d in (dimensions or SEGMENT_DIMENSIONS) if d != "horizon"]
    rows: list[dict[str, Any]] = []
    if "horizon" not in df.columns:
        return pd.DataFrame()
    for horizon, horizon_part in df.groupby("horizon", dropna=False):
        rows.append(segment_metric_dict(horizon_part, segment_dimension="overall", segment_value="all", horizon=horizon))
        for dim in dims:
            if dim not in horizon_part.columns:
                continue
            values = _safe_text(horizon_part, dim)
            for value, part_idx in values.groupby(values, dropna=False).groups.items():
                rows.append(segment_metric_dict(horizon_part.loc[part_idx], segment_dimension=dim, segment_value=value, horizon=horizon))
    return pd.DataFrame(rows)


def normalize_score(values: pd.Series, higher_is_risk: bool = True) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    if not higher_is_risk:
        numeric = -numeric
    if numeric.notna().sum() == 0:
        return numeric
    lo = numeric.min(skipna=True)
    hi = numeric.max(skipna=True)
    if pd.isna(lo) or pd.isna(hi) or hi == lo:
        return pd.Series(0.5, index=numeric.index, dtype="float64").where(numeric.notna(), np.nan)
    return ((numeric - lo) / (hi - lo)).clip(0, 1)


def add_alternative_baseline_scores(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["global_logistic_scorer"] = _safe_numeric(out, "churn_probability_H").clip(1e-9, 1 - 1e-9)

    recency = _safe_numeric(out, "months_since_last_purchase_effective")
    out["recency_only_baseline"] = normalize_score(recency, higher_is_risk=True)

    if "frequency_decay_3m_vs_12m" in out.columns:
        out["frequency_decay_baseline"] = normalize_score(1 - _safe_numeric(out, "frequency_decay_3m_vs_12m"))
    else:
        order3 = _safe_numeric(out, "order_count_last_3m_asof_cutoff")
        order12 = _safe_numeric(out, "order_count_last_12m_asof_cutoff")
        recent_rate = order3 / 3.0
        annual_rate = order12 / 12.0
        ratio = recent_rate / annual_rate.replace(0, np.nan)
        out["frequency_decay_3m_vs_12m_proxy"] = ratio
        out["frequency_decay_baseline"] = (1 - ratio.clip(upper=1)).clip(0, 1)

    overdue = _safe_numeric(out, "overdue_ratio")
    out["interval_overdue_baseline"] = (overdue / (1 + overdue)).clip(0, 1)
    out.loc[overdue.isna(), "interval_overdue_baseline"] = np.nan

    out["empirical_hazard_bucket_key"] = (
        _safe_text(out, "months_since_last_purchase_bucket")
        + "|"
        + _safe_text(out, "purchase_count_bucket")
        + "|"
        + _safe_text(out, "demand_shape_label")
    )
    out["empirical_hazard_bucket_baseline"] = np.nan
    return out


def score_metric_row(df: pd.DataFrame, score_col: str, baseline_name: str, note: str = "") -> dict[str, Any]:
    y_true, y_score = _as_binary_and_score(df, "label_die_H", score_col)
    row_count = int(len(y_true))
    pos = int(y_true.sum()) if row_count else 0
    neg = row_count - pos
    precision, lift, ndcg = top10_metrics(y_true, y_score)
    positive_rate = float(y_true.mean()) if row_count else np.nan
    pr_auc = average_precision_score_simple(y_true, y_score) if row_count and pos else np.nan
    return {
        "baseline_name": baseline_name,
        "row_count": row_count,
        "positive_rate": positive_rate,
        "score_available_rate": float(pd.to_numeric(df.get(score_col, pd.Series(index=df.index)), errors="coerce").notna().mean())
        if len(df)
        else np.nan,
        "auc": roc_auc_score_simple(y_true, y_score) if row_count and pos and neg else np.nan,
        "pr_auc": pr_auc,
        "pr_auc_baseline": positive_rate,
        "pr_auc_gain": pr_auc - positive_rate if not pd.isna(pr_auc) and not pd.isna(positive_rate) else np.nan,
        "pr_auc_lift": pr_auc / positive_rate if positive_rate and not pd.isna(pr_auc) else np.nan,
        "brier": brier_score(y_true, y_score) if row_count else np.nan,
        "logloss": log_loss_score(y_true, y_score) if row_count else np.nan,
        "ece": expected_calibration_error(y_true, y_score) if row_count else np.nan,
        "precision_at_top_10pct": precision,
        "lift_at_top_10pct": lift,
        "ndcg_at_top_10pct": ndcg,
        "candidate_level_only": True,
        "trained_formal_model": False,
        "note": note,
    }


def alternative_baseline_comparison(df: pd.DataFrame) -> pd.DataFrame:
    scored = add_alternative_baseline_scores(df)
    rows = [
        score_metric_row(scored, "global_logistic_scorer", "global_logistic_scorer", "current candidate-level scorer"),
        score_metric_row(scored, "recency_only_baseline", "recency_only_baseline", "months since last purchase, normalized"),
        score_metric_row(
            scored,
            "frequency_decay_baseline",
            "frequency_decay_baseline",
            "1 - recent-vs-12m frequency ratio proxy when raw decay is unavailable",
        ),
        score_metric_row(
            scored,
            "interval_overdue_baseline",
            "interval_overdue_baseline",
            "overdue_ratio transformed to [0,1]; only rows with survival interval fields are scored",
        ),
        {
            "baseline_name": "empirical_hazard_bucket_baseline",
            "row_count": 0,
            "positive_rate": np.nan,
            "score_available_rate": 0.0,
            "auc": np.nan,
            "pr_auc": np.nan,
            "pr_auc_baseline": np.nan,
            "pr_auc_gain": np.nan,
            "pr_auc_lift": np.nan,
            "brier": np.nan,
            "logloss": np.nan,
            "ece": np.nan,
            "precision_at_top_10pct": np.nan,
            "lift_at_top_10pct": np.nan,
            "ndcg_at_top_10pct": np.nan,
            "candidate_level_only": True,
            "trained_formal_model": False,
            "note": "feasibility only: no clean historical train split used, avoiding test-label leakage",
        },
    ]
    return pd.DataFrame(rows)


def md_table(df: pd.DataFrame, max_rows: int = 20, floatfmt: str = ".4f") -> str:
    if df is None or df.empty:
        return "_No rows._"
    try:
        return df.head(max_rows).to_markdown(index=False, floatfmt=floatfmt)
    except Exception:
        return df.head(max_rows).to_string(index=False)


def _top_segments(matrix: pd.DataFrame, mask_col: str, limit: int = 10) -> pd.DataFrame:
    if matrix.empty or mask_col not in matrix.columns:
        return pd.DataFrame()
    sort_cols = ["auc", "lift_at_top_10pct", "row_count"]
    sort_cols = [c for c in sort_cols if c in matrix.columns]
    return matrix[matrix[mask_col].astype(bool)].sort_values(sort_cols, ascending=[False, False, False]).head(limit)


def _worst_segments(matrix: pd.DataFrame, limit: int = 15) -> pd.DataFrame:
    if matrix.empty:
        return pd.DataFrame()
    eligible = matrix[matrix["row_count"].ge(50)].copy()
    eligible["bad_rank_score"] = eligible["auc"].fillna(0.0) + eligible["lift_at_top_10pct"].fillna(0.0) / 10.0
    return eligible.sort_values(["weak_segment", "bad_rank_score", "row_count"], ascending=[False, True, False]).head(limit)


def horizon_pr_ece_table(matrix_by_horizon: pd.DataFrame) -> pd.DataFrame:
    if matrix_by_horizon.empty:
        return pd.DataFrame()
    out = matrix_by_horizon[
        (matrix_by_horizon["segment_dimension"] == "overall") & (matrix_by_horizon["segment_value"] == "all")
    ].copy()
    keep = ["horizon", "row_count", "positive_rate", "auc", "pr_auc", "pr_auc_baseline", "pr_auc_gain", "pr_auc_lift", "ece"]
    return out[[c for c in keep if c in out.columns]].sort_values("horizon")


def segment_pr_ece_table(matrix: pd.DataFrame) -> pd.DataFrame:
    if matrix.empty:
        return pd.DataFrame()
    keep = [
        "segment_dimension",
        "segment_value",
        "row_count",
        "positive_rate",
        "auc",
        "pr_auc",
        "pr_auc_gain",
        "pr_auc_lift",
        "ece",
        "good_segment",
        "weak_segment",
        "not_predictable_segment",
    ]
    return matrix[matrix["row_count"].ge(50)][[c for c in keep if c in matrix.columns]].sort_values(
        ["ece", "row_count"], ascending=[False, False]
    )


def full_universe_artifact_status(root: Path) -> dict[str, Any]:
    candidates = [
        root / "reports/alive_prediction_2024_full_year_sanity_diagnosis",
        root / "reports/alive_prediction_full_year_sanity",
    ]
    existing_dirs = [p for p in candidates if p.exists()]
    monitorable_files = sorted(root.rglob("*monitorable*prediction*.csv"))
    full_universe_files = sorted(root.rglob("*full*universe*.csv"))
    return {
        "sanity_dirs": [str(p.relative_to(root)) for p in existing_dirs],
        "monitorable_prediction_files": [str(p.relative_to(root)) for p in monitorable_files[:10]],
        "full_universe_files": [str(p.relative_to(root)) for p in full_universe_files[:10]],
        "has_comparable_full_universe_metrics": bool(existing_dirs or monitorable_files or full_universe_files),
    }


def survival_feasibility_summary(df: pd.DataFrame) -> dict[str, Any]:
    total = len(df)
    events = int(_safe_numeric(df, "label_die_H").sum()) if total else 0
    cutoff_steps = int(df["cutoff_month"].nunique()) if "cutoff_month" in df.columns else 0
    horizons = sorted(_safe_text(df, "horizon").unique().tolist()) if "horizon" in df.columns else []
    purchase = _safe_numeric(df, "purchase_count_asof_cutoff")
    low_history = _safe_text(df, "history_sufficiency_flag").isin(["history_insufficient", "history_not_available"])
    return {
        "row_count": total,
        "event_count": events,
        "cutoff_steps": cutoff_steps,
        "horizons": ",".join(horizons),
        "purchase_count_ge_3_share": float(purchase.ge(3).mean()) if total else np.nan,
        "purchase_count_ge_5_share": float(purchase.ge(5).mean()) if total else np.nan,
        "purchase_count_ge_10_share": float(purchase.ge(10).mean()) if total else np.nan,
        "low_history_share": float(low_history.mean()) if total else np.nan,
        "intermittent_lumpy_share": float(_safe_text(df, "demand_shape_label").isin(["intermittent", "lumpy"]).mean())
        if total
        else np.nan,
    }


def baseline_advantage_text(alt: pd.DataFrame) -> str:
    if alt.empty:
        return "No baseline metrics available."
    logistic = alt[alt["baseline_name"].eq("global_logistic_scorer")]
    interval = alt[alt["baseline_name"].eq("interval_overdue_baseline")]
    recency = alt[alt["baseline_name"].eq("recency_only_baseline")]
    frequency = alt[alt["baseline_name"].eq("frequency_decay_baseline")]
    if logistic.empty:
        return "Current logistic scorer row is missing."
    logistic_auc = float(logistic["auc"].iloc[0]) if not pd.isna(logistic["auc"].iloc[0]) else np.nan
    parts = []
    if not interval.empty and not pd.isna(interval["auc"].iloc[0]):
        delta = float(interval["auc"].iloc[0]) - logistic_auc
        if delta >= 0.03:
            parts.append("Interval overdue baseline is materially ahead of the logistic scorer on available rows.")
        elif delta <= -0.03:
            parts.append("Interval overdue baseline is not ahead of the logistic scorer on available rows.")
        else:
            parts.append("Interval overdue baseline is close to the logistic scorer on available rows.")
    else:
        parts.append("Interval overdue baseline coverage is insufficient for a clean advantage claim.")
    close = []
    ahead = []
    for frame, name in [(recency, "recency"), (frequency, "frequency decay")]:
        if not frame.empty and not pd.isna(frame["auc"].iloc[0]) and not pd.isna(logistic_auc):
            delta = float(frame["auc"].iloc[0]) - logistic_auc
            if delta >= 0.03:
                ahead.append(name)
            elif abs(delta) <= 0.03:
                close.append(name)
    if ahead:
        ahead_text = ", ".join(ahead)
        parts.append(
            f"{ahead_text.capitalize()} baseline ranks materially better than logistic here, but its calibration metrics are not probability-safe."
        )
    if close:
        parts.append(f"{', '.join(close)} baseline is close to logistic, suggesting the scorer is mostly using those signals.")
    return " ".join(parts)


def segment_name_list(df: pd.DataFrame, limit: int = 6) -> str:
    if df.empty:
        return "not available"
    names = (df["segment_dimension"].astype(str) + "=" + df["segment_value"].astype(str)).drop_duplicates()
    return ", ".join(names.head(limit).tolist()) if not names.empty else "not available"


def summary_report(
    df: pd.DataFrame,
    matrix: pd.DataFrame,
    matrix_by_horizon: pd.DataFrame,
    alt: pd.DataFrame,
) -> str:
    horizon = horizon_pr_ece_table(matrix_by_horizon)
    good = _top_segments(matrix, "good_segment")
    weak = matrix[matrix["weak_segment"].astype(bool)] if "weak_segment" in matrix.columns else pd.DataFrame()
    not_pred = matrix[matrix["not_predictable_segment"].astype(bool)] if "not_predictable_segment" in matrix.columns else pd.DataFrame()
    return "\n".join(
        [
            "# Model Failure Segmentation Summary",
            "",
            "Scope: candidate-level recurring rows with closed labels. This report does not modify M1-M7 artifacts and does not train or save a formal model.",
            "",
            f"- recurring closed rows analyzed: {len(df)}",
            f"- segment rows: {len(matrix)}",
            f"- segment-by-horizon rows: {len(matrix_by_horizon)}",
            f"- good_segment count: {int(matrix['good_segment'].sum()) if 'good_segment' in matrix.columns else 0}",
            f"- weak_segment count: {int(matrix['weak_segment'].sum()) if 'weak_segment' in matrix.columns else 0}",
            f"- not_predictable_segment count: {int(matrix['not_predictable_segment'].sum()) if 'not_predictable_segment' in matrix.columns else 0}",
            "",
            "## Horizon Metrics",
            md_table(horizon),
            "",
            "## Good Segments",
            md_table(
                good[
                    [
                        "segment_dimension",
                        "segment_value",
                        "row_count",
                        "positive_rate",
                        "auc",
                        "pr_auc_gain",
                        "lift_at_top_10pct",
                        "ece",
                    ]
                ]
                if not good.empty
                else good
            ),
            "",
            "## Baseline Comparison",
            md_table(alt),
            "",
            "## Interpretation",
            baseline_advantage_text(alt),
        ]
    )


def stable_service_scope_report(matrix: pd.DataFrame, matrix_by_horizon: pd.DataFrame) -> str:
    good = matrix[matrix["good_segment"].astype(bool)].copy() if "good_segment" in matrix.columns else pd.DataFrame()
    observation = matrix[
        matrix["weak_segment"].astype(bool) & ~matrix["not_predictable_segment"].astype(bool)
    ].copy() if {"weak_segment", "not_predictable_segment"}.issubset(matrix.columns) else pd.DataFrame()
    hidden = matrix[matrix["not_predictable_segment"].astype(bool)].copy() if "not_predictable_segment" in matrix.columns else pd.DataFrame()
    stable_dims = ["manufacturer_code", "hospital_level_code", "demand_shape_label", "history_sufficiency_flag"]
    stable = good[good["segment_dimension"].isin(stable_dims)].sort_values(["auc", "lift_at_top_10pct"], ascending=False)
    hidden_keys = hidden[hidden["segment_dimension"].isin(["history_sufficiency_flag", "demand_shape_label", "purchase_count_bucket"])]
    return "\n".join(
        [
            "# Stable Service Scope Recommendation",
            "",
            "## Probability Output Scope",
            "Probability can be formally displayed only for segments meeting the good_segment rule. In this run, those are:",
            md_table(stable[["segment_dimension", "segment_value", "row_count", "auc", "lift_at_top_10pct", "ece"]]),
            "",
            "## Observation-Only Scope",
            "Segments with enough rows but weak ranking or weak calibration should stay observation-only. They can support analyst review, not precise probability claims.",
            md_table(
                observation[["segment_dimension", "segment_value", "row_count", "auc", "lift_at_top_10pct", "ece"]]
                if not observation.empty
                else observation
            ),
            "",
            "## Hide Probability Scope",
            "Hide probability and show data-insufficient messaging for single-class, row_count < 50, history_insufficient, and short-window intermittent/lumpy poor segments.",
            md_table(
                hidden_keys[["segment_dimension", "segment_value", "row_count", "auc", "lift_at_top_10pct", "ece", "data_quality_note"]]
                if not hidden_keys.empty
                else hidden_keys
            ),
            "",
            "## Stable Enterprise Service Range",
            "Use stable recurring relationships first: history_sufficient or history_medium rows, segments with recurring purchase history, and manufacturers or hospital/demand-shape slices listed in good_segment. Avoid claiming stable enterprise service coverage for low-history and intermittent/lumpy H3 slices until full-universe recall and entity-level validation are available.",
        ]
    )


def bad_segment_report(matrix: pd.DataFrame, matrix_by_horizon: pd.DataFrame) -> str:
    bad = _worst_segments(pd.concat([matrix, matrix_by_horizon], ignore_index=True), limit=25)
    contributors = (
        matrix[matrix["row_count"].ge(100)]
        .sort_values(["weak_segment", "row_count"], ascending=[False, False])
        .head(20)
        if not matrix.empty
        else pd.DataFrame()
    )
    return "\n".join(
        [
            "# Bad Segment Diagnosis",
            "",
            "Low candidate-level AUC is mainly explained by slices with range restriction, high base die rate, weak top-10pct lift, missing interval/history fields, or short-window lumpy/intermittent behavior.",
            "",
            "## Worst Segments",
            md_table(
                bad[
                    [
                        "horizon",
                        "segment_dimension",
                        "segment_value",
                        "row_count",
                        "positive_rate",
                        "auc",
                        "lift_at_top_10pct",
                        "ece",
                        "data_quality_note",
                    ]
                ]
                if not bad.empty
                else bad
            ),
            "",
            "## Large Weak Contributors",
            md_table(
                contributors[
                    [
                        "segment_dimension",
                        "segment_value",
                        "row_count",
                        "positive_rate",
                        "auc",
                        "lift_at_top_10pct",
                        "ece",
                    ]
                ]
                if not contributors.empty
                else contributors
            ),
            "",
            "## Diagnosis",
            "- Candidate preselection narrows score and label variance, so candidate-level AUC is expected to be lower than full-universe discrimination.",
            "- High positive_rate segments can show acceptable PR-AUC while adding little gain over base rate.",
            "- Low-history and intermittent/lumpy short-horizon slices are not reliable probability surfaces.",
            "- Detector and survival states are evidence layers; they should not be interpreted as calibrated probabilities.",
        ]
    )


def pr_auc_ece_report(matrix: pd.DataFrame, matrix_by_horizon: pd.DataFrame) -> str:
    horizon = horizon_pr_ece_table(matrix_by_horizon)
    high_pr_small_gain = matrix[(matrix["pr_auc"].ge(matrix["positive_rate"])) & (matrix["pr_auc_gain"].le(0.03))]
    low_auc_ok_ece = matrix[(matrix["auc"].lt(0.58)) & (matrix["ece"].le(0.15)) & matrix["row_count"].ge(50)]
    segment_ece = segment_pr_ece_table(matrix).head(25)
    return "\n".join(
        [
            "# PR-AUC and ECE Diagnosis",
            "",
            "## By Horizon",
            md_table(horizon),
            "",
            "## ECE by Segment",
            md_table(segment_ece),
            "",
            "## PR-AUC High but Base Rate Driven",
            "Rows below have PR-AUC at or above base rate but gain <= 0.03, so PR-AUC is mostly base-rate support rather than strong ranking evidence.",
            md_table(
                high_pr_small_gain[
                    [
                        "segment_dimension",
                        "segment_value",
                        "row_count",
                        "positive_rate",
                        "pr_auc",
                        "pr_auc_gain",
                        "pr_auc_lift",
                    ]
                ].head(20)
                if not high_pr_small_gain.empty
                else high_pr_small_gain
            ),
            "",
            "## ECE Acceptable but AUC Low",
            "These segments may have usable average calibration but weak ranking. They are suitable only for coarse risk bands, not fine TopK prioritization.",
            md_table(
                low_auc_ok_ece[
                    [
                        "segment_dimension",
                        "segment_value",
                        "row_count",
                        "auc",
                        "ece",
                        "lift_at_top_10pct",
                    ]
                ].head(20)
                if not low_auc_ok_ece.empty
                else low_auc_ok_ece
            ),
            "",
            "## Recommendation",
            "Probability should be output only for stable good_segment slices. Weak or not_predictable slices should use observation-only or data-insufficient messaging.",
        ]
    )


def candidate_vs_full_universe_report(root: Path, df: pd.DataFrame, status: dict[str, Any]) -> str:
    feature_path = find_feature_table(root)
    return "\n".join(
        [
            "# Candidate vs Full-Universe Gap",
            "",
            "1. The current recurring_backtest_frame is candidate-level. It covers M1 candidates, not the full monitorable entity universe.",
            "2. Candidate-level AUC is affected by preselection and range restriction: obvious easy negatives are already filtered out, so ranking among candidates is harder.",
            "3. Full-universe recall is not computable from the current candidate-only frame.",
            f"4. Comparable full-universe artifact found: {str(status['has_comparable_full_universe_metrics']).lower()}",
            f"5. Sanity report directories: {json.dumps(status['sanity_dirs'])}",
            f"6. Monitorable prediction files: {json.dumps(status['monitorable_prediction_files'])}",
            f"7. Full-universe files: {json.dumps(status['full_universe_files'])}",
            f"8. Optional monitorable feature table available: {str(feature_path.relative_to(root)) if feature_path else 'missing'}",
            "",
            "## Required Next Frame",
            "Generate a full-universe prediction-label frame with all monitorable recurring entities per cutoff and horizon, including non-candidate rows, closed labels, candidate flag, and scorer values. Then compare candidate-level metrics against monitorable-universe AUC, PR-AUC, recall, and candidate coverage.",
        ]
    )


def survival_feasibility_report(df: pd.DataFrame, alt: pd.DataFrame) -> str:
    summary = survival_feasibility_summary(df)
    work = df.copy()
    for col in ["purchase_count_asof_cutoff", "months_observed_asof_cutoff"]:
        if col not in work.columns:
            work[col] = np.nan
    by_shape = (
        work.groupby("demand_shape_label", dropna=False)
        .agg(
            row_count=("label_die_H", "size"),
            event_count=("label_die_H", "sum"),
            avg_purchase_count=("purchase_count_asof_cutoff", "mean"),
            avg_months_observed=("months_observed_asof_cutoff", "mean"),
        )
        .reset_index()
        if not work.empty and "demand_shape_label" in work.columns
        else pd.DataFrame()
    )
    alt_text = baseline_advantage_text(alt)
    return "\n".join(
        [
            "# Survival Baseline Feasibility",
            "",
            "No formal survival, interval, BG/NBD, or Pareto-NBD model is trained in this report.",
            "",
            "## Discrete-Time Survival Feasibility",
            f"- candidate rows: {summary['row_count']}",
            f"- event count: {summary['event_count']}",
            f"- cutoff time steps: {summary['cutoff_steps']}",
            f"- horizons: {summary['horizons']}",
            f"- low-history share: {summary['low_history_share']:.4f}",
            "",
            "A pooled discrete-time survival model is feasible only after a full-universe entity-month or entity-cutoff panel is built. Candidate-only rows are useful for diagnosis but not sufficient for recall or hazard calibration.",
            "",
            "## BG/NBD / Pareto-NBD Feasibility",
            f"- purchase_count >= 3 share: {summary['purchase_count_ge_3_share']:.4f}",
            f"- purchase_count >= 5 share: {summary['purchase_count_ge_5_share']:.4f}",
            f"- purchase_count >= 10 share: {summary['purchase_count_ge_10_share']:.4f}",
            f"- intermittent/lumpy share: {summary['intermittent_lumpy_share']:.4f}",
            "",
            "BG/NBD or Pareto-NBD should be restricted to stable recurring segments with repeated purchases. Low-frequency, lumpy, and one-shot-like behavior violates the stable-repeat assumptions and should remain observation-only or use interval evidence.",
            "",
            "## Demand Shape Readiness",
            md_table(by_shape),
            "",
            "## Baseline Advantage Signal",
            alt_text,
        ]
    )


def next_action_report(
    matrix: pd.DataFrame,
    matrix_by_horizon: pd.DataFrame,
    alt: pd.DataFrame,
    full_status: dict[str, Any],
) -> str:
    good = _top_segments(matrix, "good_segment", limit=8)
    bad = _worst_segments(pd.concat([matrix, matrix_by_horizon], ignore_index=True), limit=8)
    horizon = horizon_pr_ece_table(matrix_by_horizon)
    overall = matrix[(matrix["segment_dimension"] == "overall") & (matrix["segment_value"] == "all")]
    overall_auc = overall["auc"].iloc[0] if not overall.empty else np.nan
    overall_ece = overall["ece"].iloc[0] if not overall.empty else np.nan
    overall_gain = overall["pr_auc_gain"].iloc[0] if not overall.empty else np.nan
    return "\n".join(
        [
            "# Next Model Action Decision",
            "",
            "## Answers",
            f"1. Current low AUC is mainly driven by these weak or poor segments: {segment_name_list(bad, 6)}.",
            f"2. Better-performing segments: {segment_name_list(good, 6) if not good.empty else 'none under good_segment rule'}.",
            "3. Service scope should be limited first to stable recurring relationships if good segments are concentrated there.",
            "4. history_insufficient should hide probability and show data-insufficient messaging.",
            "5. intermittent/lumpy should be observation-only for short horizons unless the segment passes the good_segment rule.",
            f"6. PR-AUC gain is {overall_gain:.4f} overall; use gain and lift, not raw PR-AUC alone.",
            f"7. ECE is {overall_ece:.4f} overall; acceptable ECE with low AUC means only coarse risk bands are defensible.",
            "8. Candidate-level AUC is likely depressed by candidate preselection and range restriction.",
            f"9. Full-universe backtest is required: {str(not full_status['has_comparable_full_universe_metrics']).lower()}.",
            "10. Expanding training cutoffs should be evaluated with learning curves, not by mixing 2024 test labels into this research evaluation.",
            f"11. Survival / interval route: {baseline_advantage_text(alt)}",
            "12. Entity-level time series is needed for full-universe recall, survival calibration, and stable recurring modeling.",
            "13. Do not enter frontend/backend design for probability service yet. A limited analyst-facing diagnostic view could proceed only with candidate-level caveats.",
            "",
            "## Horizon Evidence",
            md_table(horizon),
            "",
            "## Training Cutoff Expansion Recommendation",
            "1. Current research evaluation must not add 2024 test labels into training.",
            "2. A future service final model can train on all cutoffs whose labels are already closed at training time.",
            "3. Run learning curves: train 2020, train 2020-2021, train 2020-2022, train 2020-2023, then test on subsequent closed windows.",
            "4. If data only extends to 2025, H12 testing in 2025 has insufficient closure and must be designed separately by horizon.",
            "",
            f"Overall candidate-level AUC in this frame: {overall_auc:.4f}",
        ]
    )


def run_model_failure_segmentation(
    root: Path,
    output_dir: Path,
    *,
    dry_run: bool = False,
) -> dict[str, pd.DataFrame | str | dict[str, Any]]:
    if dry_run:
        recurring, history, survival, detector, features = dry_run_inputs()
    else:
        recurring = read_csv_or_empty(root / "reports/alive_prediction_row_level_backtest_frame_v1/recurring_backtest_frame.csv")
        history = read_csv_or_empty(root / "reports/alive_prediction_m1_m2_corrections_v1/demand_shape_history_sufficiency_flags.csv")
        survival = read_csv_or_empty(root / "reports/alive_prediction_survival_lite_v1/survival_refinement_results.csv")
        detector = read_csv_or_empty(root / "reports/alive_prediction_detectors_v2/detector_frequency_rate_test_results.csv")
        features = load_optional_feature_table(root)

    enriched = enrich_recurring_frame(
        recurring,
        history_flags=history,
        survival=survival,
        detector=detector,
        features=features,
    )
    matrix = build_segment_metric_matrix(enriched)
    matrix_by_horizon = build_segment_metric_matrix_by_horizon(enriched)
    alt = alternative_baseline_comparison(enriched)
    full_status = full_universe_artifact_status(root)

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "segment_metric_matrix.csv", matrix)
    write_csv(output_dir / "segment_metric_matrix_by_horizon.csv", matrix_by_horizon)
    write_csv(output_dir / "alternative_baseline_comparison.csv", alt)
    write_text(output_dir / "model_failure_segmentation_summary.md", summary_report(enriched, matrix, matrix_by_horizon, alt))
    write_text(output_dir / "stable_service_scope_recommendation.md", stable_service_scope_report(matrix, matrix_by_horizon))
    write_text(output_dir / "bad_segment_diagnosis.md", bad_segment_report(matrix, matrix_by_horizon))
    write_text(output_dir / "pr_auc_ece_diagnosis.md", pr_auc_ece_report(matrix, matrix_by_horizon))
    write_text(output_dir / "candidate_vs_full_universe_gap.md", candidate_vs_full_universe_report(root, enriched, full_status))
    write_text(output_dir / "survival_baseline_feasibility.md", survival_feasibility_report(enriched, alt))
    write_text(output_dir / "next_model_action_decision.md", next_action_report(matrix, matrix_by_horizon, alt, full_status))

    return {
        "enriched": enriched,
        "segment_metric_matrix": matrix,
        "segment_metric_matrix_by_horizon": matrix_by_horizon,
        "alternative_baseline_comparison": alt,
        "full_universe_status": full_status,
        "output_dir": str(output_dir),
    }


def dry_run_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    recurring = pd.DataFrame(
        {
            "manufacturer_code": ["m1", "m1", "m2", "m2", "m3", "m3"],
            "hospital_code": ["h1", "h2", "h3", "h4", "h5", "h6"],
            "drug_group": ["d1", "d1", "d2", "d2", "d3", "d3"],
            "drug_group_source": ["drug_code"] * 6,
            "cutoff_month": ["2024-01", "2024-01", "2024-05", "2024-05", "2024-09", "2024-09"],
            "horizon": ["H3", "H3", "H6", "H6", "H12", "H12"],
            "churn_probability_H": [0.9, 0.2, 0.8, 0.4, 0.7, 0.1],
            "relative_business_priority_score_H": [90, 10, 80, 20, 70, 5],
            "label_die_H": [1, 0, 1, 0, 1, 0],
            "label_alive_H": [0, 1, 0, 1, 0, 1],
            "label_window_closed": [True] * 6,
            "demand_shape_label": ["smooth", "smooth", "intermittent", "intermittent", "lumpy", "lumpy"],
            "final_candidate_status": ["priority_review"] * 6,
        }
    )
    history = pd.DataFrame(
        {
            "manufacturer_code": recurring["manufacturer_code"],
            "hospital_code": recurring["hospital_code"],
            "drug_group": recurring["drug_group"],
            "drug_group_source": recurring["drug_group_source"],
            "cutoff_month": recurring["cutoff_month"],
            "horizon": [3, 3, 6, 6, 12, 12],
            "purchase_count_asof_cutoff": [6, 6, 4, 2, 3, 1],
            "active_month_count_asof_cutoff": [4, 4, 3, 1, 2, 1],
            "months_observed_asof_cutoff": [24, 24, 12, 8, 10, 4],
            "history_sufficiency_flag": [
                "history_sufficient",
                "history_sufficient",
                "history_sufficient",
                "history_insufficient",
                "history_medium",
                "history_insufficient",
            ],
        }
    )
    survival = pd.DataFrame(
        {
            "manufacturer_code": recurring["manufacturer_code"],
            "hospital_code": recurring["hospital_code"],
            "drug_group": recurring["drug_group"],
            "drug_group_source": recurring["drug_group_source"],
            "cutoff_month": recurring["cutoff_month"],
            "horizon": [3, 3, 6, 6, 12, 12],
            "survival_state": ["normal_interval", "normal_interval", "materially_overdue", "normal_interval", "low_confidence_lumpy", "low_confidence_lumpy"],
            "demand_shape_route": ["main_probability_model", "main_probability_model", "longer_horizon_only", "longer_horizon_only", "observation_only", "observation_only"],
            "months_since_last_purchase": [1, 1, 5, 2, 8, 1],
            "overdue_ratio": [0.5, 0.5, 2.1, 0.7, 1.5, 0.2],
        }
    )
    detector = pd.DataFrame(
        {
            "manufacturer_code": recurring["manufacturer_code"],
            "hospital_code": recurring["hospital_code"],
            "drug_group": recurring["drug_group"],
            "drug_group_source": recurring["drug_group_source"],
            "cutoff_month": recurring["cutoff_month"],
            "horizon": [3, 3, 6, 6, 12, 12],
            "detector_name": ["purchase_frequency_decay_rate_test"] * 6,
            "hit_flag": [True, False, True, False, False, False],
            "data_quality_note": [""] * 6,
        }
    )
    features = pd.DataFrame(
        {
            "manufacturer_code": recurring["manufacturer_code"],
            "hospital_code": recurring["hospital_code"],
            "drug_group": recurring["drug_group"],
            "drug_group_source": recurring["drug_group_source"],
            "cutoff_month": recurring["cutoff_month"],
            "months_since_first_purchase_asof_cutoff": [24, 24, 12, 8, 10, 4],
            "months_since_last_purchase_asof_cutoff": [1, 1, 5, 2, 8, 1],
            "order_count_last_3m_asof_cutoff": [2, 2, 0, 1, 0, 1],
            "order_count_last_12m_asof_cutoff": [8, 8, 4, 3, 2, 2],
            "province_code": ["p1", "p1", "p2", "p2", "p3", "p3"],
            "hospital_level_code": ["L1", "L1", "L2", "L2", "L3", "L3"],
            "drug_category_code": ["c1", "c1", "c2", "c2", "c3", "c3"],
        }
    )
    return recurring, history, survival, detector, features
