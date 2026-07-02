from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd


def _events() -> pd.DataFrame:
    base = {
        "drug_group_source": "drug_code",
        "drug_category_code": "c1",
        "province_code": "p1",
        "city_code": "city1",
        "county_code": "county1",
        "hospital_level_code": "L1",
        "ownership_type_code": "O1",
        "raw_sensitive_purchase_quantity": 10.0,
        "raw_sensitive_purchase_amount": 100.0,
        "raw_sensitive_delivery_quantity": 10.0,
        "raw_sensitive_arrival_quantity": 10.0,
        "order_phase_code": "ok",
        "delivery_state_code": "arrived",
        "order_failure_flag": 0,
        "order_terminal_flag": 1,
    }
    rows = [
        {
            **base,
            "manufacturer_code": "m1",
            "hospital_code": "h1",
            "drug_code": "d1",
            "drug_group": "d1",
            "purchase_time": "2020-01-10",
            "purchase_month": "2020-01-31",
        },
        {
            **base,
            "manufacturer_code": "m1",
            "hospital_code": "h1",
            "drug_code": "d1",
            "drug_group": "d1",
            "purchase_time": "2020-02-10",
            "purchase_month": "2020-02-29",
        },
        {
            **base,
            "manufacturer_code": "m2",
            "hospital_code": "h2",
            "drug_code": "d2",
            "drug_group": "d2",
            "purchase_time": "2020-01-10",
            "purchase_month": "2020-01-31",
        },
        {
            **base,
            "manufacturer_code": "m2",
            "hospital_code": "h2",
            "drug_code": "d2",
            "drug_group": "d2",
            "purchase_time": "2020-09-10",
            "purchase_month": "2020-09-30",
        },
        {
            **base,
            "manufacturer_code": "m3",
            "hospital_code": "h3",
            "drug_code": "d3",
            "drug_group": "d3",
            "purchase_time": "2020-12-10",
            "purchase_month": "2020-12-31",
        },
    ]
    return pd.DataFrame(rows)


def test_one_shot_repeat_module_imports_and_labels_are_correct():
    from alg.tasks.die_prediction.one_shot_repeat import build_first_purchase_samples

    samples = build_first_purchase_samples(_events(), horizons=[3, 6, 12], data_purchase_time_max=pd.Timestamp("2021-01-31"))
    e1 = samples[samples["drug_group"].eq("d1")].iloc[0]
    e2 = samples[samples["drug_group"].eq("d2")].iloc[0]
    assert e1["label_repeat_H3"] == 1
    assert e1["label_repeat_H6"] == 1
    assert e2["label_repeat_H3"] == 0
    assert e2["label_repeat_H6"] == 0
    assert e2["label_repeat_H12"] == 1


def test_label_window_not_closed_is_excluded():
    from alg.tasks.die_prediction.one_shot_repeat import build_first_purchase_samples, closed_horizon_samples

    samples = build_first_purchase_samples(_events(), horizons=[3], data_purchase_time_max=pd.Timestamp("2020-12-31"))
    assert samples[samples["drug_group"].eq("d3")].iloc[0]["label_window_closed_H3"] is False or not samples[samples["drug_group"].eq("d3")].iloc[0]["label_window_closed_H3"]
    closed = closed_horizon_samples(samples, 3)
    assert "d3" not in set(closed["drug_group"])


def test_attention_scores_and_probability_range():
    from alg.tasks.die_prediction.one_shot_repeat import build_attention_scores

    df = pd.DataFrame({"repeat_probability_H6": [0.25], "one_shot_value_score": [100.0]})
    scored = build_attention_scores(df, horizon=6)
    assert np.isclose(scored.loc[0, "one_shot_non_repeat_risk_H6"], 0.75)
    assert np.isclose(scored.loc[0, "one_shot_retention_risk_score_H6"], 75.0)
    assert np.isclose(scored.loc[0, "one_shot_conversion_opportunity_score_H6"], 25.0)
    assert np.isclose(scored.loc[0, "one_shot_balanced_attention_score_H6"], 18.75)
    assert 0 <= scored.loc[0, "repeat_probability_H6"] <= 1


def test_group_prior_smoothing_runs():
    from alg.tasks.die_prediction.one_shot_repeat import smoothed_repeat_rate

    rate = smoothed_repeat_rate(group_positive=2, group_count=4, global_repeat_rate=0.25, prior_strength=20)
    assert 0 <= rate <= 1
    assert np.isclose(rate, (2 + 0.25 * 20) / (4 + 20))


def test_long_output_does_not_contain_recurring_churn_probability():
    from alg.tasks.die_prediction.one_shot_repeat import make_long_enriched_output

    part = pd.DataFrame(
        {
            "manufacturer_code": ["m1"],
            "hospital_code": ["h1"],
            "drug_group": ["d1"],
            "drug_group_source": ["drug_code"],
            "first_purchase_month": ["2020-01"],
            "horizon": ["H6"],
            "repeat_probability_H6": [0.4],
            "one_shot_non_repeat_risk_H6": [0.6],
            "one_shot_value_score": [100.0],
            "one_shot_retention_risk_score_H6": [60.0],
            "one_shot_conversion_opportunity_score_H6": [40.0],
            "one_shot_balanced_attention_score_H6": [24.0],
            "selected_attention_score": [24.0],
            "selected_attention_policy": ["balanced_attention_score"],
        }
    )
    out = make_long_enriched_output([part])
    assert "churn_probability_H" not in out.columns
    assert out.loc[0, "probability_interpretation"] != "recurring_churn_probability"


def test_one_shot_repeat_script_dry_run_and_no_model_files(tmp_path):
    root = Path(__file__).resolve().parents[1]
    before = set(tmp_path.rglob("*.joblib")) | set(tmp_path.rglob("*.pkl")) | set(tmp_path.rglob("*.skops")) | set(tmp_path.rglob("*.cbm")) | set(tmp_path.rglob("*.onnx")) | set(tmp_path.rglob("*.zip"))
    subprocess.run(
        [
            sys.executable,
            "scripts/run_alive_prediction_one_shot_repeat_v1.py",
            "--dry-run",
            "--output-dir",
            str(tmp_path),
        ],
        cwd=root,
        check=True,
    )
    enriched = pd.read_csv(tmp_path / "one_shot_attention_candidates_enriched.csv")
    assert not enriched.empty
    assert "churn_probability_H" not in enriched.columns
    assert set(enriched["horizon"]) == {"H3", "H6", "H12"}
    after = set(tmp_path.rglob("*.joblib")) | set(tmp_path.rglob("*.pkl")) | set(tmp_path.rglob("*.skops")) | set(tmp_path.rglob("*.cbm")) | set(tmp_path.rglob("*.onnx")) | set(tmp_path.rglob("*.zip"))
    assert after == before
