"""Rule baseline and one-shot business attention helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd

from alg.metrics.ranking import cutoff_topk_metrics
from alg.metrics.value_weighted import cutoff_value_metrics


DEFAULT_ONE_SHOT_CONFIG = {
    "recent_one_shot_lookback_months": 36,
    "min_one_shot_silence_months": 3,
    "high_value_threshold_mode": "quantile_by_group",
    "high_value_quantile": 0.9,
    "group_keys": ["manufacturer_code", "drug_group"],
    "default_priority_score": "value_at_risk_amount_nonnegative_H12_asof_cutoff",
}


def add_recurring_candidate_flag(
    features: pd.DataFrame,
    min_purchase_count_asof_cutoff: int = 3,
    min_active_month_count_asof_cutoff: int = 2,
) -> pd.DataFrame:
    out = features.copy()
    out["recurring_candidate"] = (
        out["purchase_count_asof_cutoff"] >= min_purchase_count_asof_cutoff
    ) & (out["active_month_count_asof_cutoff"] >= min_active_month_count_asof_cutoff)
    return out


def add_one_shot_high_value_silence_flags(
    features: pd.DataFrame,
    config: dict | None = None,
) -> pd.DataFrame:
    cfg = {**DEFAULT_ONE_SHOT_CONFIG, **(config or {})}
    out = features.copy()
    priority_col = cfg["default_priority_score"]
    if priority_col not in out.columns:
        raise ValueError(f"Missing one-shot priority column: {priority_col}")
    out["one_shot_flag"] = out["purchase_count_asof_cutoff"] == 1
    out["one_shot_silence_months"] = out["months_since_last_purchase_asof_cutoff"]
    out["one_shot_recent_flag"] = out["months_since_first_purchase_asof_cutoff"] <= cfg["recent_one_shot_lookback_months"]
    if cfg["high_value_threshold_mode"] == "quantile_by_group":
        group_keys = cfg["group_keys"]
        thresholds = out.groupby(group_keys, dropna=False)[priority_col].transform(lambda s: s.quantile(cfg["high_value_quantile"]))
    else:
        thresholds = cfg.get("high_value_threshold", 0)
    out["one_shot_high_value_flag"] = out[priority_col] >= thresholds
    out["one_shot_high_value_silence_flag"] = (
        out["one_shot_flag"]
        & out["one_shot_recent_flag"]
        & out["one_shot_high_value_flag"]
        & (out["one_shot_silence_months"] >= cfg["min_one_shot_silence_months"])
    )
    out["one_shot_business_attention_flag"] = out["one_shot_high_value_silence_flag"]
    out["one_shot_business_priority_score"] = np.where(out["one_shot_business_attention_flag"], out[priority_col], 0.0)
    return out


def build_rule_baseline_scores(features: pd.DataFrame) -> pd.DataFrame:
    """Build non-probability rule scores for recurring candidates."""

    out = features.copy()
    months = pd.to_numeric(out.get("months_since_last_purchase_asof_cutoff", out.get("months_since_last_purchase")), errors="coerce")
    out["months_since_last_purchase_score"] = (months / 12).clip(lower=0, upper=1)
    interval = pd.to_numeric(out.get("median_purchase_interval_days_asof_cutoff"), errors="coerce") / 30.4375
    out["overdue_ratio_score"] = ((months / interval.replace(0, np.nan)) - 1).clip(lower=0, upper=1).fillna(0)

    recent_orders = pd.to_numeric(out.get("order_count_last_3m_asof_cutoff"), errors="coerce").fillna(0)
    base_orders = pd.to_numeric(out.get("order_count_last_12m_asof_cutoff"), errors="coerce").fillna(0) / 4
    out["recent_frequency_drop_score"] = (1 - (recent_orders / base_orders.replace(0, np.nan))).clip(lower=0, upper=1).fillna(0)

    recent_quantity = pd.to_numeric(out.get("purchase_quantity_sum_last_3m_asof_cutoff"), errors="coerce").fillna(0)
    base_quantity = pd.to_numeric(out.get("purchase_quantity_sum_last_12m_asof_cutoff"), errors="coerce").fillna(0) / 4
    out["recent_quantity_drop_score"] = (1 - (recent_quantity / base_quantity.replace(0, np.nan))).clip(lower=0, upper=1).fillna(0)

    out["rule_score"] = (
        0.35 * out["months_since_last_purchase_score"]
        + 0.25 * out["overdue_ratio_score"]
        + 0.20 * out["recent_frequency_drop_score"]
        + 0.20 * out["recent_quantity_drop_score"]
    )
    return out


def build_model_probability_topk_placeholder(rule_scored: pd.DataFrame) -> pd.DataFrame:
    """Return recurring/rule-score rows; this is not a probability-model output."""

    return rule_scored[rule_scored.get("recurring_candidate", False)].copy()


def build_one_shot_attention_list(rule_scored: pd.DataFrame) -> pd.DataFrame:
    """Return one-shot high-value business attention rows."""

    return rule_scored[rule_scored["one_shot_business_attention_flag"]].copy()


def evaluate_rule_baseline_smoke(
    rule_scored_with_labels: pd.DataFrame,
    horizons: tuple[int, ...] = (3, 6, 12),
    k_values=(10, 20, 50, 100, "top_1_pct", "top_5_pct", "top_10_pct"),
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Evaluate rule_score by cutoff_month x manufacturer_code."""

    eligible = rule_scored_with_labels[rule_scored_with_labels["recurring_candidate"]].copy()
    ranking_frames = []
    value_frames = []
    for horizon in horizons:
        label = f"label_die_H{horizon}"
        value = f"value_at_risk_amount_nonnegative_H{horizon}_asof_cutoff"
        if label not in eligible.columns or value not in eligible.columns:
            continue
        ranking = cutoff_topk_metrics(
            eligible,
            label_col=label,
            score_col="rule_score",
            k_values=k_values,
            group_cols=("cutoff_month", "manufacturer_code"),
        )
        ranking["horizon"] = horizon
        ranking_frames.append(ranking)
        value_metrics = cutoff_value_metrics(
            eligible.assign(_rule_priority=eligible["rule_score"] * eligible[value]),
            label_col=label,
            probability_col="rule_score",
            priority_col="_rule_priority",
            value_col=value,
            k_values=k_values,
            group_cols=("cutoff_month", "manufacturer_code"),
        )
        value_metrics["horizon"] = horizon
        value_frames.append(value_metrics)
    return (
        pd.concat(ranking_frames, ignore_index=True) if ranking_frames else pd.DataFrame(),
        pd.concat(value_frames, ignore_index=True) if value_frames else pd.DataFrame(),
    )
