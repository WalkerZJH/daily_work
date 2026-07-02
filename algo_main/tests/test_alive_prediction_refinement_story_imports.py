from __future__ import annotations

from pathlib import Path
import sys


def test_refinement_story_helpers_import_and_handle_missing_files(tmp_path):
    root = Path(__file__).resolve().parents[1]
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

    from alg.evaluation import alive_prediction_refinement_story as story

    assert story.load_csv_if_exists(tmp_path / "missing.csv") is None
    assert story.read_md_head(tmp_path / "missing.md").startswith("[missing]")

    overview = story.stage_overview(tmp_path)
    assert {"stage", "available_files", "expected_files", "missing_files"}.issubset(overview.columns)
    assert int(overview["available_files"].sum()) == 0

    missing = story.missing_files_report(tmp_path)
    assert {"group", "path", "exists", "file_size"}.issubset(missing.columns)

    m1 = story.m1_summary(tmp_path)
    assert {"counts", "selected_horizons", "primary_horizon", "selection_reason", "audit"}.issubset(m1.keys())

    corr = story.correction_summary(tmp_path)
    assert "counts" in corr

    assert story.bool_all_false(None, "auto_dispatch_allowed") is None
    assert "stage_closed_without_llm" in story.final_boundary_table()["item"].tolist()


def test_refinement_story_helpers_do_not_read_parquet_or_call_llm():
    root = Path(__file__).resolve().parents[1]
    helper = root / "src/alg/evaluation/alive_prediction_refinement_story.py"
    source = helper.read_text(encoding="utf-8")

    assert "read_parquet" not in source
    assert "OpenAI" not in source
    assert "chat.completions" not in source
    assert "responses.create" not in source
