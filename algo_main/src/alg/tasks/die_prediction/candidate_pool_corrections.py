"""Safety corrections and display views for alive prediction M1/M2 outputs.

The helpers here are read-only with respect to M1/M2 source artifacts. They
build checked/corrected report views without changing candidate generation
logic, model logic, or original report files.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


ENTITY_COLS = ["manufacturer_code", "hospital_code", "drug_group"]
KEY_COLS = ["manufacturer_code", "hospital_code", "drug_group", "drug_group_source", "cutoff_month"]
HISTORY_COLS = [
    "purchase_count_asof_cutoff",
    "active_month_count_asof_cutoff",
    "months_observed_asof_cutoff",
    "adi_asof_cutoff",
    "cv2_quantity_asof_cutoff",
]


@dataclass(frozen=True)
class ObservationDisplayConfig:
    display_latest_cutoff_only: bool = True
    display_primary_horizon: str = "H12"
    min_probability_quantile: float = 0.80
    min_value_quantile: float = 0.80
    manufacturer_observation_top_n: int = 20


def load_csv_if_exists(path: Path) -> pd.DataFrame | None:
    return pd.read_csv(path) if path.exists() else None


def normalize_month_column(df: pd.DataFrame, column: str) -> pd.DataFrame:
    out = df.copy()
    if column in out.columns:
        out[column] = pd.to_datetime(out[column], errors="coerce").dt.to_period("M").astype(str)
    return out


def ensure_drug_group_source(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "drug_group_source" not in out.columns:
        out["drug_group_source"] = "drug_code"
    return out


def add_entity_key(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ENTITY_COLS:
        if col not in out.columns:
            out[col] = ""
    out["entity_key"] = out[ENTITY_COLS].astype(str).agg("|".join, axis=1)
    return out


def horizon_label(series: pd.Series) -> pd.Series:
    return series.astype(str).str.replace("H", "", regex=False).astype("Int64").astype(str).radd("H")


def join_observation_history(obs: pd.DataFrame, features: pd.DataFrame | None) -> pd.DataFrame:
    work = normalize_month_column(ensure_drug_group_source(obs), "cutoff_month")
    if features is None or features.empty:
        return work
    feat = normalize_month_column(ensure_drug_group_source(features), "cutoff_month")
    join_cols = [c for c in KEY_COLS if c in work.columns and c in feat.columns]
    keep_cols = join_cols + [
        c
        for c in [
            *HISTORY_COLS,
            "historical_avg_monthly_amount_asof_cutoff",
            "purchase_amount_sum_last_12m_asof_cutoff",
            "purchase_amount_sum_last_6m_asof_cutoff",
            "purchase_amount_sum_last_3m_asof_cutoff",
        ]
        if c in feat.columns
    ]
    if not join_cols:
        return work
    return work.merge(feat[keep_cols].drop_duplicates(join_cols), on=join_cols, how="left")


def add_relative_value_for_observation(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "relative_value_at_risk_H" in out.columns:
        return out
    horizon = pd.to_numeric(out.get("horizon", pd.Series(np.nan, index=out.index)), errors="coerce")
    monthly = pd.Series(np.nan, index=out.index, dtype="float64")
    for col, multiplier in [
        ("historical_avg_monthly_amount_asof_cutoff", 1.0),
        ("purchase_amount_sum_last_12m_asof_cutoff", 1 / 12),
        ("purchase_amount_sum_last_6m_asof_cutoff", 1 / 6),
        ("purchase_amount_sum_last_3m_asof_cutoff", 1 / 3),
    ]:
        if col in out.columns:
            monthly = monthly.fillna(pd.to_numeric(out[col], errors="coerce") * multiplier)
    out["relative_value_at_risk_H"] = (monthly * horizon).clip(lower=0)
    out["relative_business_priority_score_H"] = (
        pd.to_numeric(out.get("churn_probability_H", pd.Series(np.nan, index=out.index)), errors="coerce")
        * out["relative_value_at_risk_H"]
    )
    return out


def add_history_sufficiency_flags(enriched_obs: pd.DataFrame) -> pd.DataFrame:
    out = enriched_obs.copy()
    for col in HISTORY_COLS:
        if col not in out.columns:
            out[col] = np.nan
    purchase = pd.to_numeric(out["purchase_count_asof_cutoff"], errors="coerce")
    active = pd.to_numeric(out["active_month_count_asof_cutoff"], errors="coerce")
    months = pd.to_numeric(out["months_observed_asof_cutoff"], errors="coerce")
    adi_missing = out["adi_asof_cutoff"].isna()
    cv2_missing = out["cv2_quantity_asof_cutoff"].isna()
    required_missing = purchase.isna() | active.isna()

    flag = pd.Series("history_sufficient", index=out.index, dtype="object")
    reason = pd.Series("purchase_count>=3_and_active_month_count>=2", index=out.index, dtype="object")
    medium = (months.notna() & months.lt(12)) | (adi_missing ^ cv2_missing)
    flag.loc[medium] = "history_medium"
    reason.loc[medium] = "short_months_observed_or_partial_interval_statistics"
    insufficient = purchase.lt(3) | active.lt(2) | (adi_missing & cv2_missing)
    flag.loc[insufficient] = "history_insufficient"
    reason.loc[purchase.lt(3)] = "purchase_count_asof_cutoff_lt_3"
    reason.loc[active.lt(2)] = "active_month_count_asof_cutoff_lt_2"
    reason.loc[adi_missing & cv2_missing] = "adi_and_cv2_missing_cannot_reliably_classify"
    flag.loc[required_missing] = "unknown"
    reason.loc[required_missing] = "required_history_fields_missing"

    out["history_sufficiency_flag"] = flag
    out["history_sufficiency_reason"] = reason
    return out


def display_ready_observations(
    enriched_obs: pd.DataFrame,
    *,
    config: ObservationDisplayConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    cfg = config or ObservationDisplayConfig()
    raw = add_relative_value_for_observation(add_history_sufficiency_flags(enriched_obs))
    raw = normalize_month_column(raw, "cutoff_month")
    if raw.empty:
        return raw.copy(), pd.DataFrame()
    work = raw.copy()
    work["horizon_label"] = horizon_label(work["horizon"]) if "horizon" in work.columns else ""
    latest_cutoff = work["cutoff_month"].dropna().max() if "cutoff_month" in work.columns else None
    work["filter_latest_cutoff_pass"] = True
    if cfg.display_latest_cutoff_only and latest_cutoff is not None:
        work["filter_latest_cutoff_pass"] = work["cutoff_month"].eq(latest_cutoff)
    group_cols = [c for c in ["cutoff_month", "horizon", "manufacturer_code"] if c in work.columns]
    if "churn_probability_H" in work.columns and group_cols:
        work["probability_quantile_within_group"] = work.groupby(group_cols, dropna=False)["churn_probability_H"].rank(
            pct=True, method="average"
        )
    else:
        work["probability_quantile_within_group"] = np.nan
    if "relative_value_at_risk_H" in work.columns and group_cols:
        work["value_quantile_within_group"] = work.groupby(group_cols, dropna=False)["relative_value_at_risk_H"].rank(
            pct=True, method="average"
        )
    else:
        work["value_quantile_within_group"] = np.nan
    explicit_guardrail = work.get("demand_shape_route", pd.Series("", index=work.index)).astype(str).eq("observation_only")
    primary_horizon = work["horizon_label"].eq(cfg.display_primary_horizon)
    high_probability = work["probability_quantile_within_group"].ge(cfg.min_probability_quantile)
    high_value = work["value_quantile_within_group"].ge(cfg.min_value_quantile)
    work["filter_history_pass"] = ~work["history_sufficiency_flag"].eq("history_insufficient")
    work["filter_signal_pass"] = primary_horizon | high_probability | high_value | explicit_guardrail
    work["display_filter_pass_before_topn"] = (
        work["filter_latest_cutoff_pass"] & work["filter_history_pass"] & work["filter_signal_pass"]
    )
    work["display_priority_score"] = (
        work[["probability_quantile_within_group", "value_quantile_within_group"]]
        .max(axis=1, skipna=True)
        .fillna(pd.to_numeric(work.get("churn_probability_H", pd.Series(0, index=work.index)), errors="coerce").fillna(0))
    )
    display = work[work["display_filter_pass_before_topn"]].copy()
    if not display.empty:
        display["horizon_priority"] = np.where(display["horizon_label"].eq(cfg.display_primary_horizon), 1, 0)
        display = display.sort_values(
            ["manufacturer_code", "horizon_priority", "display_priority_score", "churn_probability_H"],
            ascending=[True, False, False, False],
        )
        display["rank_within_manufacturer_display"] = display.groupby("manufacturer_code", dropna=False).cumcount() + 1
        display = display[
            display["rank_within_manufacturer_display"].le(cfg.manufacturer_observation_top_n)
        ].copy()
        display["display_ready_reason"] = np.select(
            [
                display["horizon_label"].eq(cfg.display_primary_horizon),
                display["probability_quantile_within_group"].ge(cfg.min_probability_quantile),
                display["value_quantile_within_group"].ge(cfg.min_value_quantile),
                display.get("demand_shape_route", pd.Series("", index=display.index)).astype(str).eq("observation_only"),
            ],
            [
                "primary_horizon_H12",
                "manufacturer_cutoff_horizon_probability_top20pct",
                "manufacturer_cutoff_horizon_value_top20pct",
                "explicit_observation_only_guardrail",
            ],
            default="display_filter_pass",
        )
    audit_rows = [
        {"filter_stage": "raw", "row_count": int(len(work)), "note": "raw observation rows retained separately"},
        {
            "filter_stage": "latest_cutoff",
            "row_count": int(work["filter_latest_cutoff_pass"].sum()),
            "note": f"display_latest_cutoff_only={cfg.display_latest_cutoff_only}",
        },
        {
            "filter_stage": "history_sufficiency",
            "row_count": int((work["filter_latest_cutoff_pass"] & work["filter_history_pass"]).sum()),
            "note": "history_insufficient excluded from strong display",
        },
        {
            "filter_stage": "signal_filter",
            "row_count": int(work["display_filter_pass_before_topn"].sum()),
            "note": "primary horizon, high probability/value quantile, or explicit observation guardrail",
        },
        {
            "filter_stage": "manufacturer_top_n",
            "row_count": int(len(display)),
            "note": f"manufacturer_observation_top_n={cfg.manufacturer_observation_top_n}",
        },
    ]
    return display.reset_index(drop=True), pd.DataFrame(audit_rows)


def raw_observation_profile(enriched_obs: pd.DataFrame, display: pd.DataFrame) -> pd.DataFrame:
    work = add_entity_key(normalize_month_column(enriched_obs, "cutoff_month"))
    total_rows = len(work)
    latest = work["cutoff_month"].dropna().max() if "cutoff_month" in work.columns and not work.empty else ""
    latest_part = work[work["cutoff_month"].eq(latest)] if latest else work.iloc[0:0]
    duplicate = 0
    if set(KEY_COLS + ["horizon"]).issubset(work.columns):
        duplicate = int(total_rows - work[KEY_COLS + ["horizon"]].drop_duplicates().shape[0])
    rows = [
        {"metric": "total_rows", "value": total_rows},
        {"metric": "display_ready_rows", "value": len(display)},
        {"metric": "display_ready_compression_ratio", "value": len(display) / total_rows if total_rows else np.nan},
        {"metric": "unique_entity_count", "value": int(work["entity_key"].nunique()) if not work.empty else 0},
        {
            "metric": "unique_entity_cutoff_count",
            "value": int(work[ENTITY_COLS + ["cutoff_month"]].drop_duplicates().shape[0]) if not work.empty else 0,
        },
        {
            "metric": "unique_entity_cutoff_horizon_count",
            "value": int(work[ENTITY_COLS + ["cutoff_month", "horizon"]].drop_duplicates().shape[0]) if "horizon" in work.columns and not work.empty else 0,
        },
        {"metric": "cutoff_count", "value": int(work["cutoff_month"].nunique()) if "cutoff_month" in work.columns else 0},
        {"metric": "latest_cutoff", "value": latest},
        {"metric": "latest_cutoff_rows", "value": int(len(latest_part))},
        {"metric": "latest_cutoff_unique_entity_count", "value": int(latest_part["entity_key"].nunique()) if not latest_part.empty else 0},
        {"metric": "avg_rows_per_entity", "value": total_rows / work["entity_key"].nunique() if total_rows else np.nan},
        {
            "metric": "avg_rows_per_entity_cutoff",
            "value": total_rows / work[ENTITY_COLS + ["cutoff_month"]].drop_duplicates().shape[0] if total_rows else np.nan,
        },
        {"metric": "duplicate_entity_cutoff_horizon_rows", "value": duplicate},
    ]
    for prefix, col in [
        ("rows_by_horizon", "horizon"),
        ("rows_by_demand_shape_label", "demand_shape_label"),
        ("rows_by_observation_reason", "observation_reason"),
        ("rows_by_history_sufficiency_flag", "history_sufficiency_flag"),
    ]:
        if col in work.columns:
            for key, count in work[col].fillna("__MISSING__").astype(str).value_counts().items():
                rows.append({"metric": f"{prefix}:{key}", "value": int(count)})
    return pd.DataFrame(rows)


def check_recurring_business_priority(
    recurring: pd.DataFrame,
    one_shot: pd.DataFrame | None = None,
    observation: pd.DataFrame | None = None,
) -> pd.DataFrame:
    out = normalize_month_column(ensure_drug_group_source(recurring), "cutoff_month")
    out = add_entity_key(out)
    dup = out.duplicated(KEY_COLS, keep=False) if set(KEY_COLS).issubset(out.columns) else pd.Series(False, index=out.index)
    one_entities = set(add_entity_key(one_shot)["entity_key"]) if one_shot is not None and not one_shot.empty else set()
    obs_keys = set()
    if observation is not None and not observation.empty:
        obs = add_entity_key(normalize_month_column(observation, "cutoff_month"))
        obs_keys = set((obs["entity_key"] + "|" + obs["cutoff_month"].astype(str)).tolist())
    out["business_priority_score_available"] = out.get("primary_relative_business_priority_score", pd.Series(np.nan, index=out.index)).notna()
    out["probability_available"] = out.get("primary_churn_probability", pd.Series(np.nan, index=out.index)).notna()
    out["value_available"] = out.get("primary_relative_value_at_risk", pd.Series(np.nan, index=out.index)).notna()
    out["duplicate_entity_cutoff_flag"] = dup
    selected = out.get("selected_horizons", pd.Series("", index=out.index)).fillna("").astype(str)
    out["selected_horizons_valid"] = selected.str.fullmatch(r"H(?:3|6|12)(,H(?:3|6|12))*")
    primary = out.get("primary_horizon", pd.Series("", index=out.index)).fillna("").astype(str)
    out["primary_horizon_valid"] = primary.isin(["H3", "H6", "H12"]) & (
        (~selected.str.contains("H6")) | primary.eq("H6")
    )
    out["overlaps_one_shot_attention"] = out["entity_key"].isin(one_entities)
    out["overlaps_demand_shape_observation"] = (out["entity_key"] + "|" + out["cutoff_month"].astype(str)).isin(obs_keys)
    out["semantic_check_pass"] = (
        out["business_priority_score_available"]
        & out["probability_available"]
        & out["value_available"]
        & ~out["duplicate_entity_cutoff_flag"]
        & out["selected_horizons_valid"]
        & out["primary_horizon_valid"]
    )
    out["check_note"] = np.where(
        out["semantic_check_pass"],
        "business_priority_semantics_ok",
        "check_required",
    )
    out.loc[out["overlaps_one_shot_attention"], "check_note"] += ";overlaps_one_shot_side_table"
    out.loc[out["overlaps_demand_shape_observation"], "check_note"] += ";overlaps_demand_shape_side_table"
    return out


def check_one_shot_attention(one_shot: pd.DataFrame, recurring: pd.DataFrame | None = None) -> pd.DataFrame:
    out = ensure_drug_group_source(one_shot)
    out = add_entity_key(out)
    recurring_entities = set(add_entity_key(recurring)["entity_key"]) if recurring is not None and not recurring.empty else set()
    out["erroneous_churn_probability_column_present"] = any("churn_probability" in c for c in out.columns)
    out["probability_available_false"] = out.get("probability_available", pd.Series(False, index=out.index)).astype(str).str.lower().isin(["false", "0"])
    out["probability_interpretation_valid"] = out.get("probability_interpretation", pd.Series("", index=out.index)).astype(str).eq("not_recurring_churn_probability")
    out["overlaps_recurring_main_entity"] = out["entity_key"].isin(recurring_entities)
    out["one_shot_value_score_available"] = out.get("one_shot_value_score", pd.Series(np.nan, index=out.index)).notna()
    out["attention_reason_available"] = out.get("attention_reason", pd.Series("", index=out.index)).fillna("").astype(str).ne("")
    out["semantic_check_pass"] = (
        ~out["erroneous_churn_probability_column_present"]
        & out["probability_available_false"]
        & out["probability_interpretation_valid"]
        & out["one_shot_value_score_available"]
        & out["attention_reason_available"]
    )
    return out


def audit_m2_semantics(
    enriched: pd.DataFrame | None,
    *,
    explanation_factors: pd.DataFrame | None = None,
    leakage_audit_exists: bool = False,
    metrics_exists: bool = False,
    training_summary: pd.DataFrame | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    if enriched is None or enriched.empty:
        return pd.DataFrame(
            [{"check_name": "m2_output_available", "status": "missing", "affected_rows": 0, "detail": "M2 enriched output not available"}]
        )
    prob = pd.to_numeric(enriched.get("repeat_probability_H", pd.Series(np.nan, index=enriched.index)), errors="coerce")
    risk = pd.to_numeric(enriched.get("one_shot_non_repeat_risk_H", pd.Series(np.nan, index=enriched.index)), errors="coerce")
    rows.extend(
        [
            {
                "check_name": "repeat_probability_range",
                "status": "pass" if prob.between(0, 1).all() else "fail",
                "affected_rows": int((~prob.between(0, 1)).sum()),
                "detail": "repeat_probability_H must be in [0,1]",
            },
            {
                "check_name": "non_repeat_risk_complement",
                "status": "pass" if np.isclose((1 - prob.fillna(0)) - risk.fillna(0), 0, atol=1e-6).all() else "fail",
                "affected_rows": int((~np.isclose((1 - prob.fillna(0)) - risk.fillna(0), 0, atol=1e-6)).sum()),
                "detail": "one_shot_non_repeat_risk_H must equal 1-repeat_probability_H",
            },
            {
                "check_name": "no_recurring_churn_probability_column",
                "status": "pass" if not any("churn_probability" in c for c in enriched.columns) else "fail",
                "affected_rows": int(len(enriched)) if any("churn_probability" in c for c in enriched.columns) else 0,
                "detail": "one-shot M2 output must not expose recurring churn probability",
            },
            {
                "check_name": "probability_interpretation",
                "status": "pass"
                if enriched.get("probability_interpretation", pd.Series("", index=enriched.index)).astype(str).eq(
                    "first_purchase_repeat_probability_not_recurring_churn_probability"
                ).all()
                else "fail",
                "affected_rows": int(
                    (~enriched.get("probability_interpretation", pd.Series("", index=enriched.index)).astype(str).eq(
                        "first_purchase_repeat_probability_not_recurring_churn_probability"
                    )).sum()
                ),
                "detail": "interpretation must distinguish repeat probability from recurring churn",
            },
        ]
    )
    for col in [
        "one_shot_retention_risk_score_H",
        "one_shot_conversion_opportunity_score_H",
        "one_shot_balanced_attention_score_H",
        "selected_attention_policy",
    ]:
        rows.append(
            {
                "check_name": f"{col}_exists",
                "status": "pass" if col in enriched.columns else "fail",
                "affected_rows": 0 if col in enriched.columns else int(len(enriched)),
                "detail": col,
            }
        )
    explanation_ok = explanation_factors is not None and not explanation_factors.empty and len(explanation_factors) >= len(enriched)
    rows.extend(
        [
            {
                "check_name": "explanation_factors_coverage",
                "status": "pass" if explanation_ok else "warn",
                "affected_rows": int(0 if explanation_ok else len(enriched)),
                "detail": f"explanation_rows={0 if explanation_factors is None else len(explanation_factors)}; enriched_rows={len(enriched)}",
            },
            {
                "check_name": "one_shot_leakage_audit_exists",
                "status": "pass" if leakage_audit_exists else "warn",
                "affected_rows": 0,
                "detail": str(leakage_audit_exists),
            },
            {
                "check_name": "one_shot_repeat_metrics_exists",
                "status": "pass" if metrics_exists else "warn",
                "affected_rows": 0,
                "detail": str(metrics_exists),
            },
        ]
    )
    if training_summary is not None and not training_summary.empty:
        for _, row in training_summary.iterrows():
            rows.append(
                {
                    "check_name": f"{row.get('horizon')}_training_or_fallback_status",
                    "status": "pass",
                    "affected_rows": 0,
                    "detail": f"train_rows={row.get('train_row_count')}; test_rows={row.get('test_row_count')}; skip_reason={row.get('skip_reason')}",
                }
            )
    return pd.DataFrame(rows)
