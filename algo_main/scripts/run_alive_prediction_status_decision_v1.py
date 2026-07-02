#!/usr/bin/env python
"""Run M5 evidence fusion and candidate status decision prototype."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from alg.tasks.die_prediction.status_decision import (
    build_status_decisions,
    data_quality_text,
    distribution_table,
    load_csv_if_exists,
    next_stage_text,
    semantics_audit_text,
    status_summary_text,
)


RECURRING_CHECKED_PATH = ROOT / "reports/alive_prediction_m1_m2_corrections_v1/recurring_business_priority_candidates_checked.csv"
RECURRING_RAW_PATH = ROOT / "reports/alive_prediction_candidate_pool_v1/recurring_business_priority_candidates.csv"
SURVIVAL_PATH = ROOT / "reports/alive_prediction_survival_lite_v1/survival_refinement_results.csv"
DETECTOR_PATH = ROOT / "reports/alive_prediction_detectors_v1/detector_evidence_results.csv"
ONE_SHOT_ENRICHED_PATH = ROOT / "reports/alive_prediction_one_shot_repeat_v1/one_shot_attention_candidates_enriched.csv"
ONE_SHOT_RAW_PATH = ROOT / "reports/alive_prediction_candidate_pool_v1/one_shot_attention_candidates.csv"
DEMAND_DISPLAY_PATH = ROOT / "reports/alive_prediction_m1_m2_corrections_v1/demand_shape_observation_display_ready.csv"
RAW_DEMAND_NOT_LOADED_NOTE = (
    "demand_shape_display_ready_missing; raw observation table intentionally not loaded to avoid observation explosion."
)
OUTPUT_DIR = ROOT / "reports/alive_prediction_status_decision_v1"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def dry_run_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, str]:
    recurring = pd.DataFrame(
        [
            {
                "candidate_id": "m1|h1|d1|drug_code|2024-01",
                "semantic_check_pass": True,
                "business_priority_score_available": True,
                "probability_available": True,
                "value_available": True,
            }
        ]
    )
    survival = pd.DataFrame(
        [
            {
                "candidate_id": "m1|h1|d1|drug_code|2024-01",
                "manufacturer_code": "m1",
                "hospital_code": "h1",
                "drug_group": "d1",
                "drug_group_source": "drug_code",
                "cutoff_month": "2024-01",
                "horizon": "H6",
                "churn_probability_H": 0.8,
                "relative_business_priority_score_H": 100.0,
                "relative_value_at_risk_H": 125.0,
                "survival_state": "likely_churn_interval",
                "survival_confidence": 0.8,
                "overdue_ratio": 3.1,
                "history_sufficiency_flag": "history_sufficient",
                "demand_shape_label": "smooth",
                "demand_shape_route": "main_probability_model",
            }
        ]
    )
    detectors = pd.DataFrame(
        [
            {
                "candidate_id": "m1|h1|d1|drug_code|2024-01",
                "detector_name": "terminal_loss_warning",
                "hit_flag": True,
                "severity": 85,
                "confidence": 0.8,
                "reason_code": "likely_churn_interval",
                "business_interpretation": "interval evidence",
                "data_quality_status": "evaluated",
            },
            {
                "candidate_id": "",
                "detector_name": "low_price_purchase_warning",
                "hit_flag": False,
                "severity": None,
                "confidence": None,
                "reason_code": "interface_only_not_evaluable",
                "business_interpretation": "",
                "data_quality_status": "not_evaluable",
            },
        ]
    )
    one_shot = pd.DataFrame(
        [
            {
                "manufacturer_code": "m2",
                "hospital_code": "h2",
                "drug_group": "d2",
                "drug_group_source": "drug_code",
                "first_purchase_month": "2024-01",
                "horizon": "H6",
                "repeat_probability_H": 0.3,
                "selected_attention_score": 50,
                "probability_interpretation": "first_purchase_repeat_probability_not_recurring_churn_probability",
            }
        ]
    )
    demand = pd.DataFrame(
        [
            {
                "manufacturer_code": "m3",
                "hospital_code": "h3",
                "drug_group": "d3",
                "drug_group_source": "drug_code",
                "cutoff_month": "2024-12",
                "horizon": "H12",
                "churn_probability_H": 0.7,
                "relative_value_at_risk_H": 100,
                "relative_business_priority_score_H": 70,
                "demand_shape_label": "lumpy",
                "demand_shape_route": "observation_only",
                "history_sufficiency_flag": "history_sufficient",
            }
        ]
    )
    return recurring, survival, detectors, one_shot, demand, ""


def load_inputs(dry_run: bool = False) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, str]:
    if dry_run:
        return dry_run_frames()

    recurring = load_csv_if_exists(RECURRING_CHECKED_PATH)
    if recurring.empty:
        recurring = load_csv_if_exists(RECURRING_RAW_PATH)
    survival = load_csv_if_exists(SURVIVAL_PATH)
    detectors = load_csv_if_exists(DETECTOR_PATH)
    one_shot = load_csv_if_exists(ONE_SHOT_ENRICHED_PATH)
    if one_shot.empty:
        one_shot = load_csv_if_exists(ONE_SHOT_RAW_PATH)
    demand = load_csv_if_exists(DEMAND_DISPLAY_PATH)
    demand_note = "" if not demand.empty else RAW_DEMAND_NOT_LOADED_NOTE
    return recurring, survival, detectors, one_shot, demand, demand_note


def write_outputs(
    output_dir: Path,
    combined: pd.DataFrame,
    recurring_decision: pd.DataFrame,
    one_shot_decision: pd.DataFrame,
    demand_decision: pd.DataFrame,
    recurring_input: pd.DataFrame,
    one_shot_input: pd.DataFrame,
    demand_input: pd.DataFrame,
    survival_input: pd.DataFrame,
    detector_input: pd.DataFrame,
    demand_note: str,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    combined.to_csv(output_dir / "candidate_status_decision.csv", index=False)
    recurring_decision.to_csv(output_dir / "recurring_candidate_status_decision.csv", index=False)
    one_shot_decision.to_csv(output_dir / "one_shot_candidate_status_decision.csv", index=False)
    demand_decision.to_csv(output_dir / "demand_shape_observation_status_decision.csv", index=False)
    distribution_table(combined, "final_candidate_status").to_csv(output_dir / "status_decision_distribution.csv", index=False)
    distribution_table(combined, "review_priority").to_csv(output_dir / "review_priority_distribution.csv", index=False)
    distribution_table(combined, "evidence_strength").to_csv(output_dir / "evidence_strength_distribution.csv", index=False)
    write_text(
        output_dir / "status_decision_v1_summary.md",
        status_summary_text(combined, recurring_input, one_shot_input, demand_input, demand_note),
    )
    write_text(
        output_dir / "status_decision_data_quality_report.md",
        data_quality_text(recurring_input, survival_input, detector_input, one_shot_input, demand_input, demand_note),
    )
    write_text(output_dir / "status_decision_semantics_audit.md", semantics_audit_text())
    write_text(output_dir / "status_decision_next_stage_readiness.md", next_stage_text(combined))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Run on small synthetic fixture.")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    recurring, survival, detectors, one_shot, demand, demand_note = load_inputs(dry_run=args.dry_run)
    combined, recurring_decision, one_shot_decision, demand_decision = build_status_decisions(
        recurring=recurring,
        survival=survival,
        detectors=detectors,
        one_shot=one_shot,
        demand_shape_display=demand,
    )
    write_outputs(
        output_dir=args.output_dir,
        combined=combined,
        recurring_decision=recurring_decision,
        one_shot_decision=one_shot_decision,
        demand_decision=demand_decision,
        recurring_input=recurring,
        one_shot_input=one_shot,
        demand_input=demand,
        survival_input=survival,
        detector_input=detectors,
        demand_note=demand_note,
    )


if __name__ == "__main__":
    main()
