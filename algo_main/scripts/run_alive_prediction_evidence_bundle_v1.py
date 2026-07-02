#!/usr/bin/env python
"""Run M7 structured evidence bundle prototype."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from alg.tasks.die_prediction.evidence_bundle import (
    build_structured_evidence_bundle,
    claims_table,
    completeness_report,
    data_quality_text,
    load_csv_if_exists,
    next_stage_text,
    semantics_audit_text,
    split_bundles,
    summary_text,
)


STATUS_PATH = ROOT / "reports/alive_prediction_status_decision_v1/candidate_status_decision.csv"
DETECTOR_PATH = ROOT / "reports/alive_prediction_detectors_v1/detector_evidence_results.csv"
OUTPUT_DIR = ROOT / "reports/alive_prediction_evidence_bundle_v1"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def dry_run_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    status = pd.DataFrame(
        [
            {
                "candidate_id": "m1|h1|d1|drug_code|2024-01",
                "candidate_type": "recurring_business_priority",
                "manufacturer_code": "m1",
                "hospital_code": "h1",
                "drug_group": "d1",
                "drug_group_source": "drug_code",
                "cutoff_month": "2024-01",
                "horizon": "H6",
                "final_candidate_status": "priority_review",
                "review_priority": "P1",
                "evidence_strength": "medium",
                "human_review_required": True,
                "auto_dispatch_allowed": False,
                "churn_probability_H": 0.8,
                "churn_probability_interpretation": "recurring_churn_probability_from_stage1",
                "repeat_probability_H": None,
                "repeat_probability_interpretation": "",
                "relative_value_at_risk_H": 100.0,
                "relative_business_priority_score_H": 80.0,
                "business_priority_interpretation": "not_probability",
                "survival_state": "likely_churn_interval",
                "survival_confidence": 0.8,
                "overdue_ratio": 3.0,
                "history_sufficiency_flag": "history_sufficient",
                "demand_shape_label": "smooth",
                "demand_shape_route": "main_probability_model",
                "detector_hit_count": 1,
                "strong_detector_hit_count": 1,
                "implemented_detector_hit_count": 3,
                "interface_only_detector_count": 0,
                "top_detector_reasons": "terminal_loss_warning:likely_churn_interval",
                "data_quality_note": "",
            },
            {
                "candidate_id": "m2|h2|d2|drug_code",
                "candidate_type": "one_shot_attention",
                "manufacturer_code": "m2",
                "hospital_code": "h2",
                "drug_group": "d2",
                "drug_group_source": "drug_code",
                "cutoff_month": "2024-01",
                "horizon": "H6",
                "final_candidate_status": "one_shot_attention",
                "review_priority": "P3",
                "evidence_strength": "weak",
                "human_review_required": True,
                "auto_dispatch_allowed": False,
                "churn_probability_H": None,
                "churn_probability_interpretation": "",
                "repeat_probability_H": 0.3,
                "repeat_probability_interpretation": "first_purchase_repeat_probability_not_recurring_churn_probability",
                "relative_value_at_risk_H": None,
                "relative_business_priority_score_H": None,
                "business_priority_interpretation": "one_shot_attention_score_is_not_probability",
                "survival_state": "",
                "survival_confidence": None,
                "overdue_ratio": None,
                "history_sufficiency_flag": "",
                "demand_shape_label": "",
                "demand_shape_route": "",
                "detector_hit_count": 0,
                "strong_detector_hit_count": 0,
                "implemented_detector_hit_count": 0,
                "interface_only_detector_count": 0,
                "top_detector_reasons": "",
                "data_quality_note": "",
            },
        ]
    )
    detectors = pd.DataFrame(
        [
            {
                "candidate_id": "m1|h1|d1|drug_code|2024-01",
                "detector_family": "terminal_dynamic",
                "detector_name": "terminal_loss_warning",
                "hit_flag": True,
                "severity": 85,
                "confidence": 0.8,
                "reason_code": "likely_churn_interval",
                "business_interpretation": "interval evidence",
                "evidence_fields": "survival_state",
                "data_quality_status": "evaluated",
            },
            {
                "candidate_id": "m1|h1|d1|drug_code|2024-01",
                "detector_family": "price_warning",
                "detector_name": "low_price_purchase_warning",
                "hit_flag": True,
                "severity": None,
                "confidence": None,
                "reason_code": "interface_only_not_evaluable",
                "business_interpretation": "",
                "evidence_fields": "",
                "data_quality_status": "not_evaluable",
            },
        ]
    )
    return status, detectors


def write_outputs(output_dir: Path, bundle: pd.DataFrame, status: pd.DataFrame, detectors: pd.DataFrame) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    recurring, one_shot, demand = split_bundles(bundle)
    completeness = completeness_report(bundle)
    bundle.to_csv(output_dir / "structured_evidence_bundle.csv", index=False)
    recurring.to_csv(output_dir / "recurring_structured_evidence_bundle.csv", index=False)
    one_shot.to_csv(output_dir / "one_shot_structured_evidence_bundle.csv", index=False)
    demand.to_csv(output_dir / "demand_shape_observation_evidence_bundle.csv", index=False)
    claims_table(bundle, "allowed_claims", "allowed_claim").to_csv(
        output_dir / "evidence_bundle_allowed_claims.csv", index=False
    )
    claims_table(bundle, "forbidden_claims", "forbidden_claim").to_csv(
        output_dir / "evidence_bundle_forbidden_claims.csv", index=False
    )
    claims_table(bundle, "recommended_action_candidates", "recommended_action_candidate").to_csv(
        output_dir / "evidence_bundle_recommended_actions.csv", index=False
    )
    completeness.to_csv(output_dir / "evidence_bundle_completeness_report.csv", index=False)
    write_text(output_dir / "evidence_bundle_v1_summary.md", summary_text(bundle, completeness))
    write_text(output_dir / "evidence_bundle_semantics_audit.md", semantics_audit_text())
    write_text(output_dir / "evidence_bundle_data_quality_report.md", data_quality_text(bundle, status, detectors))
    write_text(output_dir / "evidence_bundle_next_stage_readiness.md", next_stage_text(bundle))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Run on small synthetic fixture.")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    if args.dry_run:
        status, detectors = dry_run_frames()
    else:
        status = load_csv_if_exists(STATUS_PATH)
        detectors = load_csv_if_exists(DETECTOR_PATH)
    bundle = build_structured_evidence_bundle(status, detectors)
    write_outputs(args.output_dir, bundle, status, detectors)


if __name__ == "__main__":
    main()
