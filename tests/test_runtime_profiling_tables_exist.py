from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path("algo_main/data/entity_complete_v2_coverage_expansion/16_multi_month_formal_result_batches")


def test_runtime_profiling_tables_exist() -> None:
    for name in [
        "monthly_probability_runtime_profile.csv",
        "daily_detector_runtime_profile.csv",
        "end_to_end_runtime_profile.csv",
    ]:
        path = ROOT / name
        assert path.exists(), name
        assert not pd.read_csv(path).empty


def test_runtime_scaling_estimate_exists() -> None:
    csv_path = ROOT / "runtime_scaling_estimate.csv"
    md_path = Path("algo_main/reports/entity_complete_v2_coverage_expansion/27_multi_month_formal_batches/runtime_scaling_estimate.md")
    assert csv_path.exists()
    assert md_path.exists()
    estimate = pd.read_csv(csv_path)
    assert {"stage", "estimated_full_dataset_seconds_mid", "confidence_level"}.issubset(estimate.columns)

