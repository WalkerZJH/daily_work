#!/usr/bin/env python
"""Review M1-M7 structured evidence bundle outputs without calling an LLM."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from alg.tasks.die_prediction.evidence_bundle_review import (
    actionability_audit,
    build_sample_review_markdown,
    claim_consistency_audit,
    field_completeness_by_status,
    llm_readiness_report,
    load_csv_if_exists,
    review_summary,
    stratified_sample,
)


BUNDLE_PATH = ROOT / "reports/alive_prediction_evidence_bundle_v1/structured_evidence_bundle.csv"
ALLOWED_PATH = ROOT / "reports/alive_prediction_evidence_bundle_v1/evidence_bundle_allowed_claims.csv"
FORBIDDEN_PATH = ROOT / "reports/alive_prediction_evidence_bundle_v1/evidence_bundle_forbidden_claims.csv"
ACTIONS_PATH = ROOT / "reports/alive_prediction_evidence_bundle_v1/evidence_bundle_recommended_actions.csv"
COMPLETENESS_PATH = ROOT / "reports/alive_prediction_evidence_bundle_v1/evidence_bundle_completeness_report.csv"
STATUS_PATH = ROOT / "reports/alive_prediction_status_decision_v1/candidate_status_decision.csv"
DETECTOR_PATH = ROOT / "reports/alive_prediction_detectors_v1/detector_evidence_results.csv"
OUTPUT_DIR = ROOT / "reports/alive_prediction_evidence_bundle_review_v1"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def dry_run_bundle() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "bundle_id": "b1",
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
                "repeat_probability_H": None,
                "relative_business_priority_score_H": 80.0,
                "survival_state": "likely_churn_interval",
                "survival_summary": "survival_state=likely_churn_interval;overdue_ratio=3.0",
                "demand_shape_label": "smooth",
                "guardrail_summary": "standard interpretation allowed",
                "detector_evidence_list": '[{"detector_name":"terminal_loss_warning"}]',
                "allowed_claims": '["该对象进入业务优先级候选池。"]',
                "forbidden_claims": '["医院已经确定流失。"]',
                "recommended_action_candidates": '["建议人工核查近期采购频次下降原因。"]',
                "evidence_timeline_available": False,
                "data_quality_note": "",
            },
            {
                "bundle_id": "b2",
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
                "repeat_probability_H": 0.3,
                "relative_business_priority_score_H": None,
                "survival_state": "",
                "survival_summary": "",
                "demand_shape_label": "",
                "guardrail_summary": "demand-shape missing; manual review required",
                "detector_evidence_list": "[]",
                "allowed_claims": '["该对象是 one-shot high value 关注对象。"]',
                "forbidden_claims": '["医院已经确定流失。", "one_shot_non_repeat_risk_H 是 recurring churn probability。"]',
                "recommended_action_candidates": '["建议业务人员判断是否需要促进第二次采购。"]',
                "repeat_probability_interpretation": "first_purchase_repeat_probability_not_recurring_churn_probability",
                "evidence_timeline_available": False,
                "data_quality_note": "",
            },
        ]
    )


def run_review(bundle: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    sample = stratified_sample(bundle)
    claim_audit = claim_consistency_audit(bundle)
    action_audit = actionability_audit(bundle)
    completeness = field_completeness_by_status(bundle)
    sample.to_csv(output_dir / "evidence_bundle_stratified_sample.csv", index=False)
    claim_audit.to_csv(output_dir / "evidence_bundle_claim_consistency_audit.csv", index=False)
    action_audit.to_csv(output_dir / "evidence_bundle_actionability_audit.csv", index=False)
    completeness.to_csv(output_dir / "evidence_bundle_field_completeness_by_status.csv", index=False)
    write_text(output_dir / "evidence_bundle_sample_review.md", build_sample_review_markdown(sample))
    write_text(output_dir / "evidence_bundle_llm_readiness_report.md", llm_readiness_report(bundle, claim_audit))
    write_text(output_dir / "evidence_bundle_review_summary.md", review_summary(bundle, sample, claim_audit, action_audit, completeness))
    write_text(
        output_dir / "evidence_bundle_review_data_quality_report.md",
        "\n".join(
            [
                "# Evidence Bundle Review Data Quality Report",
                "",
                f"- bundle rows loaded: {len(bundle)}",
                f"- sample rows generated: {len(sample)}",
                f"- claim audit rows: {len(claim_audit)}",
                f"- actionability audit rows: {len(action_audit)}",
                "",
                "M1-M7 outputs were read only. No data/cache/parquet files were read or regenerated.",
            ]
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Run on a small synthetic bundle.")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    if args.dry_run:
        bundle = dry_run_bundle()
    else:
        bundle = load_csv_if_exists(BUNDLE_PATH)
        # Auxiliary files are intentionally only presence-checked/readable via
        # load_csv_if_exists semantics; the review logic derives its checks from
        # structured_evidence_bundle to avoid rewriting M7 outputs.
        for path in [ALLOWED_PATH, FORBIDDEN_PATH, ACTIONS_PATH, COMPLETENESS_PATH, STATUS_PATH, DETECTOR_PATH]:
            _ = load_csv_if_exists(path)
    run_review(bundle, args.output_dir)


if __name__ == "__main__":
    main()
