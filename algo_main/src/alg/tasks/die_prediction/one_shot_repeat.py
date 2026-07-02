"""M2 one-shot repeat propensity prototype helpers.

This module estimates first-purchase repeat probability for one-shot attention
objects. It is intentionally separate from recurring churn probability:
``repeat_probability_H`` is not ``churn_probability_H``.

The helpers do not write artifacts and do not persist fitted models.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd


ENTITY_COLS = ["manufacturer_code", "hospital_code", "drug_group"]
KEY_COLS = ["manufacturer_code", "hospital_code", "drug_group", "drug_group_source"]
HORIZONS = [3, 6, 12]
PRIOR_STRENGTH = 20.0
SELECTED_ATTENTION_POLICY = "balanced_attention_score"

GROUP_DEFINITIONS: dict[str, list[str]] = {
    "province_hospital_level": ["province_code", "hospital_level_code"],
    "hospital_level_drug_category": ["hospital_level_code", "drug_category_code"],
    "province_drug_category": ["province_code", "drug_category_code"],
    "manufacturer_drug_category": ["manufacturer_code", "drug_category_code"],
    "manufacturer_province": ["manufacturer_code", "province_code"],
}

CONTEXT_CATEGORICAL_COLS = [
    "hospital_level_code",
    "ownership_type_code",
    "province_code",
    "city_code",
    "county_code",
    "drug_category_code",
    "manufacturer_code",
    "drug_group",
    "order_phase_code",
    "delivery_state_code",
    "order_terminal_flag",
    "order_failure_flag",
]

CONTEXT_NUMERIC_COLS = [
    "first_purchase_quantity",
    "first_purchase_amount",
    "delivery_rate",
    "arrival_rate",
    "overall_arrival_rate",
    "return_quantity",
]


@dataclass(frozen=True)
class OneShotRepeatConfig:
    train_end_month: str = "2022-12"
    prior_strength: float = PRIOR_STRENGTH
    selected_attention_policy: str = SELECTED_ATTENTION_POLICY


def month_period(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.to_period("M")


def safe_divide(numerator: pd.Series | float, denominator: pd.Series | float) -> pd.Series:
    num = pd.to_numeric(numerator, errors="coerce")
    den = pd.to_numeric(denominator, errors="coerce")
    return (num / den.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)


def smoothed_repeat_rate(
    group_positive: float,
    group_count: float,
    global_repeat_rate: float,
    prior_strength: float = PRIOR_STRENGTH,
) -> float:
    """Bayesian-smoothed repeat rate for sparse one-shot groups."""

    if pd.isna(global_repeat_rate):
        global_repeat_rate = 0.5
    if group_count <= 0:
        return float(np.clip(global_repeat_rate, 0.0, 1.0))
    rate = (group_positive + global_repeat_rate * prior_strength) / (group_count + prior_strength)
    return float(np.clip(rate, 0.0, 1.0))


def _ensure_drug_group_source(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "drug_group_source" not in out.columns:
        out["drug_group_source"] = "drug_code"
    return out


def build_first_purchase_samples(
    purchase_events: pd.DataFrame,
    *,
    horizons: Iterable[int] = HORIZONS,
    data_purchase_time_max: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Build entity-level first-purchase samples and repeat labels.

    Labels are only usable when the repeat window is closed by the observable
    purchase data horizon.
    """

    required = set(ENTITY_COLS + ["purchase_time"])
    missing = required - set(purchase_events.columns)
    if missing:
        raise ValueError(f"purchase_events missing required columns: {sorted(missing)}")

    events = _ensure_drug_group_source(purchase_events)
    events = events.copy()
    events["purchase_time"] = pd.to_datetime(events["purchase_time"], errors="coerce")
    if "purchase_month" in events.columns:
        events["purchase_month"] = pd.to_datetime(events["purchase_month"], errors="coerce")
    else:
        events["purchase_month"] = events["purchase_time"].dt.to_period("M").dt.to_timestamp("M")
    events = events[events["purchase_time"].notna()].copy()
    if data_purchase_time_max is None:
        data_purchase_time_max = pd.to_datetime(events["purchase_time"]).max()

    sort_cols = ENTITY_COLS + ["purchase_time"]
    events = events.sort_values(sort_cols, kind="mergesort")
    first = events.groupby(ENTITY_COLS, dropna=False, sort=False).head(1).copy()
    first = first.rename(
        columns={
            "purchase_time": "first_purchase_time",
            "purchase_month": "first_purchase_month",
            "raw_sensitive_purchase_quantity": "first_purchase_quantity",
            "raw_sensitive_purchase_amount": "first_purchase_amount",
        }
    )

    first_times = first[ENTITY_COLS + ["first_purchase_time"]]
    later = events.merge(first_times, on=ENTITY_COLS, how="left")
    later = later[later["purchase_time"].gt(later["first_purchase_time"])].copy()
    second = (
        later.groupby(ENTITY_COLS, dropna=False, sort=False)["purchase_time"]
        .min()
        .reset_index()
        .rename(columns={"purchase_time": "second_purchase_time"})
    )
    samples = first.merge(second, on=ENTITY_COLS, how="left")

    if "raw_sensitive_delivery_quantity" in samples.columns:
        samples["delivery_rate"] = safe_divide(
            samples["raw_sensitive_delivery_quantity"], samples["first_purchase_quantity"]
        )
    else:
        samples["delivery_rate"] = np.nan
    if "raw_sensitive_arrival_quantity" in samples.columns:
        samples["arrival_rate"] = safe_divide(
            samples["raw_sensitive_arrival_quantity"], samples["first_purchase_quantity"]
        )
    else:
        samples["arrival_rate"] = np.nan
    samples["overall_arrival_rate"] = samples["arrival_rate"]
    if {"raw_sensitive_delivery_quantity", "raw_sensitive_arrival_quantity"}.issubset(samples.columns):
        samples["return_quantity"] = (
            pd.to_numeric(samples["raw_sensitive_delivery_quantity"], errors="coerce")
            - pd.to_numeric(samples["raw_sensitive_arrival_quantity"], errors="coerce")
        ).clip(lower=0)
    else:
        samples["return_quantity"] = np.nan

    samples["first_purchase_month"] = pd.to_datetime(samples["first_purchase_month"], errors="coerce")
    for horizon in horizons:
        label_end = samples["first_purchase_time"] + pd.DateOffset(months=int(horizon))
        samples[f"label_window_end_H{horizon}"] = label_end
        samples[f"label_window_closed_H{horizon}"] = label_end.le(data_purchase_time_max)
        repeated = samples["second_purchase_time"].notna() & samples["second_purchase_time"].le(label_end)
        samples[f"label_repeat_H{horizon}"] = np.where(
            samples[f"label_window_closed_H{horizon}"], repeated.astype(int), np.nan
        )

    samples["first_purchase_month"] = samples["first_purchase_month"].dt.to_period("M").astype(str)
    return samples.reset_index(drop=True)


def closed_horizon_samples(samples: pd.DataFrame, horizon: int) -> pd.DataFrame:
    label_col = f"label_repeat_H{horizon}"
    closed_col = f"label_window_closed_H{horizon}"
    if label_col not in samples.columns or closed_col not in samples.columns:
        return samples.iloc[0:0].copy()
    out = samples[samples[closed_col].astype(bool) & samples[label_col].notna()].copy()
    out[label_col] = out[label_col].astype(int)
    return out


def temporal_train_test_split(
    samples: pd.DataFrame,
    *,
    train_end_month: str = "2022-12",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    periods = pd.PeriodIndex(samples["first_purchase_month"], freq="M")
    train = samples[periods <= pd.Period(train_end_month, freq="M")].copy()
    test = samples[periods > pd.Period(train_end_month, freq="M")].copy()
    if train.empty or test.empty:
        ordered_months = sorted(periods.dropna().unique())
        if len(ordered_months) < 2:
            return train, test
        cutoff = ordered_months[max(0, int(len(ordered_months) * 0.75) - 1)]
        train = samples[periods <= cutoff].copy()
        test = samples[periods > cutoff].copy()
    return train, test


def build_group_prior_report(
    reference: pd.DataFrame,
    *,
    horizon: int,
    prior_strength: float = PRIOR_STRENGTH,
) -> pd.DataFrame:
    label_col = f"label_repeat_H{horizon}"
    if reference.empty or label_col not in reference.columns:
        return pd.DataFrame(
            columns=[
                "horizon",
                "group_name",
                "group_key",
                "group_count",
                "group_positive_count",
                "raw_repeat_rate",
                "smoothed_repeat_rate",
                "global_repeat_rate",
                "prior_strength",
            ]
        )
    global_rate = float(reference[label_col].mean()) if len(reference) else 0.5
    rows: list[dict[str, object]] = []
    for group_name, cols in GROUP_DEFINITIONS.items():
        existing = [c for c in cols if c in reference.columns]
        if len(existing) != len(cols):
            continue
        grouped = reference.groupby(existing, dropna=False)[label_col].agg(["count", "sum"]).reset_index()
        for _, row in grouped.iterrows():
            group_count = float(row["count"])
            group_positive = float(row["sum"])
            group_key = "|".join(str(row[c]) for c in existing)
            raw = group_positive / group_count if group_count else np.nan
            rows.append(
                {
                    "horizon": f"H{horizon}",
                    "group_name": group_name,
                    "group_key": group_key,
                    "group_count": int(group_count),
                    "group_positive_count": int(group_positive),
                    "raw_repeat_rate": raw,
                    "smoothed_repeat_rate": smoothed_repeat_rate(
                        group_positive, group_count, global_rate, prior_strength
                    ),
                    "global_repeat_rate": global_rate,
                    "prior_strength": prior_strength,
                }
            )
    return pd.DataFrame(rows)


def add_group_prior_features(
    frame: pd.DataFrame,
    reference: pd.DataFrame,
    *,
    horizon: int,
    prior_strength: float = PRIOR_STRENGTH,
) -> pd.DataFrame:
    """Add leakage-safe group priors using only the supplied reference period."""

    out = frame.copy()
    label_col = f"label_repeat_H{horizon}"
    global_rate = float(reference[label_col].mean()) if label_col in reference.columns and len(reference) else 0.5
    out[f"global_repeat_prior_H{horizon}"] = global_rate
    for group_name, cols in GROUP_DEFINITIONS.items():
        col_name = f"{group_name}_repeat_prior_H{horizon}"
        existing = [c for c in cols if c in out.columns and c in reference.columns]
        if len(existing) != len(cols) or reference.empty or label_col not in reference.columns:
            out[col_name] = global_rate
            continue
        stats = reference.groupby(existing, dropna=False)[label_col].agg(["count", "sum"]).reset_index()
        stats[col_name] = [
            smoothed_repeat_rate(pos, cnt, global_rate, prior_strength)
            for cnt, pos in zip(stats["count"], stats["sum"])
        ]
        out = out.merge(stats[existing + [col_name]], on=existing, how="left")
        out[col_name] = out[col_name].fillna(global_rate)
    return out


def model_feature_columns(df: pd.DataFrame, horizon: int) -> tuple[list[str], list[str]]:
    numeric = [c for c in CONTEXT_NUMERIC_COLS if c in df.columns]
    numeric.extend([c for c in df.columns if c.endswith(f"_repeat_prior_H{horizon}")])
    categorical = [c for c in CONTEXT_CATEGORICAL_COLS if c in df.columns]
    return numeric, categorical


def compute_ece(y_true: Iterable[float], y_prob: Iterable[float], *, n_bins: int = 10) -> float:
    y = np.asarray(list(y_true), dtype=float)
    p = np.asarray(list(y_prob), dtype=float)
    if len(y) == 0:
        return np.nan
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for low, high in zip(bins[:-1], bins[1:]):
        if high == 1.0:
            mask = (p >= low) & (p <= high)
        else:
            mask = (p >= low) & (p < high)
        if not mask.any():
            continue
        ece += mask.mean() * abs(float(y[mask].mean()) - float(p[mask].mean()))
    return float(ece)


def build_attention_scores(
    df: pd.DataFrame,
    *,
    horizon: int,
    value_col: str = "one_shot_value_score",
    selected_attention_policy: str = SELECTED_ATTENTION_POLICY,
) -> pd.DataFrame:
    out = df.copy()
    prob_col = f"repeat_probability_H{horizon}"
    risk_col = f"one_shot_non_repeat_risk_H{horizon}"
    if prob_col not in out.columns:
        raise ValueError(f"{prob_col} missing")
    if risk_col not in out.columns:
        out[risk_col] = 1.0 - out[prob_col]
    if value_col not in out.columns:
        out[value_col] = 1.0
    value = pd.to_numeric(out[value_col], errors="coerce").fillna(1.0)
    repeat = pd.to_numeric(out[prob_col], errors="coerce").clip(0, 1)
    non_repeat = pd.to_numeric(out[risk_col], errors="coerce").clip(0, 1)
    out[f"one_shot_retention_risk_score_H{horizon}"] = non_repeat * value
    out[f"one_shot_conversion_opportunity_score_H{horizon}"] = repeat * value
    out[f"one_shot_balanced_attention_score_H{horizon}"] = repeat * non_repeat * value
    policy_col = f"one_shot_{selected_attention_policy}_H{horizon}"
    if policy_col not in out.columns:
        policy_col = f"one_shot_balanced_attention_score_H{horizon}"
    out["selected_attention_score"] = out[policy_col]
    out["selected_attention_policy"] = selected_attention_policy
    return out


def make_long_enriched_output(scored_by_horizon: list[pd.DataFrame]) -> pd.DataFrame:
    if not scored_by_horizon:
        return pd.DataFrame()
    frames = []
    for part in scored_by_horizon:
        raw_horizon = str(part["horizon"].iloc[0])
        horizon = int(raw_horizon.replace("H", ""))
        out = part.copy()
        out["repeat_probability_H"] = out[f"repeat_probability_H{horizon}"]
        out["one_shot_non_repeat_risk_H"] = out[f"one_shot_non_repeat_risk_H{horizon}"]
        out["one_shot_retention_risk_score_H"] = out[f"one_shot_retention_risk_score_H{horizon}"]
        out["one_shot_conversion_opportunity_score_H"] = out[f"one_shot_conversion_opportunity_score_H{horizon}"]
        out["one_shot_balanced_attention_score_H"] = out[f"one_shot_balanced_attention_score_H{horizon}"]
        frames.append(out)
    result = pd.concat(frames, ignore_index=True)
    ordered = [
        "manufacturer_code",
        "hospital_code",
        "drug_group",
        "drug_group_source",
        "first_purchase_month",
        "horizon",
        "repeat_probability_H",
        "one_shot_non_repeat_risk_H",
        "repeat_probability_interpretation",
        "one_shot_value_score",
        "one_shot_retention_risk_score_H",
        "one_shot_conversion_opportunity_score_H",
        "one_shot_balanced_attention_score_H",
        "selected_attention_score",
        "selected_attention_policy",
        "top_explanation_factors",
        "group_prior_explanation",
        "similarity_group_id",
        "similarity_group_explanation",
        "similar_group_repeat_rate_H",
        "similar_group_sample_count",
        "model_confidence",
        "manual_review_required",
        "probability_available",
        "probability_interpretation",
    ]
    for col in ordered:
        if col not in result.columns:
            result[col] = np.nan
    return result[ordered]


def build_static_explanations(enriched_long: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for _, row in enriched_long.iterrows():
        base = {
            "manufacturer_code": row.get("manufacturer_code"),
            "hospital_code": row.get("hospital_code"),
            "drug_group": row.get("drug_group"),
            "first_purchase_month": row.get("first_purchase_month"),
            "horizon": row.get("horizon"),
        }
        prob = float(row.get("repeat_probability_H", np.nan))
        value = float(row.get("one_shot_value_score", np.nan))
        if not np.isnan(prob):
            direction = "up" if prob >= 0.5 else "down"
            rows.append(
                {
                    **base,
                    "explanation_type": "regional_prior",
                    "feature_or_group": "group_repeat_prior",
                    "direction": direction,
                    "contribution_level": "medium",
                    "message": "Historical pre-test group prior is used as leakage-safe context for repeat probability.",
                }
            )
        if not np.isnan(value):
            rows.append(
                {
                    **base,
                    "explanation_type": "first_purchase_strength",
                    "feature_or_group": "one_shot_value_score",
                    "direction": "up" if value > 1 else "neutral",
                    "contribution_level": "medium",
                    "message": "Initial purchase value is treated as relative value only, not real currency.",
                }
            )
        rows.append(
            {
                **base,
                "explanation_type": "similarity_group",
                "feature_or_group": "kmeans_similarity",
                "direction": "neutral",
                "contribution_level": "reserved",
                "message": "Similarity group explanation deferred in v1; group prior explanation is used.",
            }
        )
    return pd.DataFrame(rows)


def empty_similarity_group_report() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "similarity_group_id": "",
                "horizon": "",
                "similar_group_repeat_rate_H": np.nan,
                "similar_group_sample_count": 0,
                "status": "deferred",
                "note": "KMeans similarity is explanation-only and deferred in v1; group prior explanation is used.",
            }
        ]
    )
