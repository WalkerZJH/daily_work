#!/usr/bin/env python
"""Run M3 survival-lite / interval-aware refinement prototype."""

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

from alg.tasks.die_prediction.survival_lite import (
    format_survival_results,
    refine_survival,
)


M1_DIR = ROOT / "reports/alive_prediction_candidate_pool_v1"
CORRECTIONS_DIR = ROOT / "reports/alive_prediction_m1_m2_corrections_v1"
FEATURE_PATH = ROOT / "data/05_features/alive_prediction/v1_drug_code_monitorable_gap12/cutoff_2024-01_2024-12/feature_table__status0.parquet"
OUTPUT_DIR = ROOT / "reports/alive_prediction_survival_lite_v1"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def md_table(df: pd.DataFrame, max_rows: int = 30) -> str:
    if df is None or df.empty:
        return "_No rows._"
    return df.head(max_rows).to_markdown(index=False)


def gate_status() -> str:
    path = CORRECTIONS_DIR / "m1_m2_next_stage_gate.md"
    if not path.exists():
        return "missing"
    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        if line.strip().startswith("proceed_to_M3"):
            return line.split("=", 1)[-1].strip()
    return "unknown"


def load_candidates(dry_run: bool = False) -> pd.DataFrame:
    if dry_run:
        return pd.DataFrame(
            [
                {
                    "candidate_id": "m1|h1|d1|drug_code|2024-01",
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
                    "demand_shape_label": "smooth",
                },
                {
                    "candidate_id": "m2|h2|d2|drug_code|2024-01",
                    "manufacturer_code": "m2",
                    "hospital_code": "h2",
                    "drug_group": "d2",
                    "drug_group_source": "drug_code",
                    "cutoff_month": "2024-01",
                    "selected_horizons": "H12",
                    "primary_horizon": "H12",
                    "primary_churn_probability": 0.9,
                    "primary_relative_value_at_risk": 200.0,
                    "primary_relative_business_priority_score": 180.0,
                    "demand_shape_label": "lumpy",
                },
            ]
        )
    checked = CORRECTIONS_DIR / "recurring_business_priority_candidates_checked.csv"
    raw = M1_DIR / "recurring_business_priority_candidates.csv"
    path = checked if checked.exists() else raw
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def load_features(dry_run: bool = False) -> pd.DataFrame | None:
    if dry_run:
        return pd.DataFrame(
            [
                {
                    "manufacturer_code": "m1",
                    "hospital_code": "h1",
                    "drug_group": "d1",
                    "drug_group_source": "drug_code",
                    "cutoff_month": "2024-01",
                    "months_since_last_purchase_asof_cutoff": 2.0,
                    "purchase_count_asof_cutoff": 5,
                    "active_month_count_asof_cutoff": 3,
                    "months_observed_asof_cutoff": 12,
                    "median_purchase_interval_days_asof_cutoff": 60.0,
                    "mean_purchase_interval_days_asof_cutoff": 65.0,
                    "std_purchase_interval_days_asof_cutoff": 10.0,
                    "purchase_interval_iqr_asof_cutoff": 15.0,
                    "adi_asof_cutoff": 1.2,
                    "cv2_quantity_asof_cutoff": 0.3,
                    "order_count_last_3m_asof_cutoff": 1,
                    "order_count_last_6m_asof_cutoff": 2,
                    "order_count_last_12m_asof_cutoff": 5,
                    "drug_category_code": "c1",
                    "province_code": "p1",
                    "hospital_level_code": "L1",
                    "one_shot_flag": False,
                },
                {
                    "manufacturer_code": "m2",
                    "hospital_code": "h2",
                    "drug_group": "d2",
                    "drug_group_source": "drug_code",
                    "cutoff_month": "2024-01",
                    "months_since_last_purchase_asof_cutoff": 10.0,
                    "purchase_count_asof_cutoff": 2,
                    "active_month_count_asof_cutoff": 1,
                    "months_observed_asof_cutoff": 8,
                    "median_purchase_interval_days_asof_cutoff": np.nan,
                    "mean_purchase_interval_days_asof_cutoff": np.nan,
                    "std_purchase_interval_days_asof_cutoff": np.nan,
                    "purchase_interval_iqr_asof_cutoff": np.nan,
                    "adi_asof_cutoff": np.nan,
                    "cv2_quantity_asof_cutoff": np.nan,
                    "order_count_last_3m_asof_cutoff": 0,
                    "order_count_last_6m_asof_cutoff": 1,
                    "order_count_last_12m_asof_cutoff": 2,
                    "drug_category_code": "c2",
                    "province_code": "p2",
                    "hospital_level_code": "L2",
                    "one_shot_flag": False,
                },
            ]
        )
    if not FEATURE_PATH.exists():
        return None
    cols = [
        "manufacturer_code",
        "hospital_code",
        "drug_group",
        "cutoff_month",
        "months_since_last_purchase_asof_cutoff",
        "purchase_count_asof_cutoff",
        "active_month_count_asof_cutoff",
        "months_observed_asof_cutoff",
        "adi_asof_cutoff",
        "cv2_quantity_asof_cutoff",
        "median_purchase_interval_days_asof_cutoff",
        "mean_purchase_interval_days_asof_cutoff",
        "std_purchase_interval_days_asof_cutoff",
        "purchase_interval_iqr_asof_cutoff",
        "order_count_last_3m_asof_cutoff",
        "order_count_last_6m_asof_cutoff",
        "order_count_last_12m_asof_cutoff",
        "drug_category_code",
        "province_code",
        "hospital_level_code",
        "one_shot_flag",
        "demand_pattern_type_asof_cutoff",
    ]
    df = pd.read_parquet(FEATURE_PATH, columns=cols)
    df["drug_group_source"] = "drug_code"
    return df


def distribution(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    rows = []
    for col in columns:
        if col not in df.columns:
            continue
        for value, count in df[col].fillna("__MISSING__").astype(str).value_counts(dropna=False).items():
            rows.append({"field": col, "value": value, "row_count": int(count), "share": count / len(df) if len(df) else np.nan})
    return pd.DataFrame(rows)


def history_sufficiency_report(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty:
        return pd.DataFrame()
    return (
        results.groupby("history_sufficiency_flag", dropna=False)
        .agg(
            row_count=("candidate_id", "size"),
            avg_survival_confidence=("survival_confidence", "mean"),
            avg_overdue_ratio=("overdue_ratio", "mean"),
        )
        .reset_index()
    )


def demand_shape_route_report(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty:
        return pd.DataFrame()
    return (
        results.groupby(["demand_shape_label", "demand_shape_route", "alert_policy"], dropna=False)
        .agg(
            row_count=("candidate_id", "size"),
            avg_survival_confidence=("survival_confidence", "mean"),
            human_review_rate=("human_review_required", "mean"),
        )
        .reset_index()
    )


def state_distribution(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty:
        return pd.DataFrame()
    return (
        results.groupby(["horizon", "survival_state"], dropna=False)
        .agg(
            row_count=("candidate_id", "size"),
            avg_churn_probability_H=("churn_probability_H", "mean"),
            avg_business_priority_score_H=("relative_business_priority_score_H", "mean"),
            avg_survival_confidence=("survival_confidence", "mean"),
        )
        .reset_index()
        .sort_values(["horizon", "survival_state"])
    )


def outcome_audit(results: pd.DataFrame) -> pd.DataFrame:
    # Feature artifacts used in M3 do not include future labels. Keep schema for
    # downstream validation without manufacturing outcome labels.
    return pd.DataFrame(
        columns=[
            "horizon",
            "survival_state",
            "row_count",
            "observed_die_rate",
            "avg_churn_probability_H",
            "avg_business_priority_score_H",
            "avg_survival_confidence",
        ]
    )


def write_skip_report(output_dir: Path, reason: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_text(
        output_dir / "survival_lite_v1_summary.md",
        "\n".join(
            [
                "# Survival-Lite v1 Summary",
                "",
                "M3 was skipped.",
                f"reason = {reason}",
            ]
        ),
    )
    for name in [
        "survival_refinement_results.csv",
        "survival_history_sufficiency_report.csv",
        "survival_demand_shape_route_report.csv",
        "survival_group_prior_interval_report.csv",
        "survival_state_distribution.csv",
        "survival_state_outcome_audit.csv",
    ]:
        pd.DataFrame().to_csv(output_dir / name, index=False)
    write_text(output_dir / "survival_data_quality_report.md", f"# Survival Data Quality Report\n\nSkipped: {reason}\n")
    write_text(output_dir / "survival_leakage_audit.md", f"# Survival Leakage Audit\n\nSkipped: {reason}\n")
    write_text(output_dir / "survival_next_stage_readiness.md", f"# Survival Next Stage Readiness\n\nproceed_to_M4 = no\nreason = {reason}\n")


def leakage_audit_text() -> str:
    return "\n".join(
        [
            "# Survival-Lite Leakage Audit",
            "",
            "This is an M3 interval-aware refinement report, not a model-training run.",
            "",
            "- ADI/CV2 fields are read only from `adi_asof_cutoff` and `cv2_quantity_asof_cutoff`.",
            "- Interval fields are read only from `_asof_cutoff` interval columns.",
            "- Group prior intervals are aggregated by cutoff_month from as-of feature rows; no future purchase rows are queried.",
            "- No future labels are used by survival-lite state assignment.",
            "- `churn_probability_H` is copied from M1 and not recalculated.",
            "- `relative_business_priority_score_H` is copied from M1 and not recalculated.",
            "- If interval fields are missing, candidates use group-prior fallback or insufficient-history state.",
            "",
            "data_quality_warning: group prior intervals are aggregate report priors based on existing as-of feature artifacts; they should not be interpreted as a trained survival model.",
        ]
    )


def data_quality_text(candidates: pd.DataFrame, features: pd.DataFrame | None, results: pd.DataFrame) -> str:
    missing_feature_rows = int(results["purchase_count_asof_cutoff"].isna().sum()) if "purchase_count_asof_cutoff" in results.columns else len(results)
    return "\n".join(
        [
            "# Survival Data Quality Report",
            "",
            f"- input recurring candidates: {len(candidates)}",
            f"- feature table available: {features is not None and not features.empty}",
            f"- output rows: {len(results)}",
            f"- rows with missing joined purchase_count_asof_cutoff: {missing_feature_rows}",
            f"- one-shot excluded rows: {int((results.get('history_sufficiency_flag', pd.Series(dtype=str)) == 'one_shot').sum()) if not results.empty else 0}",
            "",
            "M3 does not read raw demand_shape_observation_candidates as input and does not process one-shot candidates.",
        ]
    )


def summary_text(
    candidates: pd.DataFrame,
    results: pd.DataFrame,
    prior_report: pd.DataFrame,
    gate: str,
) -> str:
    material = int(results["survival_state"].isin(["materially_overdue", "likely_churn_interval"]).sum()) if not results.empty else 0
    lines = [
        "# Survival-Lite v1 Summary",
        "",
        "M3 survival-lite refines only the recurring business-priority main table. It does not train a survival model and does not implement detector or line-card logic.",
        "",
        f"1. recurring main candidate table read: {str(not candidates.empty).lower()}",
        "2. one-shot processed: false",
        f"3. candidate count: {len(results)}",
        f"4. proceed_to_M3 gate status before run: {gate}",
        "",
        "## History Sufficiency Distribution",
        md_table(distribution(results, ["history_sufficiency_flag"])),
        "",
        "## Demand Shape Distribution",
        md_table(distribution(results, ["demand_shape_label"])),
        "",
        "## Survival State Distribution",
        md_table(distribution(results, ["survival_state"])),
        "",
        "## Expected Interval Source Distribution",
        md_table(distribution(results, ["expected_interval_source"])),
        "",
        "## Fallback Method Distribution",
        md_table(distribution(results, ["fallback_method"])),
        "",
        f"materially_overdue / likely_churn_interval rows: {material}",
        "",
        "## Horizon Distribution",
        md_table(distribution(results, ["horizon"])),
        "",
        f"group prior interval report generated: {str(not prior_report.empty).lower()} rows={len(prior_report)}",
        "data leakage risk: no direct future labels/orders used; see survival_leakage_audit.md for caveats.",
        "can enter M4 detector: conditional, if M4 consumes survival_refinement_results only as evidence and does not recalculate probability.",
        "M3 changed churn_probability_H: false.",
        "M3 changed business_priority_score_H: false.",
        "M3 implemented detector / line card: false.",
    ]
    return "\n".join(lines)


def next_stage_text(results: pd.DataFrame) -> str:
    return "\n".join(
        [
            "# Survival Next Stage Readiness",
            "",
            "proceed_to_M4 = conditional",
            "condition = M4 may use survival_state, overdue_ratio, demand_shape_route, and history_sufficiency_flag as evidence only.",
            "",
            "M4 must not recalculate churn probability, business priority, or one-shot repeat probability.",
            f"survival_refinement_rows = {len(results)}",
        ]
    )


def run(*, output_dir: Path = OUTPUT_DIR, dry_run: bool = False) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    gate = "conditional" if dry_run else gate_status()
    if gate == "no":
        write_skip_report(output_dir, "m1_m2_next_stage_gate proceed_to_M3=no")
        return
    candidates = load_candidates(dry_run=dry_run)
    if candidates.empty:
        write_skip_report(output_dir, "recurring_business_priority_candidates missing_or_empty")
        return
    features = load_features(dry_run=dry_run)
    results_raw, prior_report = refine_survival(candidates, features)
    results = format_survival_results(results_raw)

    results.to_csv(output_dir / "survival_refinement_results.csv", index=False, encoding="utf-8-sig")
    history_sufficiency_report(results_raw).to_csv(
        output_dir / "survival_history_sufficiency_report.csv", index=False, encoding="utf-8-sig"
    )
    demand_shape_route_report(results_raw).to_csv(
        output_dir / "survival_demand_shape_route_report.csv", index=False, encoding="utf-8-sig"
    )
    prior_report.to_csv(output_dir / "survival_group_prior_interval_report.csv", index=False, encoding="utf-8-sig")
    state_distribution(results).to_csv(output_dir / "survival_state_distribution.csv", index=False, encoding="utf-8-sig")
    outcome_audit(results).to_csv(output_dir / "survival_state_outcome_audit.csv", index=False, encoding="utf-8-sig")
    write_text(output_dir / "survival_data_quality_report.md", data_quality_text(candidates, features, results_raw))
    write_text(output_dir / "survival_leakage_audit.md", leakage_audit_text())
    write_text(output_dir / "survival_lite_v1_summary.md", summary_text(candidates, results, prior_report, gate))
    write_text(output_dir / "survival_next_stage_readiness.md", next_stage_text(results))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="run on a small synthetic fixture")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    run(output_dir=args.output_dir, dry_run=args.dry_run)
