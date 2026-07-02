from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import pandas as pd

from alg.tasks.die_prediction.detectors_v2 import (
    conditional_binomial_rate_drop_p_value,
    purchase_frequency_decay_rate_test,
    purchase_interval_overdue_warning,
)


def _survival_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "candidate_id": "m1|h1|d1|drug_code|2024-01",
        "manufacturer_code": "m1",
        "hospital_code": "h1",
        "drug_group": "d1",
        "drug_group_source": "drug_code",
        "cutoff_month": "2024-01",
        "horizon": "H6",
        "churn_probability_H": 0.8,
        "relative_business_priority_score_H": 80.0,
        "relative_value_at_risk_H": 100.0,
        "survival_state": "materially_overdue",
        "survival_confidence": 0.8,
        "overdue_ratio": 2.4,
        "expected_interval_months": 2.0,
        "months_since_last_purchase": 4.8,
        "history_sufficiency_flag": "history_sufficient",
        "demand_shape_label": "smooth",
        "demand_shape_route": "main_probability_model",
    }
    row.update(overrides)
    return row


def test_d001_overdue_ratio_hit_rule() -> None:
    out = purchase_interval_overdue_warning(pd.DataFrame([_survival_row(overdue_ratio=2.1)]))

    assert bool(out["hit_flag"].iloc[0])
    assert out["detector_name"].iloc[0] == "purchase_interval_overdue_warning"
    assert out["severity"].iloc[0] >= 60


def test_d001_observation_only_guardrail() -> None:
    out = purchase_interval_overdue_warning(
        pd.DataFrame([_survival_row(demand_shape_route="observation_only", demand_shape_label="lumpy")])
    )

    assert not bool(out["hit_flag"].iloc[0])
    assert out["reason_code"].iloc[0] == "observation_only_guardrail"
    assert out["confidence"].iloc[0] <= 0.4


def test_d001_mad_missing_has_no_p_value_or_fdr() -> None:
    out = purchase_interval_overdue_warning(pd.DataFrame([_survival_row()]))

    assert pd.isna(out["p_value"].iloc[0])
    assert out["p_value_method"].iloc[0] == "not_available_mad_missing"
    assert not bool(out["fdr_eligible"].iloc[0])


def test_d001_mad_available_generates_robust_z_p_value() -> None:
    out = purchase_interval_overdue_warning(
        pd.DataFrame(
            [
                _survival_row(
                    days_since_last_purchase_asof_cutoff=100.0,
                    median_purchase_interval_days_asof_cutoff=40.0,
                    purchase_interval_mad_days_asof_cutoff=20.0,
                )
            ]
        )
    )
    values = json.loads(out["evidence_values"].iloc[0])

    assert math.isclose(values["robust_z"], 3.0)
    assert 0.0 <= out["p_value"].iloc[0] <= 1.0
    assert bool(out["fdr_eligible"].iloc[0])


def test_d002_rate_ratio_and_p_value() -> None:
    out = purchase_frequency_decay_rate_test(
        pd.DataFrame(
            [
                _survival_row(
                    order_count_last_3m_asof_cutoff=0,
                    order_count_last_6m_asof_cutoff=1,
                    order_count_last_12m_asof_cutoff=10,
                )
            ]
        )
    )
    values = json.loads(out["evidence_values"].iloc[0])

    assert values["rate_ratio_3m_vs_previous_9m"] == 0.0
    assert 0.0 <= out["p_value"].iloc[0] <= 1.0
    assert out["p_value_method"].iloc[0] == "conditional_binomial_rate_drop_test"


def test_conditional_binomial_p_value_runs() -> None:
    p_value = conditional_binomial_rate_drop_p_value(0, 9, 3, 9)

    assert 0.0 <= p_value <= 1.0


def test_d002_negative_base_count_not_evaluable() -> None:
    out = purchase_frequency_decay_rate_test(
        pd.DataFrame(
            [
                _survival_row(
                    order_count_last_3m_asof_cutoff=5,
                    order_count_last_6m_asof_cutoff=7,
                    order_count_last_12m_asof_cutoff=4,
                )
            ]
        )
    )

    assert out["data_quality_status"].iloc[0] == "not_evaluable"
    assert out["reason_code"].iloc[0] == "not_evaluable"


def test_intermittent_lumpy_lowers_frequency_confidence() -> None:
    out = purchase_frequency_decay_rate_test(
        pd.DataFrame(
            [
                _survival_row(
                    order_count_last_3m_asof_cutoff=0,
                    order_count_last_6m_asof_cutoff=1,
                    order_count_last_12m_asof_cutoff=10,
                    demand_shape_label="lumpy",
                )
            ]
        )
    )

    assert out["confidence"].iloc[0] <= 0.5


def test_p_value_not_named_probability_and_fdr_not_applied() -> None:
    out = purchase_frequency_decay_rate_test(
        pd.DataFrame(
            [
                _survival_row(
                    order_count_last_3m_asof_cutoff=0,
                    order_count_last_6m_asof_cutoff=1,
                    order_count_last_12m_asof_cutoff=10,
                )
            ]
        )
    )

    assert "probability" not in " ".join(out.columns)
    assert not out["fdr_applied"].astype(bool).any()


def test_script_dry_run_does_not_modify_v1_outputs() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    v1_path = repo_root / "reports/alive_prediction_detectors_v1/detector_evidence_results.csv"
    before = v1_path.stat().st_mtime if v1_path.exists() else None

    completed = subprocess.run(
        [sys.executable, str(repo_root / "scripts/run_alive_prediction_detectors_v2.py"), "--dry-run"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )

    after = v1_path.stat().st_mtime if v1_path.exists() else None
    assert "D001_rows=" in completed.stdout
    assert before == after
