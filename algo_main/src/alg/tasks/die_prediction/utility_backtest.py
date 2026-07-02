"""Utility backtest for the alive-prediction M1-M7 chain.

This module is intentionally report-only. It does not train models, tune
thresholds, regenerate features, call LLMs, or modify upstream M1-M7 outputs.
Strict predictive metrics are reserved for modules with probability semantics:

- M1 recurring ``churn_probability_H``
- M2 one-shot ``repeat_probability_H``

Business priority, survival-lite, detector evidence, status decisions, and
evidence bundles are checked as utility/semantic layers.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


HORIZONS = [3, 6, 12]
M1_TOPK_SPECS: list[int | str] = [10, 20, 50, 100, "top_1_pct", "top_5_pct", "top_10_pct"]
M2_TOPK_SPECS: list[int | str] = [10, 20, 50, "top_5_pct", "top_10_pct"]
ENTITY_COLS = ["manufacturer_code", "hospital_code", "drug_group", "drug_group_source"]


M1_METRIC_COLUMNS = [
    "scope",
    "horizon",
    "cutoff_month",
    "row_count",
    "positive_rate",
    "brier_score",
    "log_loss",
    "ece",
    "auc",
    "pr_auc",
    "metric_available",
    "note",
]
M1_TOPK_COLUMNS = [
    "scope",
    "horizon",
    "cutoff_month",
    "K",
    "row_count",
    "positive_rate",
    "precision_at_k",
    "recall_at_k",
    "lift_at_k",
    "ndcg_at_k",
    "metric_available",
    "note",
]
CALIBRATION_COLUMNS = [
    "horizon",
    "cutoff_month",
    "bin_id",
    "row_count",
    "avg_pred",
    "observed_die_rate",
    "metric_available",
    "note",
]
M2_METRIC_COLUMNS = [
    "horizon",
    "row_count",
    "repeat_positive_rate",
    "non_repeat_rate",
    "brier_score",
    "log_loss",
    "ece",
    "auc",
    "pr_auc",
    "metric_available",
    "fallback_used",
    "note",
]
M2_TOPK_COLUMNS = [
    "horizon",
    "K",
    "topk_direction",
    "row_count",
    "positive_rate",
    "precision_at_k",
    "recall_at_k",
    "lift_at_k",
    "ndcg_at_k",
    "metric_available",
    "note",
]
M2_CALIBRATION_COLUMNS = [
    "horizon",
    "bin_id",
    "row_count",
    "avg_pred",
    "observed_repeat_rate",
    "metric_available",
    "note",
]


def read_csv_or_empty(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, **kwargs)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def write_csv(path: Path, df: pd.DataFrame, columns: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if columns is not None:
        for col in columns:
            if col not in df.columns:
                df[col] = np.nan
        df = df[columns]
    df.to_csv(path, index=False, encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def normalize_horizon(value: Any) -> int | None:
    if pd.isna(value):
        return None
    text = str(value).strip().upper()
    if text.startswith("H"):
        text = text[1:]
    try:
        return int(float(text))
    except ValueError:
        return None


def add_months(month_like: Any, months: int) -> pd.Timestamp:
    ts = pd.to_datetime(str(month_like), errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    return ts + pd.DateOffset(months=int(months))


def is_label_window_closed(cutoff_month: Any, horizon_months: int, max_observed_purchase_date: Any) -> bool:
    end = add_months(cutoff_month, horizon_months)
    max_date = pd.to_datetime(max_observed_purchase_date, errors="coerce")
    if pd.isna(end) or pd.isna(max_date):
        return False
    return bool(end <= max_date)


def construct_die_label(cutoff_month: Any, future_purchase_dates: list[Any], horizon_months: int) -> int | None:
    start = pd.to_datetime(str(cutoff_month), errors="coerce")
    end = add_months(cutoff_month, horizon_months)
    if pd.isna(start) or pd.isna(end):
        return None
    dates = pd.to_datetime(pd.Series(future_purchase_dates), errors="coerce").dropna()
    in_window = ((dates > start) & (dates <= end)).any()
    return int(not in_window)


def construct_repeat_label(first_purchase_month: Any, purchase_dates_after_first: list[Any], horizon_months: int) -> int | None:
    start = pd.to_datetime(str(first_purchase_month), errors="coerce")
    end = add_months(first_purchase_month, horizon_months)
    if pd.isna(start) or pd.isna(end):
        return None
    dates = pd.to_datetime(pd.Series(purchase_dates_after_first), errors="coerce").dropna()
    in_window = ((dates > start) & (dates <= end)).any()
    return int(in_window)


def _as_binary_and_score(df: pd.DataFrame, label_col: str, score_col: str) -> tuple[np.ndarray, np.ndarray]:
    valid = df[[label_col, score_col]].dropna()
    y_true = valid[label_col].astype(int).to_numpy()
    y_score = np.clip(pd.to_numeric(valid[score_col], errors="coerce").to_numpy(dtype=float), 1e-9, 1 - 1e-9)
    keep = ~np.isnan(y_score)
    return y_true[keep], y_score[keep]


def brier_score(y_true: np.ndarray, y_score: np.ndarray) -> float:
    if len(y_true) == 0:
        return float("nan")
    return float(np.mean((y_score - y_true) ** 2))


def log_loss_score(y_true: np.ndarray, y_score: np.ndarray) -> float:
    if len(y_true) == 0:
        return float("nan")
    y_score = np.clip(y_score, 1e-9, 1 - 1e-9)
    return float(-np.mean(y_true * np.log(y_score) + (1 - y_true) * np.log(1 - y_score)))


def roc_auc_score_simple(y_true: np.ndarray, y_score: np.ndarray) -> float:
    if len(np.unique(y_true)) < 2:
        return float("nan")
    order = np.argsort(y_score)
    ranks = np.empty(len(y_score), dtype=float)
    ranks[order] = np.arange(1, len(y_score) + 1)
    # Average tied ranks.
    values, inverse, counts = np.unique(y_score, return_inverse=True, return_counts=True)
    for idx, _ in enumerate(values):
        if counts[idx] > 1:
            ranks[inverse == idx] = ranks[inverse == idx].mean()
    n_pos = y_true.sum()
    n_neg = len(y_true) - n_pos
    rank_sum_pos = ranks[y_true == 1].sum()
    return float((rank_sum_pos - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def average_precision_score_simple(y_true: np.ndarray, y_score: np.ndarray) -> float:
    if len(y_true) == 0 or y_true.sum() == 0:
        return float("nan")
    order = np.argsort(-y_score)
    y_sorted = y_true[order]
    cum_tp = np.cumsum(y_sorted)
    precision_at_rank = cum_tp / (np.arange(len(y_sorted)) + 1)
    return float((precision_at_rank * y_sorted).sum() / y_true.sum())


def expected_calibration_error(y_true: np.ndarray, y_score: np.ndarray, n_bins: int = 10) -> float:
    if len(y_true) == 0:
        return float("nan")
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    total = len(y_true)
    ece = 0.0
    for lo, hi in zip(bins[:-1], bins[1:]):
        if hi == 1.0:
            mask = (y_score >= lo) & (y_score <= hi)
        else:
            mask = (y_score >= lo) & (y_score < hi)
        if mask.any():
            ece += mask.mean() * abs(float(y_score[mask].mean()) - float(y_true[mask].mean()))
    return float(ece)


def binary_metrics(df: pd.DataFrame, label_col: str, score_col: str) -> dict[str, Any]:
    y_true, y_score = _as_binary_and_score(df, label_col, score_col)
    if len(y_true) == 0:
        return {
            "row_count": 0,
            "positive_rate": np.nan,
            "brier_score": np.nan,
            "log_loss": np.nan,
            "ece": np.nan,
            "auc": np.nan,
            "pr_auc": np.nan,
        }
    return {
        "row_count": int(len(y_true)),
        "positive_rate": float(np.mean(y_true)),
        "brier_score": brier_score(y_true, y_score),
        "log_loss": log_loss_score(y_true, y_score),
        "ece": expected_calibration_error(y_true, y_score),
        "auc": roc_auc_score_simple(y_true, y_score),
        "pr_auc": average_precision_score_simple(y_true, y_score),
    }


def _topk_size(k: int | str, n: int) -> int:
    if isinstance(k, int):
        return min(k, n)
    pct = {"top_1_pct": 0.01, "top_5_pct": 0.05, "top_10_pct": 0.10}[k]
    return max(1, min(n, int(math.ceil(n * pct))))


def ndcg_at_k(y_sorted: np.ndarray, k: int) -> float:
    if k <= 0 or len(y_sorted) == 0:
        return float("nan")
    gains = y_sorted[:k]
    discounts = 1.0 / np.log2(np.arange(2, len(gains) + 2))
    dcg = float((gains * discounts).sum())
    ideal = np.sort(y_sorted)[::-1][:k]
    ideal_dcg = float((ideal * discounts).sum())
    return float(dcg / ideal_dcg) if ideal_dcg > 0 else float("nan")


def topk_metrics(
    df: pd.DataFrame,
    label_col: str,
    score_col: str,
    k_specs: list[int | str],
    scope: str,
    horizon: Any,
    cutoff_month: Any = "all",
) -> pd.DataFrame:
    y_true, y_score = _as_binary_and_score(df, label_col, score_col)
    rows: list[dict[str, Any]] = []
    if len(y_true) == 0:
        for k in k_specs:
            rows.append(
                {
                    "scope": scope,
                    "horizon": horizon,
                    "cutoff_month": cutoff_month,
                    "K": k,
                    "row_count": 0,
                    "positive_rate": np.nan,
                    "precision_at_k": np.nan,
                    "recall_at_k": np.nan,
                    "lift_at_k": np.nan,
                    "ndcg_at_k": np.nan,
                    "metric_available": False,
                    "note": "row_level_label_unavailable",
                }
            )
        return pd.DataFrame(rows)
    order = np.argsort(-y_score)
    y_sorted = y_true[order]
    base_rate = float(y_true.mean())
    total_pos = float(y_true.sum())
    for k_spec in k_specs:
        k = _topk_size(k_spec, len(y_true))
        selected = y_sorted[:k]
        precision = float(selected.mean()) if k else np.nan
        recall = float(selected.sum() / total_pos) if total_pos > 0 else np.nan
        lift = float(precision / base_rate) if base_rate > 0 else np.nan
        rows.append(
            {
                "scope": scope,
                "horizon": horizon,
                "cutoff_month": cutoff_month,
                "K": k_spec,
                "row_count": k,
                "positive_rate": base_rate,
                "precision_at_k": precision,
                "recall_at_k": recall,
                "lift_at_k": lift,
                "ndcg_at_k": ndcg_at_k(y_sorted, k),
                "metric_available": True,
                "note": "",
            }
        )
    return pd.DataFrame(rows)


def calibration_bins(
    df: pd.DataFrame,
    label_col: str,
    score_col: str,
    horizon: Any,
    cutoff_month: Any = "all",
    n_bins: int = 10,
) -> pd.DataFrame:
    valid = df[[label_col, score_col]].dropna().copy()
    if valid.empty:
        return pd.DataFrame(columns=CALIBRATION_COLUMNS)
    valid[score_col] = pd.to_numeric(valid[score_col], errors="coerce")
    bins = np.linspace(0, 1, n_bins + 1)
    valid["bin_id"] = pd.cut(valid[score_col], bins=bins, include_lowest=True, labels=False) + 1
    out = (
        valid.groupby("bin_id", dropna=True)
        .agg(row_count=(label_col, "size"), avg_pred=(score_col, "mean"), observed_die_rate=(label_col, "mean"))
        .reset_index()
    )
    out["horizon"] = horizon
    out["cutoff_month"] = cutoff_month
    out["metric_available"] = True
    out["note"] = ""
    return out[CALIBRATION_COLUMNS]


def build_m1_probability_metrics(candidate_by_horizon: pd.DataFrame, calibration_dir: Path) -> pd.DataFrame:
    if {"label_die_H", "churn_probability_H"}.issubset(candidate_by_horizon.columns):
        rows = []
        for horizon, part in candidate_by_horizon.groupby("horizon", dropna=False):
            metrics = binary_metrics(part, "label_die_H", "churn_probability_H")
            rows.append(
                {
                    "scope": "candidate_set",
                    "horizon": horizon,
                    "cutoff_month": "all",
                    **metrics,
                    "metric_available": True,
                    "note": "candidate_set_row_level_label",
                }
            )
        return pd.DataFrame(rows)

    metrics_path = calibration_dir / "calibration_v2_metrics_by_horizon.csv"
    metrics = read_csv_or_empty(metrics_path)
    if metrics.empty:
        return pd.DataFrame(
            [
                {
                    "scope": "candidate_set",
                    "horizon": f"H{h}",
                    "cutoff_month": "all",
                    "row_count": 0,
                    "positive_rate": np.nan,
                    "brier_score": np.nan,
                    "log_loss": np.nan,
                    "ece": np.nan,
                    "auc": np.nan,
                    "pr_auc": np.nan,
                    "metric_available": False,
                    "note": "row_level_label_and_existing_calibration_metrics_unavailable",
                }
                for h in HORIZONS
            ]
        )
    filtered = metrics[
        (metrics.get("model") == "logistic_regression")
        & (metrics.get("feature_set") == "frequency_decay_v1")
        & (metrics.get("calibration_method") == "raw")
        & (metrics.get("period").astype(str) == "2024")
    ].copy()
    if filtered.empty:
        filtered = metrics[
            (metrics.get("model") == "logistic_regression")
            & (metrics.get("feature_set") == "frequency_decay_v1")
            & (metrics.get("calibration_method") == "raw")
        ].copy()
    out = pd.DataFrame(
        {
            "scope": filtered.get("scope", "recurring_only"),
            "horizon": filtered.get("horizon"),
            "cutoff_month": filtered.get("period", "all"),
            "row_count": filtered.get("row_count", np.nan),
            "positive_rate": filtered.get("positive_rate", np.nan),
            "brier_score": filtered.get("brier_score", np.nan),
            "log_loss": filtered.get("log_loss", np.nan),
            "ece": filtered.get("ece", np.nan),
            "auc": filtered.get("auc", np.nan),
            "pr_auc": filtered.get("pr_auc", np.nan),
        }
    )
    out["horizon"] = out["horizon"].map(lambda x: f"H{normalize_horizon(x)}")
    out["metric_available"] = True
    out["note"] = (
        "source_existing_calibration_v2_2024_raw_metrics; "
        "full row-level prediction artifact not copied into utility backtest"
    )
    return out


def build_m1_topk_metrics(candidate_by_horizon: pd.DataFrame, calibration_dir: Path) -> pd.DataFrame:
    if {"label_die_H", "churn_probability_H"}.issubset(candidate_by_horizon.columns):
        parts = []
        for horizon, part in candidate_by_horizon.groupby("horizon", dropna=False):
            parts.append(topk_metrics(part, "label_die_H", "churn_probability_H", M1_TOPK_SPECS, "candidate_set", horizon))
        return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=M1_TOPK_COLUMNS)

    metrics = read_csv_or_empty(calibration_dir / "calibration_v2_metrics_by_horizon.csv")
    rows: list[dict[str, Any]] = []
    pct_map = {
        "top_1_pct": ("precision_at_top_1_pct", "recall_at_top_1_pct", "lift_at_top_1_pct", "ndcg_at_top_1_pct"),
        "top_5_pct": ("precision_at_top_5_pct", "recall_at_top_5_pct", "lift_at_top_5_pct", "ndcg_at_top_5_pct"),
        "top_10_pct": ("precision_at_top_10_pct", "recall_at_top_10_pct", "lift_at_top_10_pct", "ndcg_at_top_10_pct"),
    }
    if metrics.empty:
        for horizon in [f"H{h}" for h in HORIZONS]:
            for spec in M1_TOPK_SPECS:
                rows.append(
                    {
                        "scope": "candidate_set",
                        "horizon": horizon,
                        "cutoff_month": "all",
                        "K": spec,
                        "row_count": 0,
                        "positive_rate": np.nan,
                        "precision_at_k": np.nan,
                        "recall_at_k": np.nan,
                        "lift_at_k": np.nan,
                        "ndcg_at_k": np.nan,
                        "metric_available": False,
                        "note": "row_level_label_and_existing_calibration_topk_unavailable",
                    }
                )
        return pd.DataFrame(rows)

    source = metrics[
        (metrics.get("model") == "logistic_regression")
        & (metrics.get("feature_set") == "frequency_decay_v1")
        & (metrics.get("calibration_method") == "raw")
        & (metrics.get("period").astype(str) == "2024")
    ].copy()
    for _, row in source.iterrows():
        horizon = f"H{normalize_horizon(row.get('horizon'))}"
        for spec in M1_TOPK_SPECS:
            if isinstance(spec, str):
                precision_col, recall_col, lift_col, ndcg_col = pct_map[spec]
                rows.append(
                    {
                        "scope": row.get("scope", "recurring_only"),
                        "horizon": horizon,
                        "cutoff_month": row.get("period", "2024"),
                        "K": spec,
                        "row_count": np.nan,
                        "positive_rate": row.get("positive_rate", np.nan),
                        "precision_at_k": row.get(precision_col, np.nan),
                        "recall_at_k": row.get(recall_col, np.nan),
                        "lift_at_k": row.get(lift_col, np.nan),
                        "ndcg_at_k": row.get(ndcg_col, np.nan),
                        "metric_available": True,
                        "note": "source_existing_calibration_v2_pct_topk_metrics",
                    }
                )
            else:
                rows.append(
                    {
                        "scope": row.get("scope", "recurring_only"),
                        "horizon": horizon,
                        "cutoff_month": row.get("period", "2024"),
                        "K": spec,
                        "row_count": np.nan,
                        "positive_rate": row.get("positive_rate", np.nan),
                        "precision_at_k": np.nan,
                        "recall_at_k": np.nan,
                        "lift_at_k": np.nan,
                        "ndcg_at_k": np.nan,
                        "metric_available": False,
                        "note": "fixed_K_requires_row_level_prediction_label_artifact",
                    }
                )
    return pd.DataFrame(rows)


def build_m1_calibration_bins(candidate_by_horizon: pd.DataFrame, calibration_dir: Path) -> pd.DataFrame:
    if {"label_die_H", "churn_probability_H"}.issubset(candidate_by_horizon.columns):
        parts = []
        for horizon, part in candidate_by_horizon.groupby("horizon", dropna=False):
            parts.append(calibration_bins(part, "label_die_H", "churn_probability_H", horizon))
        return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=CALIBRATION_COLUMNS)
    bins = read_csv_or_empty(calibration_dir / "calibration_v2_bins.csv")
    if bins.empty:
        return pd.DataFrame(columns=CALIBRATION_COLUMNS)
    filtered = bins[
        (bins.get("model") == "logistic_regression")
        & (bins.get("feature_set") == "frequency_decay_v1")
        & (bins.get("calibration_method") == "raw")
        & (bins.get("period").astype(str).isin(["all_2024", "2024"]))
    ].copy()
    out = pd.DataFrame()
    if not filtered.empty:
        out = filtered.rename(
            columns={
                "bin": "bin_id",
                "mean_predicted_probability": "avg_pred",
                "observed_positive_rate": "observed_die_rate",
                "period": "cutoff_month",
            }
        )[["horizon", "cutoff_month", "bin_id", "row_count", "avg_pred", "observed_die_rate"]].copy()
        out["horizon"] = out["horizon"].map(lambda x: f"H{normalize_horizon(x)}")
        out["metric_available"] = True
        out["note"] = "source_existing_calibration_v2_bins"
    return out


def build_m2_repeat_metrics(enriched: pd.DataFrame, metrics_existing: pd.DataFrame) -> pd.DataFrame:
    if {"label_repeat_H", "repeat_probability_H"}.issubset(enriched.columns):
        rows = []
        for horizon, part in enriched.groupby("horizon", dropna=False):
            metrics = binary_metrics(part, "label_repeat_H", "repeat_probability_H")
            rows.append(
                {
                    "horizon": horizon,
                    "row_count": metrics["row_count"],
                    "repeat_positive_rate": metrics["positive_rate"],
                    "non_repeat_rate": 1 - metrics["positive_rate"] if not pd.isna(metrics["positive_rate"]) else np.nan,
                    "brier_score": metrics["brier_score"],
                    "log_loss": metrics["log_loss"],
                    "ece": metrics["ece"],
                    "auc": metrics["auc"],
                    "pr_auc": metrics["pr_auc"],
                    "metric_available": True,
                    "fallback_used": False,
                    "note": "candidate_enriched_row_level_label",
                }
            )
        return pd.DataFrame(rows)
    if metrics_existing.empty:
        return pd.DataFrame(
            [
                {
                    "horizon": f"H{h}",
                    "row_count": 0,
                    "repeat_positive_rate": np.nan,
                    "non_repeat_rate": np.nan,
                    "brier_score": np.nan,
                    "log_loss": np.nan,
                    "ece": np.nan,
                    "auc": np.nan,
                    "pr_auc": np.nan,
                    "metric_available": False,
                    "fallback_used": np.nan,
                    "note": "row_level_repeat_labels_and_existing_m2_metrics_unavailable",
                }
                for h in HORIZONS
            ]
        )
    out = pd.DataFrame(
        {
            "horizon": metrics_existing["horizon"],
            "row_count": metrics_existing.get("test_row_count", np.nan),
            "repeat_positive_rate": metrics_existing.get("positive_rate_test", np.nan),
            "non_repeat_rate": 1 - pd.to_numeric(metrics_existing.get("positive_rate_test", np.nan), errors="coerce"),
            "brier_score": metrics_existing.get("brier_score", np.nan),
            "log_loss": metrics_existing.get("log_loss", np.nan),
            "ece": metrics_existing.get("ece", np.nan),
            "auc": metrics_existing.get("auc", np.nan),
            "pr_auc": metrics_existing.get("pr_auc", np.nan),
            "metric_available": True,
            "fallback_used": metrics_existing.get("fallback_used", np.nan),
            "note": "source_existing_m2_temporal_holdout_metrics; candidate labels unavailable",
        }
    )
    return out


def build_m2_topk_metrics(enriched: pd.DataFrame) -> pd.DataFrame:
    if {"label_repeat_H", "repeat_probability_H"}.issubset(enriched.columns):
        parts = []
        work = enriched.copy()
        work["label_non_repeat_H"] = 1 - work["label_repeat_H"].astype(int)
        for horizon, part in work.groupby("horizon", dropna=False):
            repeat = topk_metrics(part, "label_repeat_H", "repeat_probability_H", M2_TOPK_SPECS, "one_shot_repeat", horizon)
            repeat = repeat.rename(columns={"scope": "topk_direction"})
            repeat["topk_direction"] = "repeat_opportunity"
            risk = topk_metrics(
                part, "label_non_repeat_H", "one_shot_non_repeat_risk_H", M2_TOPK_SPECS, "one_shot_non_repeat", horizon
            )
            risk = risk.rename(columns={"scope": "topk_direction"})
            risk["topk_direction"] = "non_repeat_risk"
            parts.extend([repeat, risk])
        out = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
        return out[
            ["horizon", "K", "topk_direction", "row_count", "positive_rate", "precision_at_k", "recall_at_k", "lift_at_k", "ndcg_at_k", "metric_available", "note"]
        ]
    rows = []
    horizons = sorted(enriched["horizon"].dropna().unique()) if "horizon" in enriched.columns and not enriched.empty else [f"H{h}" for h in HORIZONS]
    for horizon in horizons:
        for direction in ["repeat_opportunity", "non_repeat_risk"]:
            for spec in M2_TOPK_SPECS:
                rows.append(
                    {
                        "horizon": horizon,
                        "K": spec,
                        "topk_direction": direction,
                        "row_count": 0,
                        "positive_rate": np.nan,
                        "precision_at_k": np.nan,
                        "recall_at_k": np.nan,
                        "lift_at_k": np.nan,
                        "ndcg_at_k": np.nan,
                        "metric_available": False,
                        "note": "candidate_enriched_labels_unavailable",
                    }
                )
    return pd.DataFrame(rows)


def build_m2_calibration_bins(enriched: pd.DataFrame) -> pd.DataFrame:
    if {"label_repeat_H", "repeat_probability_H"}.issubset(enriched.columns):
        rows = []
        for horizon, part in enriched.groupby("horizon", dropna=False):
            bins = calibration_bins(part, "label_repeat_H", "repeat_probability_H", horizon)
            if not bins.empty:
                bins = bins.rename(columns={"observed_die_rate": "observed_repeat_rate"}).drop(columns=["cutoff_month"])
                rows.append(bins)
        return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=M2_CALIBRATION_COLUMNS)
    horizons = sorted(enriched["horizon"].dropna().unique()) if "horizon" in enriched.columns and not enriched.empty else [f"H{h}" for h in HORIZONS]
    return pd.DataFrame(
        [
            {
                "horizon": h,
                "bin_id": np.nan,
                "row_count": 0,
                "avg_pred": np.nan,
                "observed_repeat_rate": np.nan,
                "metric_available": False,
                "note": "candidate_enriched_labels_unavailable",
            }
            for h in horizons
        ]
    )


def business_priority_light_check(candidate_by_horizon: pd.DataFrame) -> pd.DataFrame:
    if candidate_by_horizon.empty:
        return pd.DataFrame(
            columns=[
                "horizon",
                "cutoff_month",
                "K",
                "topk_policy",
                "candidate_count",
                "avg_churn_probability",
                "avg_relative_value_at_risk",
                "avg_relative_business_priority_score",
                "observed_die_rate",
                "value_captured",
                "overlap_with_probability_topk",
                "note",
            ]
        )
    rows: list[dict[str, Any]] = []
    group_cols = ["horizon"]
    if "cutoff_month" in candidate_by_horizon.columns:
        group_cols.append("cutoff_month")
    for keys, part in candidate_by_horizon.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        horizon = keys[0]
        cutoff = keys[1] if len(keys) > 1 else "all"
        n = len(part)
        k = max(1, math.ceil(n * 0.05))
        prob_top = part.sort_values("churn_probability_H", ascending=False).head(k) if "churn_probability_H" in part.columns else part.head(0)
        bp_top = (
            part.sort_values("relative_business_priority_score_H", ascending=False).head(k)
            if "relative_business_priority_score_H" in part.columns
            else part.head(0)
        )
        current = part.copy()
        current_ids = set(current.get("candidate_id", pd.Series(dtype=str)).astype(str))
        prob_ids = set(prob_top.get("candidate_id", pd.Series(dtype=str)).astype(str))
        for policy, selected in [
            ("probability_topk", prob_top),
            ("business_priority_topk", bp_top),
            ("current_m1_policy", current),
        ]:
            selected_ids = set(selected.get("candidate_id", pd.Series(dtype=str)).astype(str))
            overlap = len(selected_ids & prob_ids) / max(1, len(selected_ids)) if selected_ids else np.nan
            rows.append(
                {
                    "horizon": horizon,
                    "cutoff_month": cutoff,
                    "K": k if policy != "current_m1_policy" else len(current_ids),
                    "topk_policy": policy,
                    "candidate_count": len(selected),
                    "avg_churn_probability": pd.to_numeric(selected.get("churn_probability_H", np.nan), errors="coerce").mean(),
                    "avg_relative_value_at_risk": pd.to_numeric(selected.get("relative_value_at_risk_H", np.nan), errors="coerce").mean(),
                    "avg_relative_business_priority_score": pd.to_numeric(
                        selected.get("relative_business_priority_score_H", np.nan), errors="coerce"
                    ).mean(),
                    "observed_die_rate": selected["label_die_H"].mean() if "label_die_H" in selected.columns else np.nan,
                    "value_captured": pd.to_numeric(selected.get("relative_value_at_risk_H", np.nan), errors="coerce").sum(),
                    "overlap_with_probability_topk": overlap,
                    "note": "light_check_only_business_priority_is_resource_allocation_not_probability_accuracy",
                }
            )
    return pd.DataFrame(rows)


def survival_state_outcome_check(survival: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "horizon",
        "survival_state",
        "row_count",
        "observed_die_rate",
        "avg_churn_probability_H",
        "avg_relative_business_priority_score_H",
        "avg_survival_confidence",
        "note",
    ]
    if survival.empty:
        return pd.DataFrame(columns=cols)
    rows = []
    for (horizon, state), part in survival.groupby(["horizon", "survival_state"], dropna=False):
        rows.append(
            {
                "horizon": horizon,
                "survival_state": state,
                "row_count": len(part),
                "observed_die_rate": part["label_die_H"].mean() if "label_die_H" in part.columns else np.nan,
                "avg_churn_probability_H": pd.to_numeric(part.get("churn_probability_H", np.nan), errors="coerce").mean(),
                "avg_relative_business_priority_score_H": pd.to_numeric(
                    part.get("relative_business_priority_score_H", np.nan), errors="coerce"
                ).mean(),
                "avg_survival_confidence": pd.to_numeric(part.get("survival_confidence", np.nan), errors="coerce").mean(),
                "note": "light_check_only; label unavailable" if "label_die_H" not in part.columns else "light_check_only",
            }
        )
    return pd.DataFrame(rows, columns=cols)


def detector_outcome_check(detector_v1: pd.DataFrame, detector_v2: pd.DataFrame, label_source: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "source",
        "detector_name",
        "hit_flag",
        "fdr_pass_flag",
        "row_count",
        "observed_die_rate",
        "avg_churn_probability_H",
        "avg_relative_business_priority_score_H",
        "lift_vs_candidate_base_rate",
        "note",
    ]
    frames = []
    if not detector_v1.empty:
        tmp = detector_v1.copy()
        tmp["source"] = "detector_v1"
        frames.append(tmp)
    if not detector_v2.empty:
        tmp = detector_v2.copy()
        tmp["source"] = "detector_v2"
        frames.append(tmp)
    if not frames:
        return pd.DataFrame(columns=cols)
    evidence = pd.concat(frames, ignore_index=True)
    if not label_source.empty and "candidate_id" in label_source.columns:
        label_cols = [
            c
            for c in ["candidate_id", "label_die_H", "churn_probability_H", "relative_business_priority_score_H"]
            if c in label_source.columns
        ]
        evidence = evidence.merge(label_source[label_cols].drop_duplicates("candidate_id"), on="candidate_id", how="left", suffixes=("", "_label"))
        for col in ["churn_probability_H", "relative_business_priority_score_H"]:
            label_col = f"{col}_label"
            if label_col in evidence.columns:
                evidence[col] = evidence[col].combine_first(evidence[label_col]) if col in evidence.columns else evidence[label_col]
    base = evidence["label_die_H"].mean() if "label_die_H" in evidence.columns else np.nan
    if "fdr_pass_flag" not in evidence.columns:
        evidence["fdr_pass_flag"] = np.nan
    rows = []
    group_cols = ["source", "detector_name", "hit_flag", "fdr_pass_flag"]
    for keys, part in evidence.groupby(group_cols, dropna=False):
        source, name, hit, fdr_pass = keys
        observed = part["label_die_H"].mean() if "label_die_H" in part.columns else np.nan
        rows.append(
            {
                "source": source,
                "detector_name": name,
                "hit_flag": hit,
                "fdr_pass_flag": fdr_pass,
                "row_count": len(part),
                "observed_die_rate": observed,
                "avg_churn_probability_H": pd.to_numeric(part.get("churn_probability_H", np.nan), errors="coerce").mean(),
                "avg_relative_business_priority_score_H": pd.to_numeric(
                    part.get("relative_business_priority_score_H", np.nan), errors="coerce"
                ).mean(),
                "lift_vs_candidate_base_rate": observed / base if not pd.isna(observed) and base not in [0, np.nan] else np.nan,
                "note": "light_check_only; price_delivery_interface_only_excluded_from_strong_claims",
            }
        )
    return pd.DataFrame(rows, columns=cols)


def status_outcome_check(status: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "horizon",
        "candidate_type",
        "final_candidate_status",
        "review_priority",
        "evidence_strength",
        "row_count",
        "observed_die_rate",
        "avg_churn_probability_H",
        "avg_relative_business_priority_score_H",
        "note",
    ]
    if status.empty:
        return pd.DataFrame(columns=cols)
    rows = []
    groups = ["horizon", "candidate_type", "final_candidate_status", "review_priority", "evidence_strength"]
    for keys, part in status.groupby(groups, dropna=False):
        horizon, ctype, final_status, priority, strength = keys
        recurring = ctype == "recurring_business_priority"
        rows.append(
            {
                "horizon": horizon,
                "candidate_type": ctype,
                "final_candidate_status": final_status,
                "review_priority": priority,
                "evidence_strength": strength,
                "row_count": len(part),
                "observed_die_rate": part["label_die_H"].mean() if recurring and "label_die_H" in part.columns else np.nan,
                "avg_churn_probability_H": pd.to_numeric(part.get("churn_probability_H", np.nan), errors="coerce").mean(),
                "avg_relative_business_priority_score_H": pd.to_numeric(
                    part.get("relative_business_priority_score_H", np.nan), errors="coerce"
                ).mean(),
                "note": "one-shot/demand-shape not evaluated as recurring die_H"
                if ctype != "recurring_business_priority"
                else ("light_check_only; label unavailable" if "label_die_H" not in part.columns else "light_check_only"),
            }
        )
    return pd.DataFrame(rows, columns=cols)


def evidence_bundle_quality_check(
    completeness: pd.DataFrame,
    field_completeness: pd.DataFrame,
    claim_audit: pd.DataFrame,
    actionability: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    if not completeness.empty:
        for _, row in completeness.iterrows():
            rows.append(
                {
                    "check_scope": f"bundle_{row.get('candidate_type', 'unknown')}",
                    "row_count": row.get("row_count", np.nan),
                    "allowed_claims_coverage": row.get("has_allowed_claims_rate", np.nan),
                    "forbidden_claims_coverage": row.get("has_forbidden_claims_rate", np.nan),
                    "recommended_action_coverage": row.get("has_recommended_actions_rate", np.nan),
                    "claim_violation_count": np.nan,
                    "actionability_pass_rate": np.nan,
                    "static_card_complete_rate": np.nan,
                    "one_shot_churn_pollution_violation": np.nan,
                    "price_delivery_interface_misuse": np.nan,
                    "note": "quality_check_not_predictive_backtest",
                }
            )
    if not field_completeness.empty or not claim_audit.empty or not actionability.empty:
        claim_violations = 0
        if not claim_audit.empty and "claim_boundary_pass" in claim_audit.columns:
            claim_violations = int((~claim_audit["claim_boundary_pass"].astype(bool)).sum())
        rows.append(
            {
                "check_scope": "static_card_review",
                "row_count": len(field_completeness) if not field_completeness.empty else np.nan,
                "allowed_claims_coverage": np.nan,
                "forbidden_claims_coverage": np.nan,
                "recommended_action_coverage": np.nan,
                "claim_violation_count": claim_violations,
                "actionability_pass_rate": actionability.get("actionable_flag", pd.Series(dtype=bool)).astype(bool).mean()
                if not actionability.empty and "actionable_flag" in actionability.columns
                else np.nan,
                "static_card_complete_rate": field_completeness.get("card_complete", pd.Series(dtype=bool)).astype(bool).mean()
                if not field_completeness.empty and "card_complete" in field_completeness.columns
                else np.nan,
                "one_shot_churn_pollution_violation": _count_violation(claim_audit, "one-shot"),
                "price_delivery_interface_misuse": _count_violation(claim_audit, "price") + _count_violation(claim_audit, "delivery"),
                "note": "quality_check_not_predictive_backtest",
            }
        )
    return pd.DataFrame(rows)


def _count_violation(audit: pd.DataFrame, token: str) -> int:
    if audit.empty or "violation_type" not in audit.columns:
        return 0
    text = audit["violation_type"].fillna("").astype(str) + " " + audit.get("violation_detail", "").fillna("").astype(str)
    return int(text.str.contains(token, case=False, regex=False).sum())


def historical_true_positive_cases(status: pd.DataFrame, max_cases: int = 30) -> pd.DataFrame:
    cols = [
        "case_id",
        "manufacturer_code",
        "hospital_code",
        "drug_group",
        "cutoff_month",
        "horizon",
        "prediction_source",
        "churn_probability_H",
        "relative_business_priority_score_H",
        "final_candidate_status",
        "review_priority",
        "survival_state",
        "top_detector_reasons",
        "label_die_H",
        "months_without_purchase_after_cutoff",
        "latest_observed_purchase_status",
        "proof_case_note",
    ]
    if status.empty or "label_die_H" not in status.columns:
        return pd.DataFrame(columns=cols)
    selected = status[
        (status["label_die_H"] == 1)
        & (status["candidate_type"] == "recurring_business_priority")
        & (status["final_candidate_status"].isin(["priority_review", "manual_review"]))
    ].copy()
    if selected.empty:
        return pd.DataFrame(columns=cols)
    selected = selected.sort_values(["review_priority", "relative_business_priority_score_H", "churn_probability_H"], ascending=[True, False, False]).head(max_cases)
    selected["case_id"] = [f"proof_case_{i:03d}" for i in range(1, len(selected) + 1)]
    selected["prediction_source"] = "m5_status_or_priority_candidate"
    selected["months_without_purchase_after_cutoff"] = selected.get("months_without_purchase_after_cutoff", np.nan)
    selected["latest_observed_purchase_status"] = selected.get("latest_observed_purchase_status", "unknown")
    selected["proof_case_note"] = "selected_true_positive_proxy_label_only_not_accuracy_report"
    return selected[cols]


def false_positive_cases(status: pd.DataFrame, max_cases: int = 100) -> pd.DataFrame:
    return _error_cases(status, label_value=0, case_type="false_positive", max_cases=max_cases)


def false_negative_cases(status: pd.DataFrame, max_cases: int = 100) -> pd.DataFrame:
    if status.empty or "label_die_H" not in status.columns:
        return _empty_error_cases()
    selected = status[
        (status["label_die_H"] == 1)
        & ~status["final_candidate_status"].isin(["priority_review", "manual_review"])
        & (status["candidate_type"] == "recurring_business_priority")
    ].copy()
    return _format_error_cases(selected, "false_negative", max_cases)


def _error_cases(status: pd.DataFrame, label_value: int, case_type: str, max_cases: int) -> pd.DataFrame:
    if status.empty or "label_die_H" not in status.columns:
        return _empty_error_cases()
    selected = status[
        (status["label_die_H"] == label_value)
        & status["final_candidate_status"].isin(["priority_review", "manual_review"])
        & (status["candidate_type"] == "recurring_business_priority")
    ].copy()
    return _format_error_cases(selected, case_type, max_cases)


def _format_error_cases(selected: pd.DataFrame, case_type: str, max_cases: int) -> pd.DataFrame:
    cols = [
        "case_type",
        "manufacturer_code",
        "hospital_code",
        "drug_group",
        "cutoff_month",
        "horizon",
        "churn_probability_H",
        "relative_business_priority_score_H",
        "final_candidate_status",
        "review_priority",
        "survival_state",
        "detector_summary",
        "label_die_H",
        "error_note",
    ]
    if selected.empty:
        return pd.DataFrame(columns=cols)
    selected = selected.head(max_cases).copy()
    selected["case_type"] = case_type
    selected["detector_summary"] = selected.get("top_detector_reasons", "")
    selected["error_note"] = f"{case_type}_for_technical_review_proxy_label"
    return selected[cols]


def _empty_error_cases() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "case_type",
            "manufacturer_code",
            "hospital_code",
            "drug_group",
            "cutoff_month",
            "horizon",
            "churn_probability_H",
            "relative_business_priority_score_H",
            "final_candidate_status",
            "review_priority",
            "survival_state",
            "detector_summary",
            "label_die_H",
            "error_note",
        ]
    )


def render_proof_case_cards(cases: pd.DataFrame) -> str:
    if cases.empty:
        return (
            "# Proof Case Cards\n\n"
            "No historical true-positive proof cases were generated because row-level closed-window labels were not available "
            "in the existing reports used by this read-only backtest.\n"
        )
    blocks = ["# Proof Case Cards", ""]
    for _, row in cases.iterrows():
        blocks.extend(
            [
                f"## {row['case_id']}",
                "",
                f"- Entity: {row.get('manufacturer_code')} / {row.get('hospital_code')} / {row.get('drug_group')}",
                f"- Cutoff / horizon: {row.get('cutoff_month')} / {row.get('horizon')}",
                f"- At cutoff, system saw: churn_probability_H={row.get('churn_probability_H')}, "
                f"relative_business_priority_score_H={row.get('relative_business_priority_score_H')}, "
                f"status={row.get('final_candidate_status')}, priority={row.get('review_priority')}",
                f"- Survival state: {row.get('survival_state')}",
                f"- Detector reasons: {row.get('top_detector_reasons')}",
                "- Future proxy outcome: label_die_H=1, meaning no valid purchase in the closed future H window.",
                "- Interpretation: this selected case illustrates a historical true-positive proxy outcome only.",
                "",
            ]
        )
    return "\n".join(blocks)


def proof_case_disclaimer() -> str:
    return (
        "# Proof Case Disclaimer\n\n"
        "This file contains selected true-positive historical cases only. It is not a complete accuracy report. "
        "False positives and false negatives are recorded in the technical backtest files.\n\n"
        "The current project uses fixed-window future no-purchase proxy labels because customer-confirmed true loss labels "
        "are unavailable. Proof cases must not be presented as full model precision, recall, or deployment readiness.\n"
    )


def build_universe_summary(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for name, df in inputs.items():
        label_cols = [c for c in ["label_die_H", "label_repeat_H"] if c in df.columns]
        rows.append(
            {
                "component": name,
                "row_count": len(df),
                "label_available_row_count": int(df[label_cols].notna().all(axis=1).sum()) if label_cols else 0,
                "label_window_closed_row_count": int(df["label_window_closed"].astype(bool).sum()) if "label_window_closed" in df.columns else 0,
                "note": "row_level_label_available" if label_cols else "row_level_label_not_available_in_existing_report",
            }
        )
    return pd.DataFrame(rows)


def render_summary(
    universe: pd.DataFrame,
    m1_metrics: pd.DataFrame,
    m2_metrics: pd.DataFrame,
    proof_cases: pd.DataFrame,
    false_pos: pd.DataFrame,
    false_neg: pd.DataFrame,
) -> str:
    m1_available = bool(m1_metrics.get("metric_available", pd.Series(dtype=bool)).astype(bool).any())
    m2_available = bool(m2_metrics.get("metric_available", pd.Series(dtype=bool)).astype(bool).any())
    label_closed = int(universe.get("label_window_closed_row_count", pd.Series(dtype=int)).sum()) if not universe.empty else 0
    universe_rows = int(universe.get("row_count", pd.Series(dtype=int)).sum()) if not universe.empty else 0
    return f"""# Utility Backtest Summary

1. Fixed-window proxy label used: yes, where row-level closed-window labels are available.
2. Test cutoff coverage: existing 2024 calibration reports for M1; existing M2 temporal holdout metrics; candidate-level reports otherwise.
3. Label closure completed rows in loaded report tables: {label_closed}.
4. Backtest universe rows loaded from reports: {universe_rows}.
5. M1 probability backtest generated: {m1_available}.
6. M2 one-shot repeat backtest generated: {m2_available}.
7. Business priority: light check only. It is a resource-allocation policy, not a probability model.
8. M3/M4/M5/M7: light checks only. No module ablation was performed.
9. Proof cases generated: {len(proof_cases)}.
10. False positives generated: {len(false_pos)}.
11. False negatives generated: {len(false_neg)}.

## Interpretation Boundaries

- M1 strict metrics evaluate recurring churn_probability_H where existing calibration metrics or labels are available.
- M2 strict metrics evaluate repeat_probability_H, which is first-purchase repeat probability, not recurring churn.
- Business priority, survival states, detector evidence, status decisions, and bundles are not independent probability models.
- Proof cases are selected true-positive examples only and must not be used as a complete accuracy report.
- No model was trained, tuned, or rerun in this utility backtest.

## Current Utility Read

The existing M1 calibration report provides a technical signal-quality view for the probability scorer. The existing M2
temporal holdout metrics provide a technical signal-quality view for one-shot repeat propensity. Candidate-level closed
future labels are not present in the current report set, so candidate proof/error case generation is intentionally limited.
"""


def render_next_action_decision(
    m1_metrics: pd.DataFrame,
    m2_metrics: pd.DataFrame,
    detector_check: pd.DataFrame,
    proof_cases: pd.DataFrame,
) -> str:
    lines = ["# Next Algorithm Action Decision", ""]
    lines.append("## Decisions")
    if m1_metrics.empty or not m1_metrics["metric_available"].astype(bool).any():
        lines.append("- M1: materialize row-level prediction + closed-window label artifacts before deeper TopK/proof analysis.")
    else:
        auc_mean = pd.to_numeric(m1_metrics["auc"], errors="coerce").mean()
        ece_mean = pd.to_numeric(m1_metrics["ece"], errors="coerce").mean()
        lines.append(f"- M1: existing aggregate probability metrics are available; mean AUC={auc_mean:.3f}, mean ECE={ece_mean:.3f}.")
        lines.append("- M1: if business-priority TopK underperforms probability TopK after labels are available, review value_at_risk.")
    if m2_metrics.empty or not m2_metrics["metric_available"].astype(bool).any():
        lines.append("- M2: repeat labels unavailable; generate closed-window one-shot labels for candidate-level review.")
    else:
        auc_mean = pd.to_numeric(m2_metrics["auc"], errors="coerce").mean()
        ece_mean = pd.to_numeric(m2_metrics["ece"], errors="coerce").mean()
        lines.append(f"- M2: existing temporal metrics are available; mean AUC={auc_mean:.3f}, mean ECE={ece_mean:.3f}.")
        lines.append("- M2: keep one-shot semantics separate from recurring churn; consider group-prior fallback if future metrics weaken.")
    d002 = detector_check[detector_check.get("detector_name", pd.Series(dtype=str)) == "purchase_frequency_decay_rate_test"]
    if not d002.empty:
        lines.append("- M4 D002: outcome linkage should be checked once labels are materialized; only then proceed from p-value readiness to FDR utility claims.")
    if proof_cases.empty:
        lines.append("- Proof cases: none generated from current reports because candidate-level closed-window labels were unavailable.")
    else:
        lines.append("- Proof cases: use only as selected historical examples, not as a full accuracy claim.")
    lines.append("")
    lines.append("## Non-actions")
    lines.append("- Do not treat business priority as probability accuracy.")
    lines.append("- Do not treat one_shot_non_repeat_risk_H as recurring churn.")
    lines.append("- Do not treat detector severity/confidence as probability.")
    return "\n".join(lines) + "\n"


def _read_inputs(root: Path) -> dict[str, pd.DataFrame]:
    reports = root / "reports"
    return {
        "m1_by_horizon": read_csv_or_empty(reports / "alive_prediction_candidate_pool_v1/recurring_business_priority_candidates_by_horizon.csv"),
        "m1_main": read_csv_or_empty(reports / "alive_prediction_candidate_pool_v1/recurring_business_priority_candidates.csv"),
        "m2_enriched": read_csv_or_empty(reports / "alive_prediction_one_shot_repeat_v1/one_shot_attention_candidates_enriched.csv"),
        "m2_metrics_existing": read_csv_or_empty(reports / "alive_prediction_one_shot_repeat_v1/one_shot_repeat_metrics.csv"),
        "survival": read_csv_or_empty(reports / "alive_prediction_survival_lite_v1/survival_refinement_results.csv"),
        "detector_v1": read_csv_or_empty(reports / "alive_prediction_detectors_v1/detector_evidence_results.csv"),
        "detector_v2": read_csv_or_empty(reports / "alive_prediction_detectors_v2/detector_evidence_results_v2.csv"),
        "status": read_csv_or_empty(reports / "alive_prediction_status_decision_v1/candidate_status_decision.csv"),
        "bundle_completeness": read_csv_or_empty(reports / "alive_prediction_evidence_bundle_v1/evidence_bundle_completeness_report.csv"),
        "static_field_completeness": read_csv_or_empty(reports / "alive_prediction_static_line_card_review_v1/static_line_card_field_completeness.csv"),
        "static_claim_audit": read_csv_or_empty(reports / "alive_prediction_static_line_card_review_v1/static_line_card_claim_boundary_audit.csv"),
        "actionability_audit": read_csv_or_empty(reports / "alive_prediction_evidence_bundle_review_v1/evidence_bundle_actionability_audit.csv"),
    }


def _dry_run_inputs() -> dict[str, pd.DataFrame]:
    m1 = pd.DataFrame(
        {
            "candidate_id": ["a", "b", "c", "d"],
            "manufacturer_code": ["m"] * 4,
            "hospital_code": ["h1", "h2", "h3", "h4"],
            "drug_group": ["d"] * 4,
            "drug_group_source": ["drug_code"] * 4,
            "cutoff_month": ["2024-01"] * 4,
            "horizon": ["H6"] * 4,
            "churn_probability_H": [0.9, 0.8, 0.2, 0.1],
            "relative_value_at_risk_H": [10, 5, 100, 80],
            "relative_business_priority_score_H": [9, 4, 20, 8],
            "label_die_H": [1, 1, 0, 0],
        }
    )
    m2 = pd.DataFrame(
        {
            "horizon": ["H3", "H3", "H3", "H3"],
            "repeat_probability_H": [0.8, 0.7, 0.2, 0.1],
            "one_shot_non_repeat_risk_H": [0.2, 0.3, 0.8, 0.9],
            "label_repeat_H": [1, 1, 0, 0],
        }
    )
    survival = m1.assign(survival_state=["likely_churn_interval", "materially_overdue", "normal_interval", "normal_interval"], survival_confidence=[0.8, 0.7, 0.6, 0.6])
    detector = m1.assign(detector_name=["terminal_loss_warning"] * 4, hit_flag=[True, True, False, False], fdr_pass_flag=[np.nan] * 4)
    status = survival.assign(
        candidate_type=["recurring_business_priority"] * 4,
        final_candidate_status=["priority_review", "manual_review", "observation_only", "low_confidence_watch"],
        review_priority=["P1", "P2", "P3", "P3"],
        evidence_strength=["medium", "weak", "insufficient", "insufficient"],
        top_detector_reasons=["terminal_loss_warning", "", "", ""],
    )
    completeness = pd.DataFrame(
        {
            "candidate_type": ["recurring_business_priority"],
            "row_count": [4],
            "has_allowed_claims_rate": [1.0],
            "has_forbidden_claims_rate": [1.0],
            "has_recommended_actions_rate": [1.0],
        }
    )
    return {
        "m1_by_horizon": m1,
        "m1_main": m1,
        "m2_enriched": m2,
        "m2_metrics_existing": pd.DataFrame(),
        "survival": survival,
        "detector_v1": detector,
        "detector_v2": pd.DataFrame(),
        "status": status,
        "bundle_completeness": completeness,
        "static_field_completeness": pd.DataFrame({"card_complete": [True, True]}),
        "static_claim_audit": pd.DataFrame({"claim_boundary_pass": [True, True], "violation_type": ["", ""], "violation_detail": ["", ""]}),
        "actionability_audit": pd.DataFrame({"actionable_flag": [True, True]}),
    }


def run_utility_backtest(root: Path, output_dir: Path, dry_run: bool = False) -> dict[str, pd.DataFrame]:
    inputs = _dry_run_inputs() if dry_run else _read_inputs(root)
    reports = root / "reports"
    calibration_dir = reports / "alive_prediction_calibration_v2"

    m1_metrics = build_m1_probability_metrics(inputs["m1_by_horizon"], calibration_dir)
    m1_topk = build_m1_topk_metrics(inputs["m1_by_horizon"], calibration_dir)
    m1_bins = build_m1_calibration_bins(inputs["m1_by_horizon"], calibration_dir)

    m2_metrics = build_m2_repeat_metrics(inputs["m2_enriched"], inputs["m2_metrics_existing"])
    m2_topk = build_m2_topk_metrics(inputs["m2_enriched"])
    m2_bins = build_m2_calibration_bins(inputs["m2_enriched"])

    business_check = business_priority_light_check(inputs["m1_by_horizon"])
    survival_check = survival_state_outcome_check(inputs["survival"])
    label_source = inputs["status"] if "label_die_H" in inputs["status"].columns else inputs["survival"]
    detector_check = detector_outcome_check(inputs["detector_v1"], inputs["detector_v2"], label_source)
    status_check = status_outcome_check(inputs["status"])
    bundle_quality = evidence_bundle_quality_check(
        inputs["bundle_completeness"],
        inputs["static_field_completeness"],
        inputs["static_claim_audit"],
        inputs["actionability_audit"],
    )
    proof_cases = historical_true_positive_cases(inputs["status"])
    fp_cases = false_positive_cases(inputs["status"])
    fn_cases = false_negative_cases(inputs["status"])
    universe = build_universe_summary(
        {
            "m1_by_horizon": inputs["m1_by_horizon"],
            "m2_enriched": inputs["m2_enriched"],
            "survival": inputs["survival"],
            "detector_v1": inputs["detector_v1"],
            "detector_v2": inputs["detector_v2"],
            "status": inputs["status"],
        }
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "backtest_universe_summary.csv", universe)
    write_csv(output_dir / "m1_probability_backtest_metrics.csv", m1_metrics, M1_METRIC_COLUMNS)
    write_csv(output_dir / "m1_probability_topk_metrics.csv", m1_topk, M1_TOPK_COLUMNS)
    write_csv(output_dir / "m1_probability_calibration_bins.csv", m1_bins, CALIBRATION_COLUMNS)
    write_csv(output_dir / "m2_one_shot_repeat_backtest_metrics.csv", m2_metrics, M2_METRIC_COLUMNS)
    write_csv(output_dir / "m2_one_shot_topk_metrics.csv", m2_topk, M2_TOPK_COLUMNS)
    write_csv(output_dir / "m2_one_shot_calibration_bins.csv", m2_bins, M2_CALIBRATION_COLUMNS)
    write_csv(output_dir / "business_priority_light_check.csv", business_check)
    write_csv(output_dir / "survival_state_outcome_check.csv", survival_check)
    write_csv(output_dir / "detector_outcome_check.csv", detector_check)
    write_csv(output_dir / "status_outcome_check.csv", status_check)
    write_csv(output_dir / "evidence_bundle_quality_check.csv", bundle_quality)
    write_csv(output_dir / "historical_true_positive_cases.csv", proof_cases)
    write_csv(output_dir / "false_positive_cases_for_technical_review.csv", fp_cases)
    write_csv(output_dir / "false_negative_cases_for_technical_review.csv", fn_cases)

    write_text(output_dir / "proof_case_cards.md", render_proof_case_cards(proof_cases))
    write_text(output_dir / "proof_case_disclaimer.md", proof_case_disclaimer())
    write_text(output_dir / "next_algorithm_action_decision.md", render_next_action_decision(m1_metrics, m2_metrics, detector_check, proof_cases))
    write_text(output_dir / "utility_backtest_summary.md", render_summary(universe, m1_metrics, m2_metrics, proof_cases, fp_cases, fn_cases))

    return {
        "universe": universe,
        "m1_metrics": m1_metrics,
        "m2_metrics": m2_metrics,
        "business_check": business_check,
        "survival_check": survival_check,
        "detector_check": detector_check,
        "status_check": status_check,
        "bundle_quality": bundle_quality,
        "proof_cases": proof_cases,
        "false_positive": fp_cases,
        "false_negative": fn_cases,
    }
