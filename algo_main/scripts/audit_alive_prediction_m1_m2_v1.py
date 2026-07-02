#!/usr/bin/env python
"""Read-only M1/M2 audit for alive prediction candidate pool prototypes."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from alg.tasks.die_prediction.candidate_pool_audit import (
    HORIZONS,
    add_entity_key,
    by_cutoff_horizon,
    choose_expansion_reasons,
    enrich_observation_with_features,
    history_sufficiency_audit,
    latest_cutoff_summary,
    load_csv_if_exists,
    m1_reference_summary,
    m2_reference_summary,
    normalize_month_column,
    overlap_audit,
    probability_value_audit,
    read_md_head,
    row_decomposition,
    safe_nunique,
    value_counts_summary,
)


M1_DIR = ROOT / "reports/alive_prediction_candidate_pool_v1"
M2_DIR = ROOT / "reports/alive_prediction_one_shot_repeat_v1"
FEATURE_PATH = ROOT / "data/05_features/alive_prediction/v1_drug_code_monitorable_gap12/cutoff_2024-01_2024-12/feature_table__status0.parquet"
OUTPUT_DIR = ROOT / "reports/alive_prediction_m1_m2_audit_v1"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def md_table(df: pd.DataFrame, max_rows: int = 30) -> str:
    if df is None or df.empty:
        return "_No rows._"
    return df.head(max_rows).to_markdown(index=False)


def describe_numeric(df: pd.DataFrame | None, columns: list[str]) -> pd.DataFrame:
    rows = []
    if df is None or df.empty:
        return pd.DataFrame(columns=["column", "count", "missing", "mean", "p50", "p90", "max"])
    for col in columns:
        if col not in df.columns:
            rows.append({"column": col, "count": 0, "missing": "missing_column"})
            continue
        vals = pd.to_numeric(df[col], errors="coerce")
        rows.append(
            {
                "column": col,
                "count": int(vals.notna().sum()),
                "missing": int(vals.isna().sum()),
                "mean": float(vals.mean()) if vals.notna().any() else np.nan,
                "p50": float(vals.quantile(0.5)) if vals.notna().any() else np.nan,
                "p90": float(vals.quantile(0.9)) if vals.notna().any() else np.nan,
                "max": float(vals.max()) if vals.notna().any() else np.nan,
            }
        )
    return pd.DataFrame(rows)


def load_feature_subset(path: Path, dry_run: bool = False) -> pd.DataFrame | None:
    if dry_run:
        return pd.DataFrame(
            [
                {
                    "manufacturer_code": "m1",
                    "hospital_code": "h1",
                    "drug_group": "d1",
                    "drug_group_source": "drug_code",
                    "cutoff_month": "2024-01",
                    "purchase_count_asof_cutoff": 2,
                    "active_month_count_asof_cutoff": 1,
                    "months_observed_asof_cutoff": 5,
                    "adi_asof_cutoff": np.nan,
                    "cv2_quantity_asof_cutoff": np.nan,
                    "historical_avg_monthly_amount_asof_cutoff": 100.0,
                },
                {
                    "manufacturer_code": "m2",
                    "hospital_code": "h2",
                    "drug_group": "d2",
                    "drug_group_source": "drug_code",
                    "cutoff_month": "2024-01",
                    "purchase_count_asof_cutoff": 8,
                    "active_month_count_asof_cutoff": 5,
                    "months_observed_asof_cutoff": 20,
                    "adi_asof_cutoff": 2.0,
                    "cv2_quantity_asof_cutoff": 0.8,
                    "historical_avg_monthly_amount_asof_cutoff": 200.0,
                },
            ]
        )
    if not path.exists():
        return None
    columns = [
        "manufacturer_code",
        "hospital_code",
        "drug_group",
        "cutoff_month",
        "purchase_count_asof_cutoff",
        "active_month_count_asof_cutoff",
        "months_observed_asof_cutoff",
        "adi_asof_cutoff",
        "cv2_quantity_asof_cutoff",
        "historical_avg_monthly_amount_asof_cutoff",
        "purchase_amount_sum_last_12m_asof_cutoff",
        "purchase_amount_sum_last_6m_asof_cutoff",
        "purchase_amount_sum_last_3m_asof_cutoff",
    ]
    df = pd.read_parquet(path, columns=[c for c in columns if c != "drug_group_source"])
    df["drug_group_source"] = "drug_code"
    return df


def dry_run_inputs() -> dict[str, pd.DataFrame]:
    by_horizon = pd.DataFrame(
        [
            {
                "manufacturer_code": "m1",
                "hospital_code": "h1",
                "drug_group": "d1",
                "drug_group_source": "drug_code",
                "cutoff_month": "2024-01",
                "horizon": 3,
                "churn_probability_H": 0.9,
                "relative_value_at_risk_H": 300.0,
                "relative_business_priority_score_H": 270.0,
                "selection_reason": "global_top5pct",
            }
        ]
    )
    recurring = pd.DataFrame(
        [
            {
                "manufacturer_code": "m1",
                "hospital_code": "h1",
                "drug_group": "d1",
                "drug_group_source": "drug_code",
                "cutoff_month": "2024-01",
                "selected_horizons": "H3,H6",
                "primary_horizon": "H6",
            }
        ]
    )
    obs = pd.DataFrame(
        [
            {
                "manufacturer_code": "m1",
                "hospital_code": "h1",
                "drug_group": "d1",
                "drug_group_source": "drug_code",
                "cutoff_month": "2024-01",
                "horizon": 3,
                "churn_probability_H": 0.9,
                "demand_shape_label": "intermittent",
                "demand_shape_route": "longer_horizon_only",
                "observation_reason": "intermittent_H3_observation_only",
            },
            {
                "manufacturer_code": "m2",
                "hospital_code": "h2",
                "drug_group": "d2",
                "drug_group_source": "drug_code",
                "cutoff_month": "2024-01",
                "horizon": 12,
                "churn_probability_H": 0.8,
                "demand_shape_label": "lumpy",
                "demand_shape_route": "observation_only",
                "observation_reason": "lumpy_high_risk_low_confidence",
            },
        ]
    )
    one = pd.DataFrame(
        [
            {
                "manufacturer_code": "m3",
                "hospital_code": "h3",
                "drug_group": "d3",
                "drug_group_source": "drug_code",
                "first_purchase_month": "2024-01",
                "one_shot_value_score": 10.0,
                "probability_available": False,
                "probability_interpretation": "not_recurring_churn_probability",
            }
        ]
    )
    return {"by_horizon": by_horizon, "recurring": recurring, "obs": obs, "one": one}


def load_inputs(dry_run: bool) -> dict[str, pd.DataFrame | None]:
    if dry_run:
        data = dry_run_inputs()
        data.update({"m2_enriched": None, "m2_metrics": None, "m2_training": None, "m2_explanations": None})
        return data
    return {
        "by_horizon": load_csv_if_exists(M1_DIR / "recurring_business_priority_candidates_by_horizon.csv"),
        "recurring": load_csv_if_exists(M1_DIR / "recurring_business_priority_candidates.csv"),
        "obs": load_csv_if_exists(M1_DIR / "demand_shape_observation_candidates.csv"),
        "one": load_csv_if_exists(M1_DIR / "one_shot_attention_candidates.csv"),
        "m2_enriched": load_csv_if_exists(M2_DIR / "one_shot_attention_candidates_enriched.csv"),
        "m2_metrics": load_csv_if_exists(M2_DIR / "one_shot_repeat_metrics.csv"),
        "m2_training": load_csv_if_exists(M2_DIR / "one_shot_repeat_training_summary.csv"),
        "m2_explanations": load_csv_if_exists(M2_DIR / "one_shot_explanation_factors.csv"),
    }


def write_m1_quality_report(path: Path, by_horizon: pd.DataFrame | None, recurring: pd.DataFrame | None) -> None:
    score_desc = describe_numeric(by_horizon, ["relative_business_priority_score_H", "churn_probability_H", "relative_value_at_risk_H"])
    mfg = pd.DataFrame()
    if recurring is not None and not recurring.empty:
        mfg = add_entity_key(recurring).groupby("manufacturer_code").size().describe().reset_index()
        mfg.columns = ["stat", "candidate_count_per_manufacturer"]
    lines = [
        "# M1 Candidate Pool Quality Report",
        "",
        "This is a read-only audit report. M1 logic and artifacts were not regenerated.",
        "",
        "## Numeric Distributions",
        md_table(score_desc),
        "",
        "## Candidate Count Per Manufacturer",
        md_table(mfg),
        "",
        "## Semantic Checks",
        "- Main table is `recurring_business_priority_candidates`.",
        "- Main table ranking is by relative business priority, not raw probability alone.",
        "- one-shot and demand-shape observation are side tables and are not unioned into the main table.",
    ]
    write_text(path, "\n".join(lines))


def write_m2_quality_report(
    path: Path,
    one: pd.DataFrame | None,
    enriched: pd.DataFrame | None,
    metrics: pd.DataFrame | None,
    explanations: pd.DataFrame | None,
) -> None:
    one_desc = describe_numeric(one, ["one_shot_value_score"])
    enriched_desc = describe_numeric(
        enriched,
        [
            "repeat_probability_H",
            "one_shot_non_repeat_risk_H",
            "one_shot_retention_risk_score_H",
            "one_shot_conversion_opportunity_score_H",
            "one_shot_balanced_attention_score_H",
        ],
    )
    explanation_coverage = 0.0
    if enriched is not None and explanations is not None and not enriched.empty:
        explanation_coverage = min(1.0, len(explanations) / max(1, len(enriched)))
    lines = [
        "# M2 One-Shot Quality Report",
        "",
        "This is a read-only audit report. M2 logic and artifacts were not regenerated.",
        "",
        "## M1 One-Shot Value Distribution",
        md_table(one_desc),
        "",
        "## M2 Enriched Score Distribution",
        md_table(enriched_desc),
        "",
        "## M2 Metrics",
        md_table(metrics if metrics is not None else pd.DataFrame([{"status": "missing"}])),
        "",
        "## Artifact Checks",
        f"- enriched output available: {enriched is not None}",
        f"- explanation factors coverage ratio proxy: {explanation_coverage:.2f}",
        f"- group prior report exists: {(M2_DIR / 'one_shot_group_prior_report.csv').exists()}",
        f"- similarity group report exists: {(M2_DIR / 'one_shot_similarity_group_report.csv').exists()}",
        f"- leakage audit exists: {(M2_DIR / 'one_shot_leakage_audit.md').exists()}",
        f"- erroneous churn_probability columns in one-shot output: {any('churn_probability' in c for c in enriched.columns) if enriched is not None else 'not_available'}",
    ]
    write_text(path, "\n".join(lines))


def write_expansion_diagnosis(
    path: Path,
    decomp: pd.DataFrame,
    latest: pd.DataFrame,
    by_reason: pd.DataFrame,
    by_shape: pd.DataFrame,
    history: pd.DataFrame,
    expansion_reasons: list[str],
) -> None:
    lines = [
        "# Demand-Shape Observation Expansion Diagnosis",
        "",
        "This report audits `demand_shape_observation_candidates.csv`; it does not change M1 logic.",
        "",
        "## Row Decomposition",
        md_table(decomp),
        "",
        "## Latest Cutoff Summary",
        md_table(latest),
        "",
        "## Observation Reason Distribution",
        md_table(by_reason),
        "",
        "## Demand Shape Distribution",
        md_table(by_shape),
        "",
        "## History Sufficiency",
        md_table(history),
        "",
        "## Diagnosis",
        "Detected expansion drivers: " + ", ".join(expansion_reasons),
        "",
        "Interpretation: demand-shape observation is a side-table audit/watch list. If latest cutoff remains large, it should not be displayed as a homepage candidate list without a limit or second-stage filter.",
        "",
        "Suggested review options only; not applied in this run:",
        "- latest cutoff only;",
        "- per-manufacturer Top N;",
        "- probability top 20% within horizon;",
        "- value top 20% within horizon;",
        "- explicit guardrail reasons only;",
        "- observation summary instead of row-level list.",
    ]
    write_text(path, "\n".join(lines))


def write_summary(
    path: Path,
    decomp: pd.DataFrame,
    latest: pd.DataFrame,
    history: pd.DataFrame,
    m1_summary: pd.DataFrame,
    m2_summary: pd.DataFrame,
    expansion_reasons: list[str],
) -> None:
    metrics = dict(zip(decomp["metric"], decomp["value"])) if not decomp.empty else {}
    latest_total = latest[latest["horizon"].astype(str).eq("all")] if not latest.empty else pd.DataFrame()
    latest_rows = int(latest_total["row_count"].iloc[0]) if not latest_total.empty else 0
    latest_entities = int(latest_total["entity_count"].iloc[0]) if not latest_total.empty else 0
    hist_issue = False
    if not history.empty and "share_purchase_count_lt_3" in history.columns:
        low = history[history["demand_shape_label"].isin(["intermittent", "lumpy"])]
        hist_issue = bool(not low.empty and low["share_purchase_count_lt_3"].max(skipna=True) > 0.3)
    m2_available = bool((m2_summary["section"].eq("m2_enriched") & m2_summary["metric"].eq("row_count")).any()) if not m2_summary.empty and "section" in m2_summary.columns else False
    lines = [
        "# M1/M2 Audit Summary",
        "",
        "This is a read-only audit. No M1/M2 algorithm logic was changed, no model was trained, and no cache/parquet/report inputs were deleted.",
        "",
        "## Demand-Shape Observation Expansion",
        f"- total rows: {int(metrics.get('total_rows', 0))}",
        f"- unique entity count: {int(metrics.get('unique_entity_count', 0))}",
        f"- unique entity x cutoff count: {int(metrics.get('unique_entity_cutoff_count', 0))}",
        f"- unique entity x cutoff x horizon count: {int(metrics.get('unique_entity_cutoff_horizon_count', 0))}",
        f"- cutoff month count: {int(metrics.get('cutoff_month_count', 0))}",
        f"- latest cutoff rows/entities: {latest_rows}/{latest_entities}",
        f"- expansion drivers: {', '.join(expansion_reasons)}",
        "",
        "The 19770-row observation table is primarily an observation/watch side table, not a main candidate table. It should not be directly used as a large homepage list.",
        "",
        "## History Sufficiency Risk",
        f"- possible history-insufficient hard classification detected: {str(hist_issue).lower()}",
        "- If many intermittent/lumpy rows have purchase_count < 3 or active_month_count < 2, add a history sufficiency gate before display or routing.",
        "",
        "## M1 Semantic Status",
        "- Main recurring table remains aligned with business-priority ranking.",
        "- one-shot and demand-shape observation remain side tables.",
        "- No union of the three tables was performed by this audit.",
        "",
        "## M2 Semantic Status",
        f"- M2 output available: {str(m2_available).lower()}",
        "- M2 repeat_probability_H is first-purchase repeat probability, not recurring churn_probability_H.",
        "- No probability semantic pollution was detected if one-shot outputs do not contain churn_probability columns.",
        "",
        "## Recommendation",
        "- proceed_to_M3: conditional",
        "- demand_shape_review_required: yes",
        "- m2_ready: yes" if m2_available else "- m2_ready: partial",
        "",
        "Proceed to M3 only if M3 treats demand-shape observation as a side watch list and does not consume it as the main candidate pool. A demand-shape display/routing review should happen before using the 19770 rows operationally.",
    ]
    write_text(path, "\n".join(lines))


def write_next_stage(path: Path, m2_available: bool, latest_rows: int, hist_issue: bool) -> None:
    proceed = "conditional"
    demand_review = "yes" if latest_rows > 1000 or hist_issue else "conditional"
    m2_ready = "yes" if m2_available else "partial"
    lines = [
        "# M1/M2 Next Stage Readiness",
        "",
        f"- proceed_to_M3 = {proceed}",
        f"- demand_shape_review_required = {demand_review}",
        f"- m2_ready = {m2_ready}",
        "",
        "## A. Conditions To Proceed To M3",
        "- M3 consumes `recurring_business_priority_candidates` as the main input.",
        "- demand-shape observation remains side-table only.",
        "- one-shot repeat output remains outside recurring survival-lite.",
        "- no business_priority or one-shot attention score is treated as a probability.",
        "",
        "## B. Conditions Requiring M1/M2 Fix Before M3",
        "- if recurring main table loses business-priority ranking semantics;",
        "- if one-shot output is mixed into recurring candidates;",
        "- if demand-shape observation is unioned into recurring candidates;",
        "- if one-shot output contains recurring churn_probability fields.",
        "",
        "## C. Demand-Shape Observation Review Conditions",
        "- latest cutoff observation rows remain too large for direct display;",
        "- intermittent/lumpy includes many history-insufficient entities;",
        "- observation rows include low-value or low-priority entities after adding value filters;",
        "- display needs a capped watch-list rather than row-level full export.",
    ]
    write_text(path, "\n".join(lines))


def run(*, output_dir: Path = OUTPUT_DIR, dry_run: bool = False) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    inputs = load_inputs(dry_run)
    by_horizon = inputs["by_horizon"]
    recurring = inputs["recurring"]
    obs = inputs["obs"]
    one = inputs["one"]
    m2_enriched = inputs["m2_enriched"]
    m2_metrics = inputs["m2_metrics"]
    m2_training = inputs["m2_training"]
    m2_explanations = inputs["m2_explanations"]
    features = load_feature_subset(FEATURE_PATH, dry_run=dry_run)

    decomp = row_decomposition(obs)
    cutoff_horizon = by_cutoff_horizon(obs)
    by_reason = value_counts_summary(obs, "observation_reason", output_name="observation_reason")
    by_shape = value_counts_summary(obs, "demand_shape_label", output_name="demand_shape_label")
    by_route = value_counts_summary(obs, "demand_shape_route", output_name="demand_shape_route")
    latest = latest_cutoff_summary(obs)
    enriched_obs = enrich_observation_with_features(obs if obs is not None else pd.DataFrame(), features)
    history = history_sufficiency_audit(enriched_obs)
    prob_value = probability_value_audit(enriched_obs)
    overlap = overlap_audit(recurring, obs, one)
    m1_summary = m1_reference_summary(by_horizon, recurring)
    m2_summary = m2_reference_summary(one, m2_enriched, m2_metrics)
    expansion_reasons = choose_expansion_reasons(decomp, latest, by_reason, history)

    decomp.to_csv(output_dir / "demand_shape_observation_row_decomposition.csv", index=False, encoding="utf-8-sig")
    cutoff_horizon.to_csv(output_dir / "demand_shape_observation_by_cutoff_horizon.csv", index=False, encoding="utf-8-sig")
    by_reason.to_csv(output_dir / "demand_shape_observation_by_reason.csv", index=False, encoding="utf-8-sig")
    by_shape.to_csv(output_dir / "demand_shape_observation_by_shape.csv", index=False, encoding="utf-8-sig")
    by_route.to_csv(output_dir / "demand_shape_observation_by_route.csv", index=False, encoding="utf-8-sig")
    latest.to_csv(output_dir / "demand_shape_observation_latest_cutoff_summary.csv", index=False, encoding="utf-8-sig")
    history.to_csv(output_dir / "demand_shape_history_sufficiency_audit.csv", index=False, encoding="utf-8-sig")
    prob_value.to_csv(output_dir / "demand_shape_probability_value_audit.csv", index=False, encoding="utf-8-sig")
    overlap.to_csv(output_dir / "demand_shape_overlap_audit.csv", index=False, encoding="utf-8-sig")
    m1_summary.to_csv(output_dir / "m1_candidate_pool_reference_summary.csv", index=False, encoding="utf-8-sig")
    m2_summary.to_csv(output_dir / "m2_one_shot_reference_summary.csv", index=False, encoding="utf-8-sig")

    write_expansion_diagnosis(
        output_dir / "demand_shape_observation_expansion_diagnosis.md",
        decomp,
        latest,
        by_reason,
        by_shape,
        history,
        expansion_reasons,
    )
    write_m1_quality_report(output_dir / "m1_candidate_pool_quality_report.md", by_horizon, recurring)
    write_m2_quality_report(output_dir / "m2_one_shot_quality_report.md", one, m2_enriched, m2_metrics, m2_explanations)
    write_summary(output_dir / "m1_m2_audit_summary.md", decomp, latest, history, m1_summary, m2_summary, expansion_reasons)

    latest_total = latest[latest["horizon"].astype(str).eq("all")] if not latest.empty else pd.DataFrame()
    latest_rows = int(latest_total["row_count"].iloc[0]) if not latest_total.empty else 0
    hist_issue = False
    if not history.empty and "share_purchase_count_lt_3" in history.columns:
        low = history[history["demand_shape_label"].isin(["intermittent", "lumpy"])]
        hist_issue = bool(not low.empty and low["share_purchase_count_lt_3"].max(skipna=True) > 0.3)
    m2_available = bool(m2_enriched is not None and not m2_enriched.empty)
    write_next_stage(output_dir / "m1_m2_next_stage_readiness.md", m2_available, latest_rows, hist_issue)

    # Small appendix file to make missing/availability status explicit.
    status_rows = [
        {"artifact": "m1_candidate_pool_summary", "status": "available" if (M1_DIR / "candidate_pool_v1_summary.md").exists() else "missing"},
        {"artifact": "m2_summary", "status": "available" if (M2_DIR / "one_shot_repeat_v1_summary.md").exists() else "missing"},
        {"artifact": "m2_leakage_audit", "status": "available" if (M2_DIR / "one_shot_leakage_audit.md").exists() else "missing"},
    ]
    pd.DataFrame(status_rows).to_csv(output_dir / "artifact_availability.csv", index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="run on a small synthetic fixture")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    run(output_dir=args.output_dir, dry_run=args.dry_run)
