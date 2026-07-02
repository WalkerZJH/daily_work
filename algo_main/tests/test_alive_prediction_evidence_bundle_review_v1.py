from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

from alg.tasks.die_prediction.evidence_bundle_review import (
    actionability_audit,
    claim_consistency_audit,
    field_completeness_by_status,
    stratified_sample,
)


def _bundle_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
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
        "repeat_probability_interpretation": "",
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
    }
    row.update(overrides)
    return row


def test_stratified_sample_runs_on_small_bundle() -> None:
    bundle = pd.DataFrame(
        [
            _bundle_row(bundle_id="b1", final_candidate_status="priority_review", review_priority="P1"),
            _bundle_row(bundle_id="b2", candidate_id="m2", final_candidate_status="manual_review", review_priority="P2"),
            _bundle_row(bundle_id="b3", candidate_id="m3", candidate_type="one_shot_attention", final_candidate_status="one_shot_attention", review_priority="P3"),
        ]
    )

    sample = stratified_sample(bundle)

    assert not sample.empty
    assert {"priority_review", "manual_review", "one_shot_attention"}.issubset(set(sample["final_candidate_status"]))


def test_claim_consistency_detects_forbidden_violation() -> None:
    bundle = pd.DataFrame(
        [
            _bundle_row(
                allowed_claims='["医院已经确定流失。"]',
                forbidden_claims='["医院已经确定流失。"]',
            )
        ]
    )

    audit = claim_consistency_audit(bundle)

    assert not audit["claim_check_pass"].all()
    assert "allowed_contains_forbidden_phrase" in set(audit["violation_type"])


def test_one_shot_churn_probability_pollution_detected() -> None:
    bundle = pd.DataFrame(
        [
            _bundle_row(
                candidate_type="one_shot_attention",
                churn_probability_H=0.7,
                repeat_probability_H=0.3,
                repeat_probability_interpretation="first_purchase_repeat_probability_not_recurring_churn_probability",
                allowed_claims='["该 one-shot 的 recurring churn_probability 是 0.7。"]',
                forbidden_claims='["one_shot_non_repeat_risk_H 是 recurring churn probability。"]',
            )
        ]
    )

    audit = claim_consistency_audit(bundle)

    assert {"one_shot_churn_probability_field_non_null", "one_shot_churn_probability_claim"}.issubset(
        set(audit["violation_type"])
    )


def test_actionability_audit_finds_missing_critical_fields() -> None:
    bundle = pd.DataFrame([_bundle_row(churn_probability_H=None, survival_summary="", detector_evidence_list="[]")])

    audit = actionability_audit(bundle)

    assert bool(audit.loc[0, "actionable_flag"]) is False
    assert "churn_probability_H" in audit.loc[0, "missing_critical_fields"]


def test_field_completeness_aggregation() -> None:
    bundle = pd.DataFrame([_bundle_row(), _bundle_row(bundle_id="b2", candidate_id="m2", churn_probability_H=None)])

    report = field_completeness_by_status(bundle)

    assert report["row_count"].sum() == 2
    assert "churn_probability_H_non_null_rate" in report.columns


def test_auto_dispatch_true_is_violation() -> None:
    bundle = pd.DataFrame([_bundle_row(auto_dispatch_allowed=True)])

    audit = claim_consistency_audit(bundle)

    assert "auto_dispatch_allowed_true" in set(audit["violation_type"])


def test_script_dry_run(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    output_dir = tmp_path / "review"
    subprocess.run(
        [
            sys.executable,
            "scripts/review_alive_prediction_evidence_bundle_v1.py",
            "--dry-run",
            "--output-dir",
            str(output_dir),
        ],
        cwd=root,
        check=True,
    )

    assert (output_dir / "evidence_bundle_stratified_sample.csv").exists()
    assert (output_dir / "evidence_bundle_llm_readiness_report.md").exists()
