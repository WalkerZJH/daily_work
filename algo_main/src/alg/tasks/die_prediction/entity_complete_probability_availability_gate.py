"""Static probability availability gate for entity-complete coverage runs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


GATE_COLUMNS = [
    "manufacturer_code",
    "hospital_code",
    "drug_group",
    "drug_group_source",
    "cutoff_month",
    "horizon",
    "candidate_id",
    "churn_probability_H",
    "probability_display_allowed",
    "probability_display_level",
    "display_mode",
    "reason_code",
    "model_confidence_bucket",
    "history_sufficiency_flag",
    "demand_shape_label",
    "choice_set_caveat",
    "selected_subset_caveat",
    "manual_review_required",
    "auto_dispatch_allowed",
]


def build_probability_availability_gate(
    candidates: pd.DataFrame,
    *,
    probability_col: str = "probability_score",
    leakage_clean: bool = True,
    selected_subset_caveat: bool = True,
) -> pd.DataFrame:
    """Classify probability display availability for candidate rows.

    The gate is deliberately conservative: one-shot rows never show recurring
    churn probability, low-history/lumpy rows are downgraded, and auto dispatch
    remains disabled for every row.
    """

    if candidates is None or candidates.empty:
        return pd.DataFrame(columns=GATE_COLUMNS)
    out = candidates.copy()
    if "drug_group_source" not in out:
        out["drug_group_source"] = "drug_code"
    out["candidate_id"] = make_candidate_id(out)
    prob = pd.to_numeric(out.get(probability_col), errors="coerce").clip(0, 1)
    out["churn_probability_H"] = prob
    history = out.get("history_sufficiency_flag", pd.Series("", index=out.index)).astype(str)
    shape = out.get("demand_shape_label", pd.Series("", index=out.index)).astype(str)
    one_shot = out.get("one_shot_flag", pd.Series(False, index=out.index)).fillna(False).astype(bool)
    confidence = confidence_bucket(prob)
    out["model_confidence_bucket"] = confidence
    choice_context = out.get("manufacturer_substitution_context_available", pd.Series(False, index=out.index)).fillna(False).astype(bool)
    out["choice_set_caveat"] = choice_context | out.filter(like="competitor_").notna().any(axis=1) if any(c.startswith("competitor_") for c in out.columns) else choice_context
    out["selected_subset_caveat"] = bool(selected_subset_caveat)

    stable = (
        leakage_clean
        & ~one_shot
        & history.eq("history_sufficient")
        & ~shape.isin(["intermittent", "lumpy", "cold_start", "unknown"])
        & confidence.isin(["high", "medium"])
        & prob.notna()
    )
    risk_band = (
        leakage_clean
        & ~one_shot
        & prob.notna()
        & ~history.eq("history_insufficient")
        & (
            history.eq("history_medium")
            | shape.isin(["intermittent", "lumpy"])
            | confidence.eq("low")
        )
    )
    observation = leakage_clean & ~one_shot & ~history.eq("history_insufficient") & prob.notna() & ~stable & ~risk_band
    insufficient = one_shot | history.eq("history_insufficient") | prob.isna() | (not leakage_clean)

    out["probability_display_level"] = np.select(
        [stable, risk_band, observation, insufficient],
        ["probability_allowed", "risk_band_only", "observation_only", "hidden_data_insufficient"],
        default="hidden_data_insufficient",
    )
    out["display_mode"] = out["probability_display_level"].map(
        {
            "probability_allowed": "show_probability",
            "risk_band_only": "show_risk_band",
            "observation_only": "show_observation_note",
            "hidden_data_insufficient": "hide_probability",
        }
    )
    out["probability_display_allowed"] = out["probability_display_level"].eq("probability_allowed")
    out["reason_code"] = reason_codes(out, leakage_clean=leakage_clean)
    out["manual_review_required"] = True
    out["auto_dispatch_allowed"] = False
    for col in GATE_COLUMNS:
        if col not in out:
            out[col] = np.nan
    return out[GATE_COLUMNS].reset_index(drop=True)


def confidence_bucket(probability: pd.Series) -> pd.Series:
    p = pd.to_numeric(probability, errors="coerce")
    return pd.Series(
        np.select(
            [p.ge(0.70), p.ge(0.45), p.notna()],
            ["high", "medium", "low"],
            default="unavailable",
        ),
        index=probability.index,
        dtype="object",
    )


def reason_codes(df: pd.DataFrame, *, leakage_clean: bool) -> pd.Series:
    history = df.get("history_sufficiency_flag", pd.Series("", index=df.index)).astype(str)
    shape = df.get("demand_shape_label", pd.Series("", index=df.index)).astype(str)
    one_shot = df.get("one_shot_flag", pd.Series(False, index=df.index)).fillna(False).astype(bool)
    reasons: list[str] = []
    for idx in df.index:
        parts = []
        if not leakage_clean:
            parts.append("leakage_audit_not_clean")
        if bool(one_shot.loc[idx]):
            parts.append("one_shot_not_recurring_churn")
        if history.loc[idx] == "history_insufficient":
            parts.append("history_insufficient")
        elif history.loc[idx] == "history_medium":
            parts.append("history_medium")
        if shape.loc[idx] in {"intermittent", "lumpy", "cold_start", "unknown"}:
            parts.append(f"demand_shape_{shape.loc[idx]}")
        if bool(df.get("choice_set_caveat", pd.Series(False, index=df.index)).loc[idx]):
            parts.append("choice_set_partial_context")
        if bool(df.get("selected_subset_caveat", pd.Series(False, index=df.index)).loc[idx]):
            parts.append("selected_subset_not_full_universe")
        if not parts:
            parts.append("stable_recurring_probability_allowed")
        reasons.append("|".join(parts))
    return pd.Series(reasons, index=df.index)


def make_candidate_id(df: pd.DataFrame) -> pd.Series:
    cols = [c for c in ["manufacturer_code", "hospital_code", "drug_group", "drug_group_source", "cutoff_month", "horizon"] if c in df.columns]
    if not cols:
        return pd.Series([f"candidate_{i}" for i in range(len(df))], index=df.index)
    return df[cols].astype(str).agg("|".join, axis=1)


def summarize_gate(gate: pd.DataFrame) -> pd.DataFrame:
    if gate.empty:
        return pd.DataFrame(columns=["probability_display_level", "row_count", "row_share"])
    out = gate.groupby(["probability_display_level", "display_mode"], dropna=False).size().reset_index(name="row_count")
    out["row_share"] = out["row_count"] / max(1, len(gate))
    return out.sort_values("row_count", ascending=False).reset_index(drop=True)


def render_gate_summary(gate: pd.DataFrame) -> str:
    summary = summarize_gate(gate)
    allowed = int(gate["probability_display_allowed"].sum()) if not gate.empty else 0
    return f"""# Probability Availability Gate Summary

- gate rows: {len(gate)}
- probability_allowed rows: {allowed}
- auto_dispatch_allowed true rows: {int(gate["auto_dispatch_allowed"].sum()) if not gate.empty else 0}
- selected_subset_caveat rows: {int(gate["selected_subset_caveat"].sum()) if not gate.empty else 0}
- choice_set_caveat rows: {int(gate["choice_set_caveat"].sum()) if not gate.empty else 0}

{summary.to_markdown(index=False) if not summary.empty else "_No rows._"}
"""


def render_service_gate_decision(gate: pd.DataFrame) -> str:
    allowed_share = float(gate["probability_display_allowed"].mean()) if not gate.empty else 0.0
    customer = False
    return f"""# Service Gate Decision

- internal_diagnostic_view: true
- analyst_view: true
- proof_case_report: true
- customer_facing_probability_service: {str(customer).lower()}
- auto_dispatch: false
- probability_allowed_share: {allowed_share:.4f}

Customer-facing probability service remains blocked until selected-subset coverage, runtime probability availability, caveats, and worklist capacity are validated beyond the current research extract.
"""


def run_probability_availability_gate(
    candidates_path: str | Path,
    output_dir: str | Path,
    *,
    leakage_clean: bool = True,
    selected_subset_caveat: bool = True,
) -> pd.DataFrame:
    candidates = pd.read_parquet(candidates_path) if str(candidates_path).endswith(".parquet") else pd.read_csv(candidates_path)
    gate = build_probability_availability_gate(
        candidates,
        leakage_clean=leakage_clean,
        selected_subset_caveat=selected_subset_caveat,
    )
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    gate.to_csv(out / "probability_availability_gate.csv", index=False, encoding="utf-8")
    (out / "probability_availability_gate_summary.md").write_text(render_gate_summary(gate), encoding="utf-8")
    (out / "service_gate_decision.md").write_text(render_service_gate_decision(gate), encoding="utf-8")
    return gate


__all__ = [
    "build_probability_availability_gate",
    "summarize_gate",
    "render_gate_summary",
    "render_service_gate_decision",
    "run_probability_availability_gate",
]
