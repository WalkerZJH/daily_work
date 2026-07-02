from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from alg.tasks.die_prediction.evidence_bundle import (
    build_detector_evidence_list,
    build_structured_evidence_bundle,
    recommended_actions_for,
)


def _status_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
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
    }
    row.update(overrides)
    return row


def _detector(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "candidate_id": "m1|h1|d1|drug_code|2024-01",
        "detector_family": "terminal_dynamic",
        "detector_name": "terminal_loss_warning",
        "hit_flag": True,
        "severity": 85.0,
        "confidence": 0.8,
        "reason_code": "likely_churn_interval",
        "business_interpretation": "interval evidence",
        "evidence_fields": "survival_state",
        "data_quality_status": "evaluated",
    }
    row.update(overrides)
    return row


def test_recurring_bundle_keeps_churn_probability_and_claims() -> None:
    bundle = build_structured_evidence_bundle(pd.DataFrame([_status_row()]), pd.DataFrame([_detector()]))

    assert bundle.loc[0, "churn_probability_H"] == 0.8
    assert bundle.loc[0, "candidate_type"] == "recurring_business_priority"
    claims = json.loads(bundle.loc[0, "allowed_claims"])
    assert any("业务优先级候选池" in claim for claim in claims)
    assert bool(bundle.loc[0, "auto_dispatch_allowed"]) is False


def test_one_shot_bundle_has_repeat_probability_not_churn_probability() -> None:
    bundle = build_structured_evidence_bundle(
        pd.DataFrame(
            [
                _status_row(
                    candidate_id="m2|h2|d2|drug_code",
                    candidate_type="one_shot_attention",
                    final_candidate_status="one_shot_attention",
                    review_priority="P3",
                    churn_probability_H=None,
                    churn_probability_interpretation="",
                    repeat_probability_H=0.3,
                    repeat_probability_interpretation="first_purchase_repeat_probability_not_recurring_churn_probability",
                    relative_value_at_risk_H=None,
                    relative_business_priority_score_H=None,
                    survival_state="",
                    demand_shape_label="",
                    demand_shape_route="",
                )
            ]
        ),
        pd.DataFrame(),
    )

    assert pd.isna(bundle.loc[0, "churn_probability_H"])
    assert bundle.loc[0, "repeat_probability_H"] == 0.3
    assert "not_recurring" in bundle.loc[0, "repeat_probability_interpretation"]
    forbidden = json.loads(bundle.loc[0, "forbidden_claims"])
    assert any("one_shot_non_repeat_risk_H" in claim for claim in forbidden)


def test_forbidden_claims_include_confirmed_churn_prohibition() -> None:
    bundle = build_structured_evidence_bundle(pd.DataFrame([_status_row()]), pd.DataFrame())
    forbidden = json.loads(bundle.loc[0, "forbidden_claims"])

    assert "医院已经确定流失。" in forbidden


def test_recommended_actions_by_status() -> None:
    manual_actions = recommended_actions_for(pd.Series(_status_row(final_candidate_status="manual_review")))
    one_shot_actions = recommended_actions_for(
        pd.Series(_status_row(candidate_type="one_shot_attention", final_candidate_status="one_shot_attention"))
    )

    assert any("人工核查" in action for action in manual_actions)
    assert any("第二次采购" in action for action in one_shot_actions)


def test_m6_fields_are_reserved_and_disabled() -> None:
    bundle = build_structured_evidence_bundle(pd.DataFrame([_status_row()]), pd.DataFrame())

    assert bool(bundle.loc[0, "evidence_timeline_available"]) is False
    assert pd.isna(bundle.loc[0, "evidence_timeline_reference"])
    assert bundle.loc[0, "evidence_persistence_summary"] == "not_implemented_in_v1"


def test_interface_only_detector_not_in_effective_evidence_list() -> None:
    evidence = pd.DataFrame(
        [
            _detector(),
            _detector(
                detector_family="price_warning",
                detector_name="low_price_purchase_warning",
                data_quality_status="not_evaluable",
                reason_code="interface_only_not_evaluable",
            ),
        ]
    )
    detector_list = build_detector_evidence_list(evidence)
    values = json.loads(detector_list.loc[0, "detector_evidence_list"])

    assert len(values) == 1
    assert values[0]["detector_name"] == "terminal_loss_warning"


def test_evidence_bundle_script_dry_run(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    output_dir = tmp_path / "evidence_bundle"
    subprocess.run(
        [
            sys.executable,
            "scripts/run_alive_prediction_evidence_bundle_v1.py",
            "--dry-run",
            "--output-dir",
            str(output_dir),
        ],
        cwd=root,
        check=True,
    )

    out = pd.read_csv(output_dir / "structured_evidence_bundle.csv")
    assert not out.empty
    assert (~out["auto_dispatch_allowed"].astype(bool)).all()
    assert (~out["evidence_timeline_available"].astype(bool)).all()
    assert (output_dir / "evidence_bundle_semantics_audit.md").exists()
