"""M5 evidence fusion and candidate status decision prototype.

M5 is a rule-based status layer. It consumes M1/M2/M3/M4 structured outputs
and does not recalculate probabilities, business-priority scores, or detector
evidence.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


IMPLEMENTED_DETECTORS = {
    "terminal_loss_warning",
    "purchase_frequency_fluctuation_warning",
    "purchase_quantity_fluctuation_warning",
    "new_terminal_detection",
}
INTERFACE_ONLY_DETECTORS = {
    "low_price_purchase_warning",
    "order_price_spread_warning",
    "rejection_response_warning",
    "delayed_response_warning",
    "low_delivery_rate_warning",
}
DECISION_COLUMNS = [
    "candidate_id",
    "candidate_type",
    "manufacturer_code",
    "hospital_code",
    "drug_group",
    "drug_group_source",
    "cutoff_month",
    "horizon",
    "final_candidate_status",
    "review_priority",
    "evidence_strength",
    "human_review_required",
    "auto_dispatch_allowed",
    "churn_probability_H",
    "churn_probability_interpretation",
    "repeat_probability_H",
    "repeat_probability_interpretation",
    "relative_value_at_risk_H",
    "relative_business_priority_score_H",
    "business_priority_interpretation",
    "survival_state",
    "survival_confidence",
    "overdue_ratio",
    "history_sufficiency_flag",
    "demand_shape_label",
    "demand_shape_route",
    "guardrail_status",
    "detector_hit_count",
    "strong_detector_hit_count",
    "implemented_detector_hit_count",
    "interface_only_detector_count",
    "top_detector_reasons",
    "data_quality_warning_flag",
    "probability_reference",
    "business_priority_reference",
    "status_reason",
    "data_quality_note",
    "evidence_timeline_available",
    "evidence_timeline_reference",
    "evidence_persistence_summary",
]


def load_csv_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def normalize_bool(series: pd.Series) -> pd.Series:
    if series.empty:
        return series.astype(bool)
    if series.dtype == bool:
        return series.fillna(False)
    return series.fillna(False).astype(str).str.lower().isin(["true", "1", "yes", "y"])


def as_numeric(series: pd.Series | None, index: pd.Index) -> pd.Series:
    if series is None:
        return pd.Series(np.nan, index=index, dtype="float64")
    return pd.to_numeric(series, errors="coerce")


def normalize_horizon(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.upper().startswith("H"):
        return text.upper()
    if text.endswith(".0"):
        text = text[:-2]
    return f"H{text}" if text else ""


def make_entity_candidate_id(df: pd.DataFrame) -> pd.Series:
    cols = ["manufacturer_code", "hospital_code", "drug_group", "drug_group_source"]
    work = df.copy()
    if "drug_group_source" not in work.columns:
        work["drug_group_source"] = "drug_code"
    return work[cols].fillna("").astype(str).agg("|".join, axis=1)


def _reason_text(group: pd.DataFrame) -> str:
    if group.empty:
        return ""
    hits = group[normalize_bool(group["hit_flag"])].copy()
    if hits.empty:
        return ""
    hits["severity_num"] = pd.to_numeric(hits["severity"], errors="coerce").fillna(0)
    hits = hits.sort_values(["severity_num", "detector_name"], ascending=[False, True]).head(3)
    parts = []
    for _, row in hits.iterrows():
        reason = str(row.get("reason_code", ""))
        interp = str(row.get("business_interpretation", ""))
        parts.append(f"{row.get('detector_name', '')}:{reason}:{interp}"[:240])
    return " | ".join(parts)


def aggregate_detector_evidence(evidence: pd.DataFrame) -> pd.DataFrame:
    """Aggregate M4 detector evidence to candidate_id.

    Interface-only detector rows are counted separately and never contribute to
    effective detector hit counts.
    """
    cols = [
        "candidate_id",
        "detector_hit_count",
        "strong_detector_hit_count",
        "implemented_detector_hit_count",
        "interface_only_detector_count",
        "terminal_loss_hit",
        "frequency_hit",
        "quantity_hit",
        "new_terminal_hit",
        "max_implemented_detector_confidence",
        "all_detectors_not_evaluable",
        "top_detector_reasons",
    ]
    if evidence is None or evidence.empty or "candidate_id" not in evidence.columns:
        return pd.DataFrame(columns=cols)

    work = evidence.copy()
    work["hit_bool"] = normalize_bool(work.get("hit_flag", pd.Series(False, index=work.index)))
    work["detector_name"] = work.get("detector_name", pd.Series("", index=work.index)).fillna("").astype(str)
    work["data_quality_status"] = work.get("data_quality_status", pd.Series("", index=work.index)).fillna("").astype(str)
    work["severity_num"] = pd.to_numeric(work.get("severity", pd.Series(np.nan, index=work.index)), errors="coerce")
    work["confidence_num"] = pd.to_numeric(work.get("confidence", pd.Series(np.nan, index=work.index)), errors="coerce")
    work["is_interface_only"] = work["detector_name"].isin(INTERFACE_ONLY_DETECTORS)
    work["is_implemented"] = work["detector_name"].isin(IMPLEMENTED_DETECTORS)
    work["is_effective_hit"] = (
        work["hit_bool"]
        & work["is_implemented"]
        & work["data_quality_status"].ne("not_evaluable")
        & ~work["is_interface_only"]
    )
    work["is_strong_hit"] = work["is_effective_hit"] & work["severity_num"].ge(70) & work["confidence_num"].ge(0.6)
    candidate_rows = work["candidate_id"].fillna("").astype(str).ne("")
    grouped = work[candidate_rows].groupby("candidate_id", dropna=False)
    out = grouped.agg(
        detector_hit_count=("is_effective_hit", "sum"),
        strong_detector_hit_count=("is_strong_hit", "sum"),
        implemented_detector_hit_count=("is_implemented", "sum"),
        interface_only_detector_count=("is_interface_only", "sum"),
        terminal_loss_hit=("is_effective_hit", lambda x: False),
    ).reset_index()
    # Named aggregation cannot easily inspect detector_name alongside flags, so
    # compute named hits in a small loop with grouped indices.
    named = []
    for candidate_id, group in grouped:
        effective = group[group["is_effective_hit"]]
        named.append(
            {
                "candidate_id": candidate_id,
                "terminal_loss_hit": bool(effective["detector_name"].eq("terminal_loss_warning").any()),
                "frequency_hit": bool(effective["detector_name"].eq("purchase_frequency_fluctuation_warning").any()),
                "quantity_hit": bool(effective["detector_name"].eq("purchase_quantity_fluctuation_warning").any()),
                "new_terminal_hit": bool(effective["detector_name"].eq("new_terminal_detection").any()),
                "max_implemented_detector_confidence": pd.to_numeric(
                    effective["confidence_num"], errors="coerce"
                ).max(),
                "all_detectors_not_evaluable": bool(
                    len(group) > 0 and group["data_quality_status"].eq("not_evaluable").all()
                ),
                "top_detector_reasons": _reason_text(group),
            }
        )
    out = out.drop(columns=["terminal_loss_hit"]).merge(pd.DataFrame(named), on="candidate_id", how="left")
    for c in ["detector_hit_count", "strong_detector_hit_count", "implemented_detector_hit_count", "interface_only_detector_count"]:
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0).astype(int)
    return out[cols]


def _business_priority_threshold(series: pd.Series, q: float = 0.8) -> float:
    nums = pd.to_numeric(series, errors="coerce").dropna()
    return float(nums.quantile(q)) if not nums.empty else math.inf


def calculate_recurring_evidence_strength(df: pd.DataFrame) -> pd.Series:
    state = df["survival_state"].fillna("").astype(str)
    route = df["demand_shape_route"].fillna("").astype(str)
    terminal = normalize_bool(df["terminal_loss_hit"])
    frequency = normalize_bool(df["frequency_hit"])
    quantity = normalize_bool(df["quantity_hit"])
    conf = as_numeric(df.get("survival_confidence"), df.index).fillna(0)
    max_det_conf = as_numeric(df.get("max_implemented_detector_confidence"), df.index).fillna(0)
    all_not_eval = normalize_bool(df["all_detectors_not_evaluable"])
    missing_core = df[["candidate_id", "churn_probability_H", "relative_business_priority_score_H"]].isna().any(axis=1)

    strong = (
        terminal
        & state.isin(["materially_overdue", "likely_churn_interval"])
        & conf.ge(0.7)
        & ~route.isin(["observation_only"])
        & max_det_conf.ge(0.6)
    )
    medium = (
        (terminal & conf.lt(0.7))
        | (state.eq("slightly_overdue") & (frequency | quantity))
        | (frequency & quantity)
        | (state.isin(["materially_overdue", "likely_churn_interval"]) & ~strong)
    )
    weak = (
        df["relative_business_priority_score_H"].notna()
        | frequency
        | quantity
        | (state.isin(["normal_interval", "near_expected_interval"]) & (frequency | quantity))
    )
    insufficient = missing_core | all_not_eval | route.eq("unknown")
    out = pd.Series("insufficient", index=df.index, dtype="object")
    out.loc[weak & ~insufficient] = "weak"
    out.loc[medium & ~insufficient] = "medium"
    out.loc[strong & ~insufficient] = "strong"
    out.loc[insufficient] = "insufficient"
    return out


def decide_recurring_status(recurring: pd.DataFrame, survival: pd.DataFrame, detector_agg: pd.DataFrame) -> pd.DataFrame:
    if survival is None or survival.empty:
        return pd.DataFrame(columns=DECISION_COLUMNS)
    base = survival.copy()
    if "drug_group_source" not in base.columns:
        base["drug_group_source"] = "drug_code"
    if "horizon" in base.columns:
        base["horizon"] = base["horizon"].map(normalize_horizon)
    # Merge checked M1 fields only as data-quality context.
    if recurring is not None and not recurring.empty and "candidate_id" in recurring.columns:
        keep = [
            c
            for c in [
                "candidate_id",
                "semantic_check_pass",
                "business_priority_score_available",
                "probability_available",
                "value_available",
                "check_note",
            ]
            if c in recurring.columns
        ]
        base = base.merge(recurring[keep].drop_duplicates("candidate_id"), on="candidate_id", how="left")
    base = base.merge(detector_agg, on="candidate_id", how="left")
    for col in [
        "detector_hit_count",
        "strong_detector_hit_count",
        "implemented_detector_hit_count",
        "interface_only_detector_count",
    ]:
        base[col] = pd.to_numeric(base.get(col, 0), errors="coerce").fillna(0).astype(int)
    for col in ["terminal_loss_hit", "frequency_hit", "quantity_hit", "new_terminal_hit", "all_detectors_not_evaluable"]:
        base[col] = normalize_bool(base.get(col, pd.Series(False, index=base.index)))
    base["top_detector_reasons"] = base.get("top_detector_reasons", pd.Series("", index=base.index)).fillna("")
    base["max_implemented_detector_confidence"] = pd.to_numeric(
        base.get("max_implemented_detector_confidence", pd.Series(np.nan, index=base.index)), errors="coerce"
    )

    base["candidate_type"] = "recurring_business_priority"
    base["evidence_strength"] = calculate_recurring_evidence_strength(base)
    state = base.get("survival_state", pd.Series("", index=base.index)).fillna("").astype(str)
    route = base.get("demand_shape_route", pd.Series("", index=base.index)).fillna("").astype(str)
    shape = base.get("demand_shape_label", pd.Series("", index=base.index)).fillna("").astype(str)
    hist = base.get("history_sufficiency_flag", pd.Series("", index=base.index)).fillna("").astype(str)
    conf = as_numeric(base.get("survival_confidence"), base.index).fillna(0)
    bp = as_numeric(base.get("relative_business_priority_score_H"), base.index)
    prob = as_numeric(base.get("churn_probability_H"), base.index)
    horizon = base.get("horizon", pd.Series("", index=base.index)).fillna("").astype(str)
    missing_core = base["candidate_id"].isna() | prob.isna() | bp.isna()

    priority = (
        state.isin(["materially_overdue", "likely_churn_interval"])
        & ~route.isin(["observation_only"])
        & base["evidence_strength"].isin(["strong", "medium"])
        & bp.notna()
    )
    manual = (
        state.isin(["slightly_overdue", "materially_overdue", "likely_churn_interval"])
        | shape.eq("erratic")
        | (bp.ge(_business_priority_threshold(bp, 0.8)) & base["evidence_strength"].isin(["weak", "insufficient"]))
    )
    observation = (
        route.eq("observation_only")
        | state.eq("low_confidence_lumpy")
        | shape.eq("lumpy")
        | (shape.eq("intermittent") & horizon.eq("H3"))
    )
    low_conf = (
        hist.ne("history_sufficient")
        | conf.lt(0.5)
        | route.eq("unknown")
        | base["all_detectors_not_evaluable"]
    )

    status = pd.Series("not_actionable", index=base.index, dtype="object")
    status.loc[~missing_core] = "manual_review"
    status.loc[low_conf & ~missing_core] = "low_confidence_watch"
    status.loc[manual & ~missing_core] = "manual_review"
    status.loc[priority & ~missing_core] = "priority_review"
    status.loc[observation & ~missing_core] = "observation_only"
    status.loc[missing_core] = "not_actionable"
    base["final_candidate_status"] = status

    bp_top20 = bp.ge(_business_priority_threshold(bp, 0.8))
    review = pd.Series("P3", index=base.index, dtype="object")
    review.loc[base["final_candidate_status"].isin(["observation_only", "low_confidence_watch"]) & bp_top20] = "P2"
    review.loc[
        base["final_candidate_status"].isin(["priority_review", "manual_review"])
        & base["evidence_strength"].isin(["medium", "strong"])
        & bp_top20
    ] = "P1"
    review.loc[
        base["final_candidate_status"].eq("priority_review")
        & base["evidence_strength"].eq("strong")
        & state.isin(["likely_churn_interval", "materially_overdue"])
        & bp_top20
    ] = "P0"
    base["review_priority"] = review
    base["human_review_required"] = base["final_candidate_status"].ne("not_actionable")
    base["data_quality_warning_flag"] = (
        missing_core
        | base.get("semantic_check_pass", pd.Series(True, index=base.index)).fillna(True).astype(str).str.lower().eq("false")
        | base.get("data_quality_note", pd.Series("", index=base.index)).fillna("").astype(str).ne("")
    )
    base["guardrail_status"] = np.where(route.eq("observation_only"), "demand_shape_observation_only", "none")
    base["churn_probability_interpretation"] = "recurring_churn_probability_from_stage1"
    base["repeat_probability_H"] = np.nan
    base["repeat_probability_interpretation"] = ""
    base["business_priority_interpretation"] = "business_priority_score_is_probability_times_relative_value_not_probability"
    base["probability_reference"] = base["churn_probability_H"]
    base["business_priority_reference"] = base["relative_business_priority_score_H"]
    base["status_reason"] = [
        f"status={s}; survival_state={st}; evidence_strength={es}; guardrail={gr}"
        for s, st, es, gr in zip(status, state, base["evidence_strength"], base["guardrail_status"])
    ]
    base["data_quality_note"] = base.get("data_quality_note", pd.Series("", index=base.index)).fillna("")
    return finalize_decision(base)


def decide_one_shot_status(one_shot: pd.DataFrame, detector_agg: pd.DataFrame) -> pd.DataFrame:
    if one_shot is None or one_shot.empty:
        return pd.DataFrame(columns=DECISION_COLUMNS)
    base = one_shot.copy()
    if "drug_group_source" not in base.columns:
        base["drug_group_source"] = "drug_code"
    base["candidate_id"] = make_entity_candidate_id(base)
    if "horizon" in base.columns:
        base["horizon"] = base["horizon"].map(normalize_horizon)
    else:
        base["horizon"] = ""
    base["cutoff_month"] = base.get("first_purchase_month", pd.Series("", index=base.index))
    base = base.merge(detector_agg, on="candidate_id", how="left")
    for col in ["detector_hit_count", "strong_detector_hit_count", "implemented_detector_hit_count", "interface_only_detector_count"]:
        base[col] = pd.to_numeric(base.get(col, 0), errors="coerce").fillna(0).astype(int)
    score = pd.to_numeric(base.get("selected_attention_score", pd.Series(np.nan, index=base.index)), errors="coerce")
    threshold = _business_priority_threshold(score, 0.8)
    base["candidate_type"] = "one_shot_attention"
    base["final_candidate_status"] = "one_shot_attention"
    base["review_priority"] = np.where(score.notna() & score.ge(threshold), "P2", "P3")
    base["evidence_strength"] = np.where(score.notna() & score.ge(threshold), "weak", "insufficient")
    base["human_review_required"] = True
    base["churn_probability_H"] = np.nan
    base["churn_probability_interpretation"] = ""
    base["repeat_probability_interpretation"] = "first_purchase_repeat_probability_not_recurring_churn_probability"
    base["relative_value_at_risk_H"] = np.nan
    base["relative_business_priority_score_H"] = np.nan
    base["business_priority_interpretation"] = "one_shot_attention_score_is_not_business_priority_score"
    base["survival_state"] = ""
    base["survival_confidence"] = np.nan
    base["overdue_ratio"] = np.nan
    base["history_sufficiency_flag"] = ""
    base["demand_shape_label"] = ""
    base["demand_shape_route"] = ""
    base["guardrail_status"] = "one_shot_side_table"
    base["top_detector_reasons"] = base.get("top_detector_reasons", pd.Series("", index=base.index)).fillna("")
    base["data_quality_warning_flag"] = False
    base["probability_reference"] = pd.to_numeric(base.get("repeat_probability_H", pd.Series(np.nan, index=base.index)), errors="coerce")
    base["business_priority_reference"] = pd.to_numeric(base.get("selected_attention_score", pd.Series(np.nan, index=base.index)), errors="coerce")
    base["status_reason"] = "one_shot_attention_side_table; repeat_probability_not_recurring_churn_probability"
    base["data_quality_note"] = ""
    return finalize_decision(base)


def decide_demand_shape_observation_status(display: pd.DataFrame) -> pd.DataFrame:
    if display is None or display.empty:
        return pd.DataFrame(columns=DECISION_COLUMNS)
    base = display.copy()
    if "drug_group_source" not in base.columns:
        base["drug_group_source"] = "drug_code"
    base["candidate_id"] = (
        base[["manufacturer_code", "hospital_code", "drug_group", "drug_group_source", "cutoff_month"]]
        .fillna("")
        .astype(str)
        .agg("|".join, axis=1)
    )
    base["horizon"] = base.get("horizon", pd.Series("", index=base.index)).map(normalize_horizon)
    prob = pd.to_numeric(base.get("churn_probability_H", pd.Series(np.nan, index=base.index)), errors="coerce")
    value = pd.to_numeric(base.get("relative_value_at_risk_H", pd.Series(np.nan, index=base.index)), errors="coerce")
    high_prob = prob.ge(_business_priority_threshold(prob, 0.8))
    high_value = value.ge(_business_priority_threshold(value, 0.8))
    base["candidate_type"] = "demand_shape_observation"
    base["final_candidate_status"] = "observation_only"
    base["review_priority"] = np.where(high_prob | high_value, "P2", "P3")
    base["evidence_strength"] = np.where(high_prob | high_value, "weak", "insufficient")
    base["human_review_required"] = True
    base["churn_probability_interpretation"] = "recurring_churn_probability_with_demand_shape_guardrail"
    base["repeat_probability_H"] = np.nan
    base["repeat_probability_interpretation"] = ""
    base["relative_business_priority_score_H"] = pd.to_numeric(
        base.get("relative_business_priority_score_H", pd.Series(np.nan, index=base.index)), errors="coerce"
    )
    base["business_priority_interpretation"] = "display_ready_observation_not_main_business_priority_candidate"
    base["survival_state"] = ""
    base["survival_confidence"] = np.nan
    base["overdue_ratio"] = np.nan
    base["guardrail_status"] = "demand_shape_display_ready_observation_only"
    base["detector_hit_count"] = 0
    base["strong_detector_hit_count"] = 0
    base["implemented_detector_hit_count"] = 0
    base["interface_only_detector_count"] = 0
    base["top_detector_reasons"] = ""
    base["data_quality_warning_flag"] = base.get("history_sufficiency_flag", pd.Series("", index=base.index)).fillna("").ne("history_sufficient")
    base["probability_reference"] = prob
    base["business_priority_reference"] = base["relative_business_priority_score_H"]
    base["status_reason"] = "display_ready_demand_shape_observation; not_main_high_risk_candidate"
    base["data_quality_note"] = base.get("history_sufficiency_reason", pd.Series("", index=base.index)).fillna("")
    return finalize_decision(base)


def finalize_decision(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["auto_dispatch_allowed"] = False
    out["evidence_timeline_available"] = False
    out["evidence_timeline_reference"] = np.nan
    out["evidence_persistence_summary"] = "not_implemented_in_v1"
    for col in DECISION_COLUMNS:
        if col not in out.columns:
            out[col] = np.nan
    return out[DECISION_COLUMNS]


def build_status_decisions(
    recurring: pd.DataFrame,
    survival: pd.DataFrame,
    detectors: pd.DataFrame,
    one_shot: pd.DataFrame,
    demand_shape_display: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    detector_agg = aggregate_detector_evidence(detectors)
    recurring_decision = decide_recurring_status(recurring, survival, detector_agg)
    one_shot_decision = decide_one_shot_status(one_shot, detector_agg)
    demand_decision = decide_demand_shape_observation_status(demand_shape_display)
    parts = [df for df in [recurring_decision, one_shot_decision, demand_decision] if df is not None and not df.empty]
    combined = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=DECISION_COLUMNS)
    return combined, recurring_decision, one_shot_decision, demand_decision


def distribution_table(df: pd.DataFrame, column: str) -> pd.DataFrame:
    if df is None or df.empty or column not in df.columns:
        return pd.DataFrame(columns=[column, "row_count", "share"])
    counts = df[column].fillna("__MISSING__").astype(str).value_counts(dropna=False).reset_index()
    counts.columns = [column, "row_count"]
    counts["share"] = counts["row_count"] / max(len(df), 1)
    return counts


def status_summary_text(
    combined: pd.DataFrame,
    recurring: pd.DataFrame,
    one_shot: pd.DataFrame,
    demand: pd.DataFrame,
    demand_missing_note: str = "",
) -> str:
    status_dist = distribution_table(combined, "final_candidate_status")
    priority_dist = distribution_table(combined, "review_priority")
    strength_dist = distribution_table(combined, "evidence_strength")
    lines = [
        "# Status Decision v1 Summary",
        "",
        "M5 consumed M1/M2/M3/M4 structured reports and produced candidate status decisions. It did not train a model, recalculate probability, recalculate business priority, run detectors, implement M6/M7, generate line cards, call an LLM, or allow auto-dispatch.",
        "",
        f"- recurring input rows: {len(recurring)}",
        f"- one-shot input rows: {len(one_shot)}",
        f"- demand-shape display-ready input rows: {len(demand)}",
        f"- candidate_status_decision rows: {len(combined)}",
        f"- priority_review count: {int(combined['final_candidate_status'].eq('priority_review').sum()) if not combined.empty else 0}",
        f"- manual_review count: {int(combined['final_candidate_status'].eq('manual_review').sum()) if not combined.empty else 0}",
        f"- observation_only count: {int(combined['final_candidate_status'].eq('observation_only').sum()) if not combined.empty else 0}",
        f"- low_confidence_watch count: {int(combined['final_candidate_status'].eq('low_confidence_watch').sum()) if not combined.empty else 0}",
        f"- one_shot_attention count: {int(combined['final_candidate_status'].eq('one_shot_attention').sum()) if not combined.empty else 0}",
        f"- not_actionable count: {int(combined['final_candidate_status'].eq('not_actionable').sum()) if not combined.empty else 0}",
        f"- auto_dispatch_allowed all false: {bool((~combined['auto_dispatch_allowed'].astype(bool)).all()) if not combined.empty else True}",
        "- price/delivery interface-only detector rows are not counted as effective evidence.",
        "- probability and business-priority values are copied from upstream references and are not changed.",
        "- M5 output can feed a later M7 structured evidence bundle; M7 is not implemented here.",
    ]
    if demand_missing_note:
        lines.append(f"- demand-shape observation note: {demand_missing_note}")
    lines += ["", "## final_candidate_status", status_dist.to_markdown(index=False), "", "## review_priority", priority_dist.to_markdown(index=False), "", "## evidence_strength", strength_dist.to_markdown(index=False)]
    return "\n".join(lines)


def semantics_audit_text() -> str:
    return "\n".join(
        [
            "# Status Decision Semantics Audit",
            "",
            "- M5 does not recalculate `churn_probability_H`.",
            "- M5 does not recalculate `relative_business_priority_score_H`.",
            "- detector `severity` and `confidence` are not probabilities.",
            "- one-shot `repeat_probability_H` is not recurring `churn_probability_H`.",
            "- demand-shape observation is not the main high-risk candidate table.",
            "- price and delivery interface-only detectors are not effective evidence.",
            "- `auto_dispatch_allowed` is fixed to false.",
            "- M6 cache is not implemented; only interface fields are reserved.",
            "- M7 structured evidence bundle is not implemented.",
            "- No LLM participates in status decisions.",
        ]
    )


def data_quality_text(
    recurring: pd.DataFrame,
    survival: pd.DataFrame,
    detectors: pd.DataFrame,
    one_shot: pd.DataFrame,
    demand: pd.DataFrame,
    demand_missing_note: str = "",
) -> str:
    return "\n".join(
        [
            "# Status Decision Data Quality Report",
            "",
            f"- recurring candidate rows loaded: {len(recurring)}",
            f"- survival rows loaded: {len(survival)}",
            f"- detector evidence rows loaded: {len(detectors)}",
            f"- one-shot rows loaded: {len(one_shot)}",
            f"- demand-shape display-ready rows loaded: {len(demand)}",
            f"- demand-shape note: {demand_missing_note or 'display-ready table loaded or not required'}",
            "",
            "Raw `demand_shape_observation_candidates.csv` is intentionally not loaded as M5 input.",
        ]
    )


def next_stage_text(combined: pd.DataFrame) -> str:
    has_recurring = bool((combined.get("candidate_type", pd.Series(dtype=str)) == "recurring_business_priority").any())
    has_status = bool(not combined.empty)
    ready = "conditional" if has_recurring and has_status else "no"
    return "\n".join(
        [
            "# Status Decision Next Stage Readiness",
            "",
            f"proceed_to_M7 = {ready}",
            "m6_cache_implemented = false",
            "structured_evidence_bundle_implemented = false",
            "",
            "condition: M7 may consume `candidate_status_decision.csv`, but must preserve the same probability semantics and must not treat detector severity/confidence as probability.",
        ]
    )
