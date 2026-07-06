from __future__ import annotations

from pathlib import Path

import pandas as pd

from alg.tasks.die_prediction import entity_complete_rebuild as rebuild
from alg.tasks.die_prediction import entity_complete_v2_coverage_expansion as module


def test_v2_module_imports() -> None:
    assert module.VERSION == "entity_complete_v2_coverage_expansion"
    assert "tier_medium" in module.TIER_CONFIGS


def test_redirected_rebuild_paths_do_not_overwrite_v1() -> None:
    original_data_root = rebuild.DATA_ROOT

    with module.redirected_rebuild_paths():
        assert str(rebuild.DATA_ROOT).replace("\\", "/").endswith("data/entity_complete_v2_coverage_expansion")
        assert str(rebuild.REPORT_ROOT).replace("\\", "/").endswith("reports/entity_complete_v2_coverage_expansion")

    assert rebuild.DATA_ROOT == original_data_root


def test_estimated_detail_rows_uses_selected_scope_counts() -> None:
    estimate = {
        "selected_manufacturers": pd.DataFrame({"sql_row_count": [10, 20]}),
        "selected_entities": pd.DataFrame({"sql_order_count_total": [3, 7]}),
        "selected_hospital_drug_pairs": pd.DataFrame({"all_pair_order_count": [5]}),
    }

    assert module.estimated_detail_rows(estimate) == 45


def test_sql_unavailable_plan_masks_password(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SQL_DATABASE_URL", "mssql+pymssql://user:secret@host:1433/db")

    module.write_sql_unavailable_plan(tmp_path, "failed mssql+pymssql://user:secret@host:1433/db; PWD=secret")

    text = (tmp_path / module.REPORT_ROOT / "01_extraction_design" / "sql_unavailable_coverage_expansion_plan.md").read_text(encoding="utf-8")
    assert "secret" not in text
    assert "***" in text


def test_multi_recall_union_top20_does_not_use_label() -> None:
    df = pd.DataFrame(
        {
            "probability_score": [0.9, 0.1, 0.2, 0.3, 0.4],
            "interval_overdue_baseline": [0.1, 0.9, 0.2, 0.3, 0.4],
            "frequency_decay_baseline": [0.1, 0.2, 0.9, 0.3, 0.4],
            "recency_only_baseline": [0.1, 0.2, 0.3, 0.9, 0.4],
            "label_die_H": [0, 0, 0, 0, 1],
        }
    )
    scored = module.consolidation.add_candidate_policy_scores(df.drop(columns=["label_die_H"]), "H3")

    selected = module.select_multi_recall_union(scored, 0.20)

    assert len(selected) >= 3
    assert 4 not in set(selected)


def test_v2_output_path_constant_is_separate_from_v1() -> None:
    assert "entity_complete_v1" not in str(module.DATA_ROOT)
    assert "entity_complete_v1" not in str(module.REPORT_ROOT)
