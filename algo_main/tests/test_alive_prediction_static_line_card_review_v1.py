from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

from alg.tasks.die_prediction.static_line_card_review import (
    choose_card_samples,
    claim_boundary_audit,
    field_completeness,
    render_card_markdown,
    render_cards_html,
    render_cards_markdown,
)


def _row(**overrides: object) -> dict[str, object]:
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
        "final_candidate_status": "manual_review",
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
    }
    row.update(overrides)
    return row


def test_recurring_card_does_not_misinterpret_repeat_probability() -> None:
    samples = choose_card_samples(pd.DataFrame([_row()]))
    md = render_card_markdown(samples.iloc[0])

    assert "- repeat_probability_H: not_applicable" in md
    assert "repeat_probability_interpretation" not in md


def test_one_shot_card_does_not_show_churn_probability() -> None:
    samples = choose_card_samples(
        pd.DataFrame(
            [
                _row(
                    bundle_id="b2",
                    candidate_id="m2",
                    candidate_type="one_shot_attention",
                    final_candidate_status="one_shot_attention",
                    review_priority="P3",
                    churn_probability_H=None,
                    repeat_probability_H=0.3,
                    repeat_probability_interpretation="first_purchase_repeat_probability_not_recurring_churn_probability",
                    survival_summary="",
                    detector_evidence_list="[]",
                )
            ]
        )
    )
    md = render_card_markdown(samples.iloc[0])

    assert "churn_probability_H:" not in md
    assert "不是 recurring churn probability" in md


def test_observation_card_does_not_generate_priority_review() -> None:
    samples = choose_card_samples(
        pd.DataFrame(
            [
                _row(
                    bundle_id="b3",
                    candidate_type="demand_shape_observation",
                    final_candidate_status="observation_only",
                    review_priority="P2",
                    demand_shape_label="lumpy",
                    demand_shape_route="observation_only",
                    guardrail_summary="observation only unless strong external evidence",
                )
            ]
        )
    )
    md = render_card_markdown(samples.iloc[0])

    assert "final_candidate_status: observation_only" in md
    assert "final_candidate_status: priority_review" not in md


def test_forbidden_claim_detection_and_auto_dispatch_detection() -> None:
    samples = choose_card_samples(pd.DataFrame([_row(auto_dispatch_allowed=True)]))
    md = render_card_markdown(samples.iloc[0]).replace("auto_dispatch_allowed: false", "auto_dispatch_allowed: true")
    boundary = claim_boundary_audit(samples, {samples.loc[0, "card_id"]: md})

    assert "auto_dispatch_allowed_true" in set(boundary["violation_type"])


def test_card_completeness_and_markdown_html_render() -> None:
    samples = choose_card_samples(pd.DataFrame([_row()]))
    markdowns = {samples.loc[0, "card_id"]: render_card_markdown(samples.iloc[0])}
    completeness = field_completeness(samples, markdowns)
    md = render_cards_markdown(samples)
    html = render_cards_html(samples)

    assert bool(completeness.loc[0, "card_complete"]) is True
    assert "Alive Prediction Static Line Card Samples v1" in md
    assert "<html>" in html


def test_script_dry_run(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    output_dir = tmp_path / "static_cards"
    subprocess.run(
        [
            sys.executable,
            "scripts/render_alive_prediction_static_line_cards_v1.py",
            "--dry-run",
            "--output-dir",
            str(output_dir),
        ],
        cwd=root,
        check=True,
    )

    assert (output_dir / "static_line_card_samples.md").exists()
    assert (output_dir / "static_line_card_samples.html").exists()
    assert (output_dir / "static_line_card_claim_boundary_audit.csv").exists()
