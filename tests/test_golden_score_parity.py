from __future__ import annotations

from pathlib import Path

import pandas as pd


REPORT_DIR = Path("algo_main/reports/entity_complete_v2_coverage_expansion/18_best_model_runtime_alignment")
GOLDEN_DIR = Path("algo_main/data/entity_complete_v2_coverage_expansion/12_best_model_runtime_alignment/golden_reference")


def test_golden_score_parity_matches_reference_predictions() -> None:
    parity = pd.read_csv(REPORT_DIR / "golden_score_parity.csv")
    row = parity.iloc[0]
    assert str(row["status"]).startswith("pass")
    assert float(row["score_max_abs_diff"]) == 0.0
    assert float(row["score_mean_abs_diff"]) == 0.0
    assert float(row["score_corr"]) == 1.0


def test_golden_feature_and_result_parity_blockers_are_explicit() -> None:
    feature = pd.read_csv(REPORT_DIR / "golden_feature_parity.csv")
    result = pd.read_csv(REPORT_DIR / "golden_result_batch_parity.csv")
    assert feature.iloc[0]["status"] in {"blocked", "pass"}
    assert result.iloc[0]["status"] in {"blocked", "pass"}
    assert (GOLDEN_DIR / "golden_raw_input_blocker.md").exists()
