#!/usr/bin/env python
"""Render fixed-template static line-card review samples without an LLM."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from alg.tasks.die_prediction.static_line_card_review import (
    choose_card_samples,
    claim_boundary_audit,
    field_completeness,
    load_csv_if_exists,
    llm_readiness_note,
    manual_review_checklist_text,
    render_card_markdown,
    render_cards_html,
    render_cards_markdown,
    sample_index,
    summary_text,
)


BUNDLE_PATH = ROOT / "reports/alive_prediction_evidence_bundle_v1/structured_evidence_bundle.csv"
SAMPLE_PATH = ROOT / "reports/alive_prediction_evidence_bundle_review_v1/evidence_bundle_stratified_sample.csv"
CLAIM_AUDIT_PATH = ROOT / "reports/alive_prediction_evidence_bundle_review_v1/evidence_bundle_claim_consistency_audit.csv"
ACTION_AUDIT_PATH = ROOT / "reports/alive_prediction_evidence_bundle_review_v1/evidence_bundle_actionability_audit.csv"
LLM_READINESS_PATH = ROOT / "reports/alive_prediction_evidence_bundle_review_v1/evidence_bundle_llm_readiness_report.md"
OUTPUT_DIR = ROOT / "reports/alive_prediction_static_line_card_review_v1"


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
                "churn_probability_interpretation": "recurring_churn_probability_from_stage1",
                "repeat_probability_H": None,
                "repeat_probability_interpretation": "",
                "relative_value_at_risk_H": 100.0,
                "relative_business_priority_score_H": 80.0,
                "business_priority_interpretation": "not_probability",
                "survival_state": "likely_churn_interval",
                "survival_confidence": 0.8,
                "survival_summary": "survival_state=likely_churn_interval;overdue_ratio=3.0",
                "demand_shape_label": "smooth",
                "demand_shape_route": "main_probability_model",
                "guardrail_summary": "standard interpretation allowed",
                "detector_evidence_list": '[{"detector_family":"terminal_dynamic","detector_name":"terminal_loss_warning","severity":85,"confidence":0.8,"reason_code":"likely_churn_interval","business_interpretation":"interval evidence"}]',
                "allowed_claims": '["该对象进入业务优先级候选池。"]',
                "forbidden_claims": '["医院已经确定流失。"]',
                "recommended_action_candidates": '["建议人工核查近期采购频次下降原因。"]',
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
                "churn_probability_interpretation": "",
                "repeat_probability_H": 0.3,
                "repeat_probability_interpretation": "first_purchase_repeat_probability_not_recurring_churn_probability",
                "relative_value_at_risk_H": None,
                "relative_business_priority_score_H": None,
                "business_priority_interpretation": "one_shot_score_not_probability",
                "survival_state": "",
                "survival_confidence": None,
                "survival_summary": "",
                "demand_shape_label": "",
                "demand_shape_route": "",
                "guardrail_summary": "demand-shape missing; manual review required",
                "detector_evidence_list": "[]",
                "allowed_claims": '["该对象是 one-shot high value 关注对象。"]',
                "forbidden_claims": '["医院已经确定流失。", "one_shot_non_repeat_risk_H 是 recurring churn probability。"]',
                "recommended_action_candidates": '["建议业务人员判断是否需要促进第二次采购。"]',
                "data_quality_note": "",
            },
        ]
    )


def load_source(dry_run: bool) -> pd.DataFrame:
    if dry_run:
        return dry_run_bundle()
    sample = load_csv_if_exists(SAMPLE_PATH)
    if not sample.empty:
        return sample
    return load_csv_if_exists(BUNDLE_PATH)


def render_outputs(samples: pd.DataFrame, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    card_markdowns = {row.get("card_id"): render_card_markdown(row) for _, row in samples.iterrows()}
    markdown = render_cards_markdown(samples)
    html = render_cards_html(samples)
    boundary = claim_boundary_audit(samples, card_markdowns)
    completeness = field_completeness(samples, card_markdowns)
    write_text(output_dir / "static_line_card_samples.md", markdown)
    write_text(output_dir / "static_line_card_samples.html", html)
    sample_index(samples).to_csv(output_dir / "static_line_card_sample_index.csv", index=False)
    completeness.to_csv(output_dir / "static_line_card_field_completeness.csv", index=False)
    boundary.to_csv(output_dir / "static_line_card_claim_boundary_audit.csv", index=False)
    write_text(output_dir / "static_line_card_manual_review_checklist.md", manual_review_checklist_text())
    write_text(output_dir / "static_line_card_llm_readiness_note.md", llm_readiness_note(boundary, completeness))
    write_text(output_dir / "static_line_card_review_summary.md", summary_text(samples, completeness, boundary))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Render a small synthetic fixture.")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()

    # Auxiliary review files are intentionally not used to mutate samples; load
    # calls verify missing files do not fail and keep this script read-only.
    for path in [CLAIM_AUDIT_PATH, ACTION_AUDIT_PATH, LLM_READINESS_PATH]:
        if path.suffix.lower() == ".csv":
            _ = load_csv_if_exists(path)
        else:
            _ = path.read_text(encoding="utf-8") if path.exists() else ""
    source = load_source(args.dry_run)
    samples = choose_card_samples(source)
    render_outputs(samples, args.output_dir)


if __name__ == "__main__":
    main()
