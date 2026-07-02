from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

from alg.tasks.die_prediction.row_level_backtest_frame import (
    build_one_shot_repeat_backtest_frame,
    build_recurring_backtest_frame,
    build_row_level_backtest_frames,
    closed_window_flag,
    one_shot_repeat_label,
    recurring_label_for_window,
)


def test_recurring_fixed_window_label_construction() -> None:
    label = recurring_label_for_window("2024-01", ["2024-02-29"], 3, "2024-12-31")

    assert label["label_window_closed"] is True
    assert label["label_alive_H"] == 1
    assert label["label_die_H"] == 0


def test_label_window_closed_logic() -> None:
    assert closed_window_flag("2024-07-31", "2024-12-31")
    assert not closed_window_flag("2025-01-31", "2024-12-31")


def test_one_shot_second_purchase_label_construction() -> None:
    repeated = one_shot_repeat_label("2024-01", 2, 3, "2024-12-31")
    not_repeated = one_shot_repeat_label("2024-01", 1, 3, "2024-12-31")

    assert repeated["label_repeat_H"] == 1
    assert repeated["label_non_repeat_H"] == 0
    assert not_repeated["label_repeat_H"] == 0
    assert not_repeated["label_non_repeat_H"] == 1


def test_unclosed_one_shot_window_marked_false() -> None:
    label = one_shot_repeat_label("2024-11", 1, 3, "2024-12-31")

    assert label["label_window_closed"] is False
    assert pd.isna(label["label_repeat_H"])


def test_prediction_label_join_keeps_entity_keys() -> None:
    candidate = pd.DataFrame(
        {
            "candidate_id": ["m|h|d|drug_code|2024-01|3"],
            "manufacturer_code": ["m"],
            "hospital_code": ["h"],
            "drug_group": ["d"],
            "drug_group_source": ["drug_code"],
            "cutoff_month": ["2024-01"],
            "horizon": [3],
            "churn_probability_H": [0.8],
            "relative_value_at_risk_H": [100.0],
            "relative_business_priority_score_H": [80.0],
        }
    )
    labels = pd.DataFrame(
        {
            "manufacturer_code": ["m"],
            "hospital_code": ["h"],
            "drug_group": ["d"],
            "cutoff_month": ["2024-01-31"],
            "label_alive_H3": [0],
            "label_die_H3": [1],
            "label_alive_H6": [0],
            "label_die_H6": [1],
            "label_alive_H12": [0],
            "label_die_H12": [1],
        }
    )
    frame, source = build_recurring_backtest_frame(candidate, labels, pd.DataFrame(), pd.DataFrame(), pd.DataFrame())

    assert source == "candidate_level_join_existing_alive_labels"
    assert frame["manufacturer_code"].iloc[0] == "m"
    assert frame["label_die_H"].iloc[0] == 1
    assert bool(frame["label_window_closed"].iloc[0])


def test_candidate_only_fallback_does_not_crash() -> None:
    candidate = pd.DataFrame(
        {
            "candidate_id": ["m|h|d|drug_code|2024-01|3"],
            "manufacturer_code": ["m"],
            "hospital_code": ["h"],
            "drug_group": ["d"],
            "drug_group_source": ["drug_code"],
            "cutoff_month": ["2024-01"],
            "horizon": [3],
            "churn_probability_H": [0.8],
            "relative_value_at_risk_H": [100.0],
            "relative_business_priority_score_H": [80.0],
        }
    )
    frame, source = build_recurring_backtest_frame(candidate, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame())

    assert source == "label_artifact_missing"
    assert len(frame) == 1
    assert not bool(frame["label_window_closed"].iloc[0])


def test_one_shot_frame_from_feature_snapshot() -> None:
    one_shot = pd.DataFrame(
        {
            "manufacturer_code": ["m"],
            "hospital_code": ["h"],
            "drug_group": ["d"],
            "drug_group_source": ["drug_code"],
            "first_purchase_month": ["2024-01"],
            "horizon": ["H3"],
            "repeat_probability_H": [0.7],
            "one_shot_non_repeat_risk_H": [0.3],
            "selected_attention_score": [10.0],
            "selected_attention_policy": ["balanced_attention_score"],
            "probability_interpretation": ["first_purchase_repeat_probability_not_recurring_churn_probability"],
        }
    )
    snapshots = pd.DataFrame(
        {
            "manufacturer_code": ["m"],
            "hospital_code": ["h"],
            "drug_group": ["d"],
            "cutoff_month": ["2024-04-30"],
            "purchase_count_asof_cutoff": [2],
        }
    )
    frame, source = build_one_shot_repeat_backtest_frame(one_shot, snapshots)

    assert source == "candidate_level_join_feature_snapshot_purchase_count"
    assert frame["label_repeat_H"].iloc[0] == 1
    assert bool(frame["label_window_closed"].iloc[0])


def test_script_dry_run_and_no_model_file(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "build_alive_prediction_row_level_backtest_frame_v1.py"
    out_dir = tmp_path / "row_level_frame"
    result = subprocess.run(
        [sys.executable, str(script), "--dry-run", "--output-dir", str(out_dir)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "wrote row-level backtest frames" in result.stdout
    assert (out_dir / "recurring_backtest_frame.csv").exists()
    assert (out_dir / "one_shot_repeat_backtest_frame.csv").exists()
    assert not list(out_dir.glob("*.pkl"))
    assert not list(out_dir.glob("*.joblib"))


def test_build_with_missing_inputs_does_not_modify_inputs(tmp_path: Path) -> None:
    root = tmp_path / "algo_main"
    out_dir = root / "reports/alive_prediction_row_level_backtest_frame_v1"
    outputs = build_row_level_backtest_frames(root, out_dir, dry_run=False)

    assert outputs["recurring"].empty
    assert outputs["one_shot"].empty
    assert (out_dir / "row_level_backtest_frame_summary.md").exists()
