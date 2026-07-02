from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

from alg.tasks.die_prediction.stage_end_audit import (
    Assessment,
    assess_demand_shape,
    assess_evidence_material,
    assess_one_shot,
    assess_survival_detector,
    build_required_fixes,
    build_risk_register,
    freeze_decision,
    run_stage_end_audit,
)


def _assessment(area: str, status: str, requires_fix: bool = False) -> Assessment:
    return Assessment(area, status, requires_fix, "summary", {}, "")


def test_missing_input_reports_do_not_crash(tmp_path: Path) -> None:
    result = run_stage_end_audit(tmp_path, output_dir=tmp_path / "out")

    assert result["stage_freeze_decision"] in {"freeze_with_caveats", "do_not_freeze", "freeze"}
    assert (tmp_path / "out/stage_end_algorithm_risk_review.md").exists()


def test_freeze_decision_rules() -> None:
    clear = [
        _assessment("demand_shape", "resolved"),
        _assessment("value_at_risk", "clear"),
        _assessment("one_shot", "usable"),
    ]
    caveat = clear + [_assessment("survival_detector", "acceptable_with_caveat")]
    blocking = caveat + [_assessment("evidence_material", "requires_fix_before_review", True)]

    assert freeze_decision(clear) == "freeze"
    assert freeze_decision(caveat) == "freeze_with_caveats"
    assert freeze_decision(blocking) == "do_not_freeze"


def test_risk_register_and_blocking_fixes() -> None:
    assessments = [
        _assessment("demand_shape", "acceptable_with_caveat"),
        _assessment("value_at_risk", "acceptable_with_caveat"),
        _assessment("one_shot", "usable_with_caveat"),
        _assessment("survival_detector", "acceptable_with_caveat"),
        _assessment("evidence_material", "ready_for_manual_review"),
    ]
    for item in assessments:
        item.details.update(
            {
                "raw_rows": 100,
                "display_ready_rows": 5,
                "intermittent_lumpy_history_insufficient_rate": 0.1,
                "relative_value_columns": ["relative_value_at_risk_H"],
                "mean_auc": 0.59,
                "quantity_hit_rate": 0.6,
                "price_interface_only": True,
                "delivery_interface_only": True,
                "p0_count": 0,
                "strong_count": 0,
            }
        )

    risk_register = build_risk_register(assessments)
    required = build_required_fixes(assessments)
    required_blocking = build_required_fixes([_assessment("demand_shape", "requires_fix_before_freeze", True)])

    assert len(risk_register) >= 10
    assert required.empty
    assert len(required_blocking) == 1
    assert bool(required_blocking["required_before_freeze"].iloc[0])


def test_demand_shape_assessment_from_mock_summary(tmp_path: Path) -> None:
    base = tmp_path / "reports/alive_prediction_m1_m2_corrections_v1"
    base.mkdir(parents=True)
    pd.DataFrame(
        [
            {"metric": "total_rows", "value": 19770},
            {"metric": "display_ready_rows", "value": 200},
            {"metric": "latest_cutoff_rows", "value": 3076},
        ]
    ).to_csv(base / "demand_shape_observation_raw_profile.csv", index=False)
    pd.DataFrame([{"filter_stage": "raw", "row_count": 19770, "note": "raw observation rows retained separately"}]).to_csv(
        base / "demand_shape_observation_filter_audit.csv", index=False
    )
    pd.DataFrame(
        [
            {
                "demand_shape_label": "lumpy",
                "history_sufficiency_flag": "history_insufficient",
                "purchase_count_asof_cutoff": 1,
                "active_month_count_asof_cutoff": 1,
                "adi_asof_cutoff": None,
                "cv2_quantity_asof_cutoff": None,
            }
        ]
    ).to_csv(base / "demand_shape_history_sufficiency_flags.csv", index=False)
    (base / "m1_m2_next_stage_gate.md").write_text("proceed_to_M3 = conditional", encoding="utf-8")

    assessment = assess_demand_shape(tmp_path)

    assert assessment.status == "acceptable_with_caveat"
    assert not assessment.requires_fix
    assert assessment.details["display_ready_rows"] == 200.0


def test_one_shot_metrics_assessment_from_mock_csv(tmp_path: Path) -> None:
    base = tmp_path / "reports/alive_prediction_one_shot_repeat_v1"
    base.mkdir(parents=True)
    pd.DataFrame(
        [
            {"horizon": "H3", "auc": 0.58, "ece": 0.12, "fallback_used": False, "skip_reason": ""},
            {"horizon": "H6", "auc": 0.6, "ece": 0.1, "fallback_used": False, "skip_reason": ""},
        ]
    ).to_csv(base / "one_shot_repeat_metrics.csv", index=False)
    pd.DataFrame(
        [
            {
                "candidate_id": "c1",
                "repeat_probability_H": 0.4,
                "probability_interpretation": "first_purchase_repeat_probability_not_recurring_churn_probability",
            }
        ]
    ).to_csv(base / "one_shot_attention_candidates_enriched.csv", index=False)
    pd.DataFrame([{"candidate_id": "c1"}]).to_csv(base / "one_shot_explanation_factors.csv", index=False)
    (base / "one_shot_leakage_audit.md").write_text("No leakage.", encoding="utf-8")

    assessment = assess_one_shot(tmp_path)

    assert assessment.status == "usable_with_caveat"
    assert not assessment.requires_fix
    assert assessment.details["churn_probability_columns"] == []


def test_detector_assessment_from_mock_csv(tmp_path: Path) -> None:
    survival = tmp_path / "reports/alive_prediction_survival_lite_v1"
    detector = tmp_path / "reports/alive_prediction_detectors_v1"
    status = tmp_path / "reports/alive_prediction_status_decision_v1"
    survival.mkdir(parents=True)
    detector.mkdir(parents=True)
    status.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "survival_state": "materially_overdue",
                "survival_confidence": 0.8,
                "survival_note": "probability_and_business_priority_unchanged",
            }
        ]
    ).to_csv(survival / "survival_refinement_results.csv", index=False)
    (survival / "survival_leakage_audit.md").write_text("No direct leakage.", encoding="utf-8")
    pd.DataFrame(
        [
            {"detector_name": "terminal_loss_warning", "detector_status": "implemented", "hit_count": 1, "hit_rate": 1.0},
            {
                "detector_name": "purchase_quantity_fluctuation_warning",
                "detector_status": "implemented",
                "hit_count": 2,
                "hit_rate": 0.8,
            },
            {"detector_name": "low_price_purchase_warning", "detector_status": "interface_only", "hit_count": 0, "hit_rate": 0},
            {"detector_name": "delayed_response_warning", "detector_status": "interface_only", "hit_count": 0, "hit_rate": 0},
        ]
    ).to_csv(detector / "detector_family_summary.csv", index=False)
    pd.DataFrame([{"evidence_strength": "medium"}]).to_csv(status / "candidate_status_decision.csv", index=False)

    assessment = assess_survival_detector(tmp_path)

    assert assessment.status == "acceptable_with_caveat"
    assert not assessment.requires_fix
    assert assessment.details["quantity_hit_rate"] == 0.8


def test_static_card_assessment_from_mock_reports(tmp_path: Path) -> None:
    bundle = tmp_path / "reports/alive_prediction_evidence_bundle_v1"
    review = tmp_path / "reports/alive_prediction_evidence_bundle_review_v1"
    static = tmp_path / "reports/alive_prediction_static_line_card_review_v1"
    bundle.mkdir(parents=True)
    review.mkdir(parents=True)
    static.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "review_priority": "P1",
                "evidence_strength": "medium",
                "auto_dispatch_allowed": False,
                "allowed_claims": "[]",
                "forbidden_claims": "[]",
                "recommended_action_candidates": "[]",
            }
        ]
    ).to_csv(bundle / "structured_evidence_bundle.csv", index=False)
    pd.DataFrame(
        [
            {
                "candidate_type": "recurring_business_priority",
                "has_allowed_claims_rate": 1.0,
                "has_forbidden_claims_rate": 1.0,
                "has_recommended_actions_rate": 1.0,
            }
        ]
    ).to_csv(bundle / "evidence_bundle_completeness_report.csv", index=False)
    pd.DataFrame([{"claim_check_pass": True}]).to_csv(review / "evidence_bundle_claim_consistency_audit.csv", index=False)
    pd.DataFrame([{"actionable_flag": True}]).to_csv(review / "evidence_bundle_actionability_audit.csv", index=False)
    pd.DataFrame([{"claim_boundary_pass": True}]).to_csv(static / "static_line_card_claim_boundary_audit.csv", index=False)
    pd.DataFrame([{"card_complete": True}]).to_csv(static / "static_line_card_field_completeness.csv", index=False)

    assessment = assess_evidence_material(tmp_path)

    assert assessment.status == "ready_for_manual_review"
    assert not assessment.requires_fix


def test_script_dry_run_fixture(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts/audit_alive_prediction_stage_end_v1.py"
    out = tmp_path / "out"
    fixture = tmp_path / "fixture"

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--dry-run",
            "--fixture-root",
            str(fixture),
            "--output-dir",
            str(out),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "stage_freeze_decision=" in completed.stdout
    assert (out / "stage_end_freeze_decision.md").exists()
