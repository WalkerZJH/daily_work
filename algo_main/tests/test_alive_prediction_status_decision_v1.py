from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

from alg.tasks.die_prediction.status_decision import (
    aggregate_detector_evidence,
    build_status_decisions,
    decide_one_shot_status,
    decide_recurring_status,
    load_csv_if_exists,
)


def _recurring_candidate(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "candidate_id": "m1|h1|d1|drug_code|2024-01",
        "manufacturer_code": "m1",
        "hospital_code": "h1",
        "drug_group": "d1",
        "drug_group_source": "drug_code",
        "cutoff_month": "2024-01",
        "horizon": "H6",
        "churn_probability_H": 0.8,
        "relative_value_at_risk_H": 100.0,
        "relative_business_priority_score_H": 100.0,
        "survival_state": "likely_churn_interval",
        "survival_confidence": 0.8,
        "overdue_ratio": 3.0,
        "history_sufficiency_flag": "history_sufficient",
        "demand_shape_label": "smooth",
        "demand_shape_route": "main_probability_model",
    }
    row.update(overrides)
    return row


def _detector(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "candidate_id": "m1|h1|d1|drug_code|2024-01",
        "detector_name": "terminal_loss_warning",
        "hit_flag": True,
        "severity": 85.0,
        "confidence": 0.8,
        "reason_code": "likely_churn_interval",
        "business_interpretation": "interval evidence",
        "data_quality_status": "evaluated",
    }
    row.update(overrides)
    return row


def test_recurring_priority_review_rule() -> None:
    decision = decide_recurring_status(
        recurring=pd.DataFrame(),
        survival=pd.DataFrame([_recurring_candidate()]),
        detector_agg=aggregate_detector_evidence(pd.DataFrame([_detector()])),
    )

    assert decision.loc[0, "final_candidate_status"] == "priority_review"
    assert decision.loc[0, "evidence_strength"] == "strong"
    assert bool(decision.loc[0, "auto_dispatch_allowed"]) is False


def test_observation_only_guardrail_and_lumpy_no_priority() -> None:
    decision = decide_recurring_status(
        recurring=pd.DataFrame(),
        survival=pd.DataFrame(
            [
                _recurring_candidate(
                    survival_state="low_confidence_lumpy",
                    demand_shape_label="lumpy",
                    demand_shape_route="observation_only",
                    survival_confidence=0.4,
                )
            ]
        ),
        detector_agg=aggregate_detector_evidence(pd.DataFrame([_detector()])),
    )

    assert decision.loc[0, "final_candidate_status"] == "observation_only"
    assert decision.loc[0, "final_candidate_status"] != "priority_review"


def test_one_shot_attention_does_not_output_churn_probability() -> None:
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
                "selected_attention_score": 10.0,
            }
        ]
    )

    decision = decide_one_shot_status(one_shot, aggregate_detector_evidence(pd.DataFrame()))

    assert decision.loc[0, "final_candidate_status"] == "one_shot_attention"
    assert pd.isna(decision.loc[0, "churn_probability_H"])
    assert decision.loc[0, "repeat_probability_interpretation"] == (
        "first_purchase_repeat_probability_not_recurring_churn_probability"
    )


def test_interface_only_detector_not_effective_and_quantity_only_not_strong() -> None:
    evidence = pd.DataFrame(
        [
            _detector(detector_name="low_price_purchase_warning", hit_flag=True, data_quality_status="not_evaluable"),
            _detector(detector_name="purchase_quantity_fluctuation_warning", severity=95.0, confidence=0.9),
        ]
    )
    agg = aggregate_detector_evidence(evidence)
    decision = decide_recurring_status(
        recurring=pd.DataFrame(),
        survival=pd.DataFrame([_recurring_candidate(survival_state="normal_interval", survival_confidence=0.9)]),
        detector_agg=agg,
    )

    assert agg.loc[0, "detector_hit_count"] == 1
    assert decision.loc[0, "evidence_strength"] == "weak"
    assert decision.loc[0, "final_candidate_status"] != "priority_review"


def test_m6_fields_reserved_but_not_implemented() -> None:
    decision = decide_recurring_status(
        recurring=pd.DataFrame(),
        survival=pd.DataFrame([_recurring_candidate()]),
        detector_agg=aggregate_detector_evidence(pd.DataFrame([_detector()])),
    )

    assert bool(decision.loc[0, "evidence_timeline_available"]) is False
    assert pd.isna(decision.loc[0, "evidence_timeline_reference"])
    assert decision.loc[0, "evidence_persistence_summary"] == "not_implemented_in_v1"


def test_missing_m2_and_missing_demand_shape_inputs_do_not_fail() -> None:
    combined, recurring, one_shot, demand = build_status_decisions(
        recurring=pd.DataFrame(),
        survival=pd.DataFrame([_recurring_candidate()]),
        detectors=pd.DataFrame([_detector()]),
        one_shot=pd.DataFrame(),
        demand_shape_display=pd.DataFrame(),
    )

    assert len(combined) == 1
    assert len(recurring) == 1
    assert one_shot.empty
    assert demand.empty


def test_load_csv_missing_returns_empty_without_raw_observation() -> None:
    missing = load_csv_if_exists(Path("definitely_missing.csv"))
    assert missing.empty


def test_status_decision_script_dry_run(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    output_dir = tmp_path / "status_decision"
    subprocess.run(
        [
            sys.executable,
            "scripts/run_alive_prediction_status_decision_v1.py",
            "--dry-run",
            "--output-dir",
            str(output_dir),
        ],
        cwd=root,
        check=True,
    )

    out = pd.read_csv(output_dir / "candidate_status_decision.csv")
    assert not out.empty
    assert (~out["auto_dispatch_allowed"].astype(bool)).all()
    assert (output_dir / "status_decision_semantics_audit.md").exists()
