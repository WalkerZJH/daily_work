from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

from alg.tasks.die_prediction.detectors import (
    EVIDENCE_COLUMNS,
    interface_only_detectors,
    purchase_frequency_fluctuation_warning,
    purchase_quantity_fluctuation_warning,
    terminal_loss_warning,
)


def _base_candidate(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "candidate_id": "m1|h1|d1|drug_code|2024-01|H6",
        "manufacturer_code": "m1",
        "hospital_code": "h1",
        "drug_group": "d1",
        "drug_group_source": "drug_code",
        "cutoff_month": "2024-01",
        "horizon": "H6",
        "churn_probability_H": 0.8,
        "relative_business_priority_score_H": 80.0,
        "relative_value_at_risk_H": 100.0,
        "survival_state": "likely_churn_interval",
        "survival_confidence": 0.8,
        "overdue_ratio": 3.2,
        "history_sufficiency_flag": "history_sufficient",
        "demand_shape_label": "smooth",
        "demand_shape_route": "main_probability_model",
        "order_count_last_3m_asof_cutoff": 0,
        "order_count_last_6m_asof_cutoff": 1,
        "order_count_last_12m_asof_cutoff": 12,
        "purchase_quantity_sum_last_3m_asof_cutoff": 3,
        "historical_avg_monthly_quantity_asof_cutoff": 10,
        "purchase_count_asof_cutoff": 8,
    }
    row.update(overrides)
    return row


def test_terminal_loss_warning_hit_and_observation_guardrail() -> None:
    df = pd.DataFrame(
        [
            _base_candidate(),
            _base_candidate(
                candidate_id="m2|h2|d2|drug_code|2024-01|H6",
                manufacturer_code="m2",
                hospital_code="h2",
                drug_group="d2",
                survival_state="materially_overdue",
                demand_shape_route="observation_only",
                demand_shape_label="lumpy",
                overdue_ratio=2.4,
            ),
        ]
    )

    evidence = terminal_loss_warning(df)

    assert set(EVIDENCE_COLUMNS).issubset(evidence.columns)
    assert bool(evidence.loc[0, "hit_flag"]) is True
    assert evidence.loc[0, "severity"] >= 80
    assert bool(evidence.loc[1, "hit_flag"]) is False
    assert evidence.loc[1, "reason_code"] == "observation_only_guardrail"


def test_purchase_frequency_drop_detector() -> None:
    evidence = purchase_frequency_fluctuation_warning(pd.DataFrame([_base_candidate()]))

    assert bool(evidence.loc[0, "hit_flag"]) is True
    assert evidence.loc[0, "detector_name"] == "purchase_frequency_fluctuation_warning"
    assert evidence.loc[0, "reason_code"] == "frequency_drop_multi_window"
    assert evidence.loc[0, "severity"] > 0


def test_purchase_quantity_fluctuation_detector() -> None:
    drop = purchase_quantity_fluctuation_warning(pd.DataFrame([_base_candidate()]))
    spike = purchase_quantity_fluctuation_warning(
        pd.DataFrame([_base_candidate(purchase_quantity_sum_last_3m_asof_cutoff=120)])
    )

    assert bool(drop.loc[0, "hit_flag"]) is True
    assert drop.loc[0, "reason_code"] == "quantity_drop"
    assert bool(spike.loc[0, "hit_flag"]) is True
    assert spike.loc[0, "reason_code"] == "quantity_spike"


def test_interface_only_detectors_do_not_emit_hits_or_probability_columns() -> None:
    evidence = interface_only_detectors()

    assert {"low_price_purchase_warning", "order_price_spread_warning"}.issubset(set(evidence["detector_name"]))
    assert {"rejection_response_warning", "delayed_response_warning", "low_delivery_rate_warning"}.issubset(
        set(evidence["detector_name"])
    )
    assert not evidence["hit_flag"].any()
    assert evidence["data_quality_status"].eq("not_evaluable").all()
    assert "severity_probability" not in evidence.columns
    assert "confidence_probability" not in evidence.columns
    assert {"evidence_id", "evidence_hash", "previous_evidence_id", "evidence_timeline_reference"}.issubset(
        evidence.columns
    )
    assert evidence["previous_evidence_id"].isna().all()
    assert evidence["evidence_timeline_reference"].isna().all()


def test_missing_fields_do_not_crash_detectors() -> None:
    minimal = pd.DataFrame([_base_candidate()])[["candidate_id", "manufacturer_code", "hospital_code", "drug_group"]]

    freq = purchase_frequency_fluctuation_warning(minimal)
    qty = purchase_quantity_fluctuation_warning(minimal)

    assert freq.loc[0, "data_quality_status"] == "not_evaluable"
    assert qty.loc[0, "data_quality_status"] == "not_evaluable"


def test_detector_script_dry_run(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    output_dir = tmp_path / "detectors"

    subprocess.run(
        [
            sys.executable,
            "scripts/run_alive_prediction_detectors_v1.py",
            "--dry-run",
            "--output-dir",
            str(output_dir),
        ],
        cwd=root,
        check=True,
    )

    assert (output_dir / "detector_evidence_results.csv").exists()
    assert (output_dir / "detector_family_summary.csv").exists()
    forbidden = []
    for pattern in ("*.joblib", "*.pkl", "*.skops", "*.cbm", "*.onnx", "*.zip"):
        forbidden.extend(output_dir.rglob(pattern))
    assert forbidden == []
