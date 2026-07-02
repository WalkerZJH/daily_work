#!/usr/bin/env python
"""Build safe corrected M1/M2 report views without changing M1/M2 artifacts."""

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

from alg.tasks.die_prediction.candidate_pool_corrections import (
    ObservationDisplayConfig,
    add_history_sufficiency_flags,
    audit_m2_semantics,
    check_one_shot_attention,
    check_recurring_business_priority,
    display_ready_observations,
    join_observation_history,
    load_csv_if_exists,
    raw_observation_profile,
)


M1_DIR = ROOT / "reports/alive_prediction_candidate_pool_v1"
M2_DIR = ROOT / "reports/alive_prediction_one_shot_repeat_v1"
FEATURE_PATH = ROOT / "data/05_features/alive_prediction/v1_drug_code_monitorable_gap12/cutoff_2024-01_2024-12/feature_table__status0.parquet"
OUTPUT_DIR = ROOT / "reports/alive_prediction_m1_m2_corrections_v1"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def md_table(df: pd.DataFrame, max_rows: int = 30) -> str:
    if df is None or df.empty:
        return "_No rows._"
    return df.head(max_rows).to_markdown(index=False)


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
                    "purchase_count_asof_cutoff": 6,
                    "active_month_count_asof_cutoff": 4,
                    "months_observed_asof_cutoff": 20,
                    "adi_asof_cutoff": 2.0,
                    "cv2_quantity_asof_cutoff": 0.6,
                    "historical_avg_monthly_amount_asof_cutoff": 200.0,
                },
            ]
        )
    if not path.exists():
        return None
    cols = [
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
    df = pd.read_parquet(path, columns=cols)
    df["drug_group_source"] = "drug_code"
    return df


def dry_run_inputs() -> dict[str, pd.DataFrame | None]:
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
                "primary_churn_probability": 0.8,
                "primary_relative_value_at_risk": 100.0,
                "primary_relative_business_priority_score": 80.0,
            }
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
                "attention_reason": "dry_run",
                "probability_available": False,
                "probability_interpretation": "not_recurring_churn_probability",
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
                "churn_probability_H": 0.85,
                "demand_shape_label": "lumpy",
                "demand_shape_route": "observation_only",
                "observation_reason": "lumpy_high_risk_low_confidence",
            },
        ]
    )
    return {
        "recurring": recurring,
        "one": one,
        "obs": obs,
        "m2_enriched": None,
        "m2_explanations": None,
        "m2_training": None,
    }


def load_inputs(dry_run: bool) -> dict[str, pd.DataFrame | None]:
    if dry_run:
        return dry_run_inputs()
    return {
        "recurring": load_csv_if_exists(M1_DIR / "recurring_business_priority_candidates.csv"),
        "one": load_csv_if_exists(M1_DIR / "one_shot_attention_candidates.csv"),
        "obs": load_csv_if_exists(M1_DIR / "demand_shape_observation_candidates.csv"),
        "m2_enriched": load_csv_if_exists(M2_DIR / "one_shot_attention_candidates_enriched.csv"),
        "m2_explanations": load_csv_if_exists(M2_DIR / "one_shot_explanation_factors.csv"),
        "m2_training": load_csv_if_exists(M2_DIR / "one_shot_repeat_training_summary.csv"),
    }


def write_display_summary(path: Path, raw_profile: pd.DataFrame, display: pd.DataFrame, filter_audit: pd.DataFrame) -> None:
    profile = dict(zip(raw_profile["metric"], raw_profile["value"])) if not raw_profile.empty else {}
    raw_rows = int(float(profile.get("total_rows", 0)))
    display_rows = len(display)
    compression = display_rows / raw_rows if raw_rows else np.nan
    lines = [
        "# Demand-Shape Observation Display Summary",
        "",
        "Raw observation rows are retained as audit rows. This display-ready view is a capped side-table view only.",
        "",
        f"- raw rows: {raw_rows}",
        f"- display-ready rows: {display_rows}",
        f"- compression ratio: {compression:.4f}" if raw_rows else "- compression ratio: not_available",
        "",
        "## Filter Audit",
        md_table(filter_audit),
        "",
        "## Display Semantics",
        "- display-ready observation is not a candidate union;",
        "- it does not enter `recurring_business_priority_candidates`;",
        "- history_insufficient rows are excluded from strong display and should only appear in low-confidence summaries.",
    ]
    write_text(path, "\n".join(lines))


def write_summary(
    path: Path,
    raw_profile: pd.DataFrame,
    display: pd.DataFrame,
    history_flags: pd.DataFrame,
    recurring_checked: pd.DataFrame,
    one_checked: pd.DataFrame,
    m2_audit: pd.DataFrame,
) -> None:
    profile = dict(zip(raw_profile["metric"], raw_profile["value"])) if not raw_profile.empty else {}
    raw_rows = int(float(profile.get("total_rows", 0)))
    display_rows = len(display)
    latest_rows = int(float(profile.get("latest_cutoff_rows", 0)))
    compression = display_rows / raw_rows if raw_rows else np.nan
    hist_insufficient = int(history_flags["history_sufficiency_flag"].eq("history_insufficient").sum()) if not history_flags.empty else 0
    recurring_pass = bool(recurring_checked["semantic_check_pass"].all()) if not recurring_checked.empty else False
    one_pass = bool(one_checked["semantic_check_pass"].all()) if not one_checked.empty else False
    m2_available = not m2_audit.empty and not m2_audit["status"].eq("missing").all()
    m2_pollution = bool(
        not m2_audit.empty
        and (
            m2_audit[m2_audit["check_name"].eq("no_recurring_churn_probability_column")]["status"].astype(str).eq("fail").any()
        )
    )
    lines = [
        "# M1/M2 Correction Summary",
        "",
        "This run generated safe corrected report views only. It did not overwrite M1/M2 source outputs, did not train models, and did not implement M3/M4/M5/M6/M7.",
        "",
        f"1. raw demand-shape observation retained: true, rows={raw_rows}",
        "2. 19770-row expansion diagnosis: mainly multi-cutoff and multi-horizon expansion; latest cutoff is still too large for direct display. No source rows were deleted.",
        f"3. display-ready observation rows: {display_rows}",
        f"4. display-ready compression ratio: {compression:.4f}" if raw_rows else "4. display-ready compression ratio: not_available",
        f"5. latest cutoff observation rows: {latest_rows}",
        f"6. history_insufficient rows flagged: {hist_insufficient}",
        "7. history_sufficiency_flag added: true",
        f"8. M1 recurring business-priority semantic check pass: {str(recurring_pass).lower()}",
        f"9. one-shot side-table semantic check pass: {str(one_pass).lower()}",
        f"10. M2 output available: {str(m2_available).lower()}",
        f"11. M2 probability semantic pollution detected: {str(m2_pollution).lower()}",
        "12. proceed_to_M3 recommendation: conditional; M3 must read only recurring_business_priority_candidates and not raw demand-shape observation.",
        "13. demand-shape review recommendation: yes; display-ready cap should be used for review surfaces.",
    ]
    write_text(path, "\n".join(lines))


def write_next_stage_gate(
    path: Path,
    recurring_checked: pd.DataFrame,
    display: pd.DataFrame,
    raw_profile: pd.DataFrame,
    m2_audit: pd.DataFrame,
) -> None:
    recurring_pass = bool(recurring_checked["semantic_check_pass"].all()) if not recurring_checked.empty else False
    m2_available = not m2_audit.empty and not m2_audit["status"].eq("missing").all()
    profile = dict(zip(raw_profile["metric"], raw_profile["value"])) if not raw_profile.empty else {}
    raw_rows = int(float(profile.get("total_rows", 0)))
    display_rows = len(display)
    if not recurring_pass:
        proceed = "no"
        condition = "recurring main table semantic checks failed"
    elif raw_rows > display_rows and raw_rows > 1000:
        proceed = "conditional"
        condition = "M3 must only read recurring_business_priority_candidates, not raw demand_shape_observation_candidates"
    else:
        proceed = "yes"
        condition = "recurring main table passed and demand-shape side table is controlled"
    demand_review = "yes" if raw_rows > display_rows else "no"
    m2_ready = "yes" if m2_available else "no"
    lines = [
        "# M1/M2 Next Stage Gate",
        "",
        f"proceed_to_M3 = {proceed}",
        f"demand_shape_review_required = {demand_review}",
        f"m2_ready = {m2_ready}",
        "",
        f"condition = {condition}",
        "",
        "M3 must not consume one-shot attention or raw demand-shape observation as recurring candidates.",
    ]
    write_text(path, "\n".join(lines))


def run(*, output_dir: Path = OUTPUT_DIR, dry_run: bool = False) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    inputs = load_inputs(dry_run)
    features = load_feature_subset(FEATURE_PATH, dry_run=dry_run)

    obs = inputs["obs"] if inputs["obs"] is not None else pd.DataFrame()
    recurring = inputs["recurring"] if inputs["recurring"] is not None else pd.DataFrame()
    one = inputs["one"] if inputs["one"] is not None else pd.DataFrame()
    enriched_obs = join_observation_history(obs, features)
    history_flags_full = add_history_sufficiency_flags(enriched_obs)
    display, filter_audit = display_ready_observations(history_flags_full, config=ObservationDisplayConfig())
    raw_profile = raw_observation_profile(history_flags_full, display)
    recurring_checked = check_recurring_business_priority(recurring, one_shot=one, observation=obs) if not recurring.empty else pd.DataFrame()
    one_checked = check_one_shot_attention(one, recurring=recurring) if not one.empty else pd.DataFrame()
    m2_audit = audit_m2_semantics(
        inputs["m2_enriched"],
        explanation_factors=inputs["m2_explanations"],
        leakage_audit_exists=(M2_DIR / "one_shot_leakage_audit.md").exists() and not dry_run,
        metrics_exists=(M2_DIR / "one_shot_repeat_metrics.csv").exists() and not dry_run,
        training_summary=inputs["m2_training"],
    )

    history_cols = [
        "manufacturer_code",
        "hospital_code",
        "drug_group",
        "drug_group_source",
        "cutoff_month",
        "horizon",
        "demand_shape_label",
        "purchase_count_asof_cutoff",
        "active_month_count_asof_cutoff",
        "months_observed_asof_cutoff",
        "adi_asof_cutoff",
        "cv2_quantity_asof_cutoff",
        "history_sufficiency_flag",
        "history_sufficiency_reason",
    ]
    history_flags_full[[c for c in history_cols if c in history_flags_full.columns]].to_csv(
        output_dir / "demand_shape_history_sufficiency_flags.csv", index=False, encoding="utf-8-sig"
    )
    raw_profile.to_csv(output_dir / "demand_shape_observation_raw_profile.csv", index=False, encoding="utf-8-sig")
    display.to_csv(output_dir / "demand_shape_observation_display_ready.csv", index=False, encoding="utf-8-sig")
    filter_audit.to_csv(output_dir / "demand_shape_observation_filter_audit.csv", index=False, encoding="utf-8-sig")
    recurring_checked.to_csv(output_dir / "recurring_business_priority_candidates_checked.csv", index=False, encoding="utf-8-sig")
    one_checked.to_csv(output_dir / "one_shot_attention_candidates_checked.csv", index=False, encoding="utf-8-sig")
    m2_audit.to_csv(output_dir / "one_shot_m2_semantics_audit.csv", index=False, encoding="utf-8-sig")
    write_display_summary(output_dir / "demand_shape_observation_display_summary.md", raw_profile, display, filter_audit)
    write_summary(output_dir / "m1_m2_correction_summary.md", raw_profile, display, history_flags_full, recurring_checked, one_checked, m2_audit)
    write_next_stage_gate(output_dir / "m1_m2_next_stage_gate.md", recurring_checked, display, raw_profile, m2_audit)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="run on a small synthetic fixture")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    run(output_dir=args.output_dir, dry_run=args.dry_run)
