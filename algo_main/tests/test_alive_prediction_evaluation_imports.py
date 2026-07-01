from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd


def test_alive_prediction_story_helpers_import_and_handle_missing_files(tmp_path):
    root = Path(__file__).resolve().parents[1]
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

    from alg.evaluation import alive_prediction_story as story

    assert story.load_csv_if_exists(tmp_path / "missing.csv") is None
    assert story.read_md_head(tmp_path / "missing.md").startswith("[missing]")

    stage = story.build_stage_summary_table(tmp_path)
    assert {"stage", "available_files", "expected_files", "missing_files"}.issubset(stage.columns)
    assert int(stage["available_files"].sum()) == 0

    final = story.build_final_decision_table(tmp_path)
    assert "probability_candidate_v1" in final["decision_item"].tolist()

    fig = story.plot_model_probability_metrics(pd.DataFrame())
    assert fig is not None

