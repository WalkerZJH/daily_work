"""Candidate-pool helpers for alive/churn die prediction M1.

M1 separates three logical outputs:

* recurring business-priority candidates, ranked by probability times value;
* one-shot attention candidates, as a side table without churn probability;
* demand-shape observation candidates, as a side table without priority union.

The helpers here do not train models and do not write artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd


KEY_COLS = ["manufacturer_code", "hospital_code", "drug_group", "drug_group_source", "cutoff_month"]
ENTITY_COLS = ["manufacturer_code", "hospital_code", "drug_group"]
PROBABILITY_CANDIDATE_VERSION = "logistic_regression + frequency_decay_v1 + raw"
VALUE_FALLBACKS = [
    ("historical_avg_monthly_amount_asof_cutoff", 1.0, "historical_avg_monthly_amount_asof_cutoff"),
    ("purchase_amount_sum_last_12m_asof_cutoff", 1 / 12, "purchase_amount_sum_last_12m_asof_cutoff_div_12"),
    ("purchase_amount_sum_last_6m_asof_cutoff", 1 / 6, "purchase_amount_sum_last_6m_asof_cutoff_div_6"),
    ("purchase_amount_sum_last_3m_asof_cutoff", 1 / 3, "purchase_amount_sum_last_3m_asof_cutoff_div_3"),
]


@dataclass(frozen=True)
class CandidatePoolConfig:
    global_top_pct: float = 0.05
    manufacturer_min_candidates: int = 3
    default_primary_horizon: int = 6
    probability_candidate_version: str = PROBABILITY_CANDIDATE_VERSION


def ensure_drug_group_source(df: pd.DataFrame, source: str = "drug_code") -> pd.DataFrame:
    out = df.copy()
    if "drug_group_source" not in out.columns:
        out["drug_group_source"] = source
    return out


def candidate_id(df: pd.DataFrame, *, include_horizon: bool = False) -> pd.Series:
    cols = KEY_COLS + (["horizon"] if include_horizon else [])
    return df[cols].astype(str).agg("|".join, axis=1)


def compute_relative_value_at_risk(df: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Compute relative value exposure with documented fallbacks.

    Amount fields are treated as relative/desensitized values, not real currency.
    """

    out = df.copy()
    monthly = pd.Series(np.nan, index=out.index, dtype="float64")
    source = pd.Series("", index=out.index, dtype="string")
    for column, multiplier, source_name in VALUE_FALLBACKS:
        if column not in out.columns:
            continue
        values = pd.to_numeric(out[column], errors="coerce") * multiplier
        mask = monthly.isna() & values.notna()
        monthly.loc[mask] = values.loc[mask]
        source.loc[mask] = source_name
    out[f"relative_value_at_risk_H{horizon}"] = (monthly * horizon).clip(lower=0)
    out[f"relative_value_source_H{horizon}"] = source.fillna("")
    out[f"value_missing_H{horizon}"] = out[f"relative_value_at_risk_H{horizon}"].isna()
    return out


def make_horizon_scored_frame(
    df: pd.DataFrame,
    *,
    horizon: int,
    probability: Iterable[float] | pd.Series | np.ndarray,
    probability_candidate_version: str = PROBABILITY_CANDIDATE_VERSION,
) -> pd.DataFrame:
    out = ensure_drug_group_source(df)
    out["horizon"] = int(horizon)
    out["churn_probability_H"] = np.clip(np.asarray(probability, dtype=float), 1e-15, 1 - 1e-15)
    out = compute_relative_value_at_risk(out, int(horizon))
    out["relative_value_at_risk_H"] = out[f"relative_value_at_risk_H{horizon}"]
    out["relative_value_source"] = out[f"relative_value_source_H{horizon}"]
    out["relative_business_priority_score_H"] = out["churn_probability_H"] * out["relative_value_at_risk_H"]
    out["probability_candidate_version"] = probability_candidate_version
    if "demand_shape_label" not in out.columns:
        out["demand_shape_label"] = "__MISSING__"
    return out


def rank_business_priority(scored_long: pd.DataFrame) -> pd.DataFrame:
    out = scored_long.copy()
    group_cols = ["cutoff_month", "horizon"]
    out["rank_global"] = (
        out.groupby(group_cols, dropna=False)["relative_business_priority_score_H"]
        .rank(method="first", ascending=False)
        .astype(int)
    )
    out["rank_within_manufacturer"] = (
        out.groupby(group_cols + ["manufacturer_code"], dropna=False)["relative_business_priority_score_H"]
        .rank(method="first", ascending=False)
        .astype(int)
    )
    return out


def select_recurring_business_priority_candidates(
    scored_long: pd.DataFrame,
    *,
    config: CandidatePoolConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Select global top pct plus manufacturer minimum fill by cutoff/horizon."""

    cfg = config or CandidatePoolConfig()
    eligible = ensure_drug_group_source(scored_long)
    input_count = int(len(eligible))
    eligible = eligible[eligible["relative_business_priority_score_H"].notna()].copy()
    eligible = rank_business_priority(eligible)
    selected_frames: list[pd.DataFrame] = []
    audit_rows: list[dict[str, object]] = []
    missing_count = input_count - len(eligible)

    for (cutoff, horizon), group in eligible.groupby(["cutoff_month", "horizon"], dropna=False, sort=True):
        cutoff_horizon_count = int(len(group))
        top_n = max(1, int(np.ceil(cutoff_horizon_count * cfg.global_top_pct))) if cutoff_horizon_count else 0
        global_selected = group[group["rank_global"] <= top_n].copy()
        global_selected["selection_reason"] = "global_top5pct"
        global_selected["selection_note"] = ""
        selected_parts = [global_selected]
        global_keys = set(global_selected.index)
        fill_count = 0
        less_than_min_count = 0
        for manufacturer, mfg in group.groupby("manufacturer_code", dropna=False, sort=True):
            current_count = int(global_selected[global_selected["manufacturer_code"].eq(manufacturer)].shape[0])
            if len(mfg) < cfg.manufacturer_min_candidates:
                need = max(0, len(mfg) - current_count)
                note = "available_entities_less_than_minimum"
                reason = "available_entities_less_than_minimum"
            else:
                need = max(0, cfg.manufacturer_min_candidates - current_count)
                note = ""
                reason = "manufacturer_min_fill"
            if need <= 0:
                continue
            supplement = mfg[~mfg.index.isin(global_keys)].sort_values(
                ["relative_business_priority_score_H", "rank_within_manufacturer"],
                ascending=[False, True],
            ).head(need).copy()
            if supplement.empty:
                continue
            supplement["selection_reason"] = reason
            supplement["selection_note"] = note
            selected_parts.append(supplement)
            if reason == "manufacturer_min_fill":
                fill_count += int(len(supplement))
            else:
                less_than_min_count += int(len(supplement))
        selected = pd.concat(selected_parts, ignore_index=False) if selected_parts else group.iloc[0:0].copy()
        selected_frames.append(selected)
        audit_rows.extend(
            [
                {
                    "candidate_id": "",
                    "table_name": "recurring_business_priority_candidates_by_horizon",
                    "selection_reason": "global_top5pct",
                    "selection_stage": "global_top_pct",
                    "input_row_count": input_count,
                    "eligible_row_count": cutoff_horizon_count,
                    "selected_row_count": int(len(global_selected)),
                    "manufacturer_code": "",
                    "horizon": int(horizon),
                    "cutoff_month": cutoff,
                    "note": f"top_pct={cfg.global_top_pct}",
                },
                {
                    "candidate_id": "",
                    "table_name": "recurring_business_priority_candidates_by_horizon",
                    "selection_reason": "manufacturer_min_fill",
                    "selection_stage": "manufacturer_min_fill",
                    "input_row_count": input_count,
                    "eligible_row_count": cutoff_horizon_count,
                    "selected_row_count": fill_count,
                    "manufacturer_code": "",
                    "horizon": int(horizon),
                    "cutoff_month": cutoff,
                    "note": f"manufacturer_min_candidates={cfg.manufacturer_min_candidates}",
                },
                {
                    "candidate_id": "",
                    "table_name": "recurring_business_priority_candidates_by_horizon",
                    "selection_reason": "available_entities_less_than_minimum",
                    "selection_stage": "manufacturer_min_fill",
                    "input_row_count": input_count,
                    "eligible_row_count": cutoff_horizon_count,
                    "selected_row_count": less_than_min_count,
                    "manufacturer_code": "",
                    "horizon": int(horizon),
                    "cutoff_month": cutoff,
                    "note": "manufacturer available recurring entities less than minimum",
                },
            ]
        )

    if missing_count:
        audit_rows.append(
            {
                "candidate_id": "",
                "table_name": "recurring_business_priority_candidates_by_horizon",
                "selection_reason": "value_missing",
                "selection_stage": "eligibility",
                "input_row_count": input_count,
                "eligible_row_count": int(len(eligible)),
                "selected_row_count": 0,
                "manufacturer_code": "",
                "horizon": "",
                "cutoff_month": "",
                "note": f"rows_without_relative_value_at_risk={missing_count}",
            }
        )
    out = pd.concat(selected_frames, ignore_index=True) if selected_frames else eligible.iloc[0:0].copy()
    if not out.empty:
        out["candidate_id"] = candidate_id(out, include_horizon=True)
    return format_horizon_candidates(out), pd.DataFrame(audit_rows)


def format_horizon_candidates(df: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "candidate_id",
        "manufacturer_code",
        "hospital_code",
        "drug_group",
        "drug_group_source",
        "cutoff_month",
        "horizon",
        "churn_probability_H",
        "relative_value_at_risk_H",
        "relative_business_priority_score_H",
        "rank_global",
        "rank_within_manufacturer",
        "selection_reason",
        "selection_note",
        "demand_shape_label",
        "probability_candidate_version",
    ]
    out = ensure_drug_group_source(df)
    for column in columns:
        if column not in out.columns:
            out[column] = np.nan
    return out[columns].sort_values(["cutoff_month", "horizon", "rank_global", "manufacturer_code"]).reset_index(drop=True)


def collapse_horizon_candidates(
    by_horizon: pd.DataFrame,
    *,
    config: CandidatePoolConfig | None = None,
) -> pd.DataFrame:
    cfg = config or CandidatePoolConfig()
    if by_horizon.empty:
        columns = [
            "candidate_id",
            *KEY_COLS,
            "selected_horizons",
            "primary_horizon",
            "primary_churn_probability",
            "primary_relative_value_at_risk",
            "primary_relative_business_priority_score",
            "candidate_selection_reasons",
            "rank_global_primary_horizon",
            "rank_within_manufacturer_primary_horizon",
            "demand_shape_label",
            "probability_candidate_version",
        ]
        return pd.DataFrame(columns=columns)
    work = ensure_drug_group_source(by_horizon).copy()
    rows: list[dict[str, object]] = []
    for keys, group in work.groupby(KEY_COLS, dropna=False, sort=True):
        group = group.sort_values("horizon")
        h6 = group[group["horizon"].eq(cfg.default_primary_horizon)]
        if not h6.empty:
            primary = h6.sort_values("relative_business_priority_score_H", ascending=False).iloc[0]
        else:
            primary = group.sort_values("relative_business_priority_score_H", ascending=False).iloc[0]
        rows.append(
            {
                "candidate_id": "|".join(map(str, keys)),
                **dict(zip(KEY_COLS, keys)),
                "selected_horizons": ",".join(f"H{int(h)}" for h in sorted(group["horizon"].astype(int).unique())),
                "primary_horizon": f"H{int(primary['horizon'])}",
                "primary_churn_probability": primary["churn_probability_H"],
                "primary_relative_value_at_risk": primary["relative_value_at_risk_H"],
                "primary_relative_business_priority_score": primary["relative_business_priority_score_H"],
                "candidate_selection_reasons": ";".join(sorted(group["selection_reason"].dropna().astype(str).unique())),
                "rank_global_primary_horizon": primary["rank_global"],
                "rank_within_manufacturer_primary_horizon": primary["rank_within_manufacturer"],
                "demand_shape_label": primary.get("demand_shape_label", "__MISSING__"),
                "probability_candidate_version": primary.get("probability_candidate_version", cfg.probability_candidate_version),
            }
        )
    return pd.DataFrame(rows).sort_values(["cutoff_month", "primary_relative_business_priority_score"], ascending=[True, False]).reset_index(drop=True)


def build_one_shot_attention_candidates(source: pd.DataFrame | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    columns = [
        "manufacturer_code",
        "hospital_code",
        "drug_group",
        "drug_group_source",
        "first_purchase_month",
        "one_shot_value_score",
        "attention_reason",
        "probability_available",
        "probability_interpretation",
    ]
    if source is None or source.empty:
        table = pd.DataFrame(columns=columns)
        audit = pd.DataFrame(
            [
                {
                    "candidate_id": "",
                    "table_name": "one_shot_attention_candidates",
                    "selection_reason": "source_unavailable_or_empty",
                    "selection_stage": "passthrough",
                    "input_row_count": 0 if source is None else int(len(source)),
                    "eligible_row_count": 0,
                    "selected_row_count": 0,
                    "manufacturer_code": "",
                    "horizon": "",
                    "cutoff_month": "",
                    "note": "one_shot_attention_candidates not generated because source artifact was unavailable or empty",
                }
            ]
        )
        return table, audit
    work = ensure_drug_group_source(source)
    value_score = pd.Series(np.nan, index=work.index, dtype="float64")
    for column in ["historical_avg_monthly_amount_asof_cutoff", "purchase_amount_sum_last_12m_asof_cutoff", "purchase_amount_sum_last_6m_asof_cutoff", "purchase_amount_sum_last_3m_asof_cutoff"]:
        if column in work.columns:
            values = pd.to_numeric(work[column], errors="coerce")
            value_score = value_score.fillna(values)
    out = pd.DataFrame(
        {
            "manufacturer_code": work["manufacturer_code"],
            "hospital_code": work["hospital_code"],
            "drug_group": work["drug_group"],
            "drug_group_source": work["drug_group_source"],
            "first_purchase_month": work.get("first_purchase_month_asof_cutoff", work.get("first_purchase_month", "")),
            "one_shot_value_score": value_score,
            "attention_reason": "one_shot_high_value_attention_passthrough",
            "probability_available": False,
            "probability_interpretation": "not_recurring_churn_probability",
        }
    ).drop_duplicates(subset=["manufacturer_code", "hospital_code", "drug_group", "drug_group_source", "first_purchase_month"])
    audit = pd.DataFrame(
        [
            {
                "candidate_id": "",
                "table_name": "one_shot_attention_candidates",
                "selection_reason": "source_passthrough",
                "selection_stage": "passthrough",
                "input_row_count": int(len(source)),
                "eligible_row_count": int(len(out)),
                "selected_row_count": int(len(out)),
                "manufacturer_code": "",
                "horizon": "",
                "cutoff_month": "",
                "note": "probability_available=false; no recurring churn_probability generated",
            }
        ]
    )
    return out[columns].reset_index(drop=True), audit


def build_demand_shape_observation_candidates(scored_long: pd.DataFrame, probability_threshold: float = 0.75) -> tuple[pd.DataFrame, pd.DataFrame]:
    work = ensure_drug_group_source(scored_long).copy()
    if "demand_shape_label" not in work.columns:
        work["demand_shape_label"] = "__MISSING__"
    intermittent_h3 = work["demand_shape_label"].eq("intermittent") & work["horizon"].eq(3) & (work["churn_probability_H"] >= probability_threshold)
    lumpy_high = work["demand_shape_label"].eq("lumpy") & (work["churn_probability_H"] >= probability_threshold)
    obs = work[intermittent_h3 | lumpy_high].copy()
    if obs.empty:
        columns = [
            "manufacturer_code",
            "hospital_code",
            "drug_group",
            "drug_group_source",
            "cutoff_month",
            "horizon",
            "churn_probability_H",
            "demand_shape_label",
            "demand_shape_route",
            "observation_reason",
            "recommended_observation_window",
            "probability_interpretation",
        ]
        return pd.DataFrame(columns=columns), _observation_audit(0, 0)
    obs["demand_shape_route"] = np.where(obs["demand_shape_label"].eq("lumpy"), "observation_only", "longer_horizon_only")
    obs["observation_reason"] = np.where(
        obs["demand_shape_label"].eq("intermittent") & obs["horizon"].eq(3),
        "intermittent_H3_observation_only",
        "lumpy_high_risk_low_confidence",
    )
    obs["recommended_observation_window"] = np.where(obs["demand_shape_label"].eq("intermittent"), "H12", "H12_or_observation_only")
    obs["probability_interpretation"] = "recurring_churn_probability_with_demand_shape_guardrail"
    columns = [
        "manufacturer_code",
        "hospital_code",
        "drug_group",
        "drug_group_source",
        "cutoff_month",
        "horizon",
        "churn_probability_H",
        "demand_shape_label",
        "demand_shape_route",
        "observation_reason",
        "recommended_observation_window",
        "probability_interpretation",
    ]
    return obs[columns].reset_index(drop=True), _observation_audit(len(work), len(obs))


def _observation_audit(input_count: int, selected_count: int) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "candidate_id": "",
                "table_name": "demand_shape_observation_candidates",
                "selection_reason": "demand_shape_guardrail",
                "selection_stage": "observation_side_table",
                "input_row_count": int(input_count),
                "eligible_row_count": int(input_count),
                "selected_row_count": int(selected_count),
                "manufacturer_code": "",
                "horizon": "",
                "cutoff_month": "",
                "note": "side table only; not unioned into recurring business-priority candidates",
            }
        ]
    )
