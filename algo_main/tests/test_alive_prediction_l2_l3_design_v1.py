from __future__ import annotations

from pathlib import Path

import pandas as pd

from alg.tasks.die_prediction.l2_l3_design import (
    build_detector_eligibility_matrix,
    build_fdr_design_matrix,
    corroboration_level,
    effective_signal_families,
    fdr_group_key,
    write_l2_l3_design,
)


def test_l2_l3_design_import_and_matrix_generation() -> None:
    matrix = build_detector_eligibility_matrix()

    assert not matrix.empty
    assert "purchase_frequency_decay_rate_test" in set(matrix["detector_name"])
    assert "purchase_interval_overdue_warning" in set(matrix["detector_name"])


def test_d002_is_fdr_eligible() -> None:
    matrix = build_detector_eligibility_matrix()
    row = matrix.loc[matrix["detector_name"] == "purchase_frequency_decay_rate_test"].iloc[0]

    assert bool(row["has_p_value"])
    assert bool(row["fdr_eligible"])
    assert row["detector_type"] == "statistical_test"


def test_d001_is_corroboration_not_fdr() -> None:
    matrix = build_detector_eligibility_matrix()
    row = matrix.loc[matrix["detector_name"] == "purchase_interval_overdue_warning"].iloc[0]

    assert not bool(row["fdr_eligible"])
    assert row["corroboration_eligible"] == "true"
    assert row["effective_signal_family"] == "terminal_dynamic"


def test_interface_only_detector_not_effective_signal() -> None:
    evidence = pd.DataFrame(
        [
            {
                "detector_name": "low_price_purchase_warning",
                "hit_flag": True,
                "data_quality_status": "evaluated",
            }
        ]
    )

    assert effective_signal_families(evidence) == set()


def test_fdr_scope_key_rule() -> None:
    assert (
        fdr_group_key("2024-01", "H6", "purchase_frequency_decay_rate_test")
        == "2024-01|H6|purchase_frequency_decay_rate_test"
    )
    assert (
        fdr_group_key("2024-01", 6, "purchase_frequency_decay_rate_test")
        == "2024-01|H6|purchase_frequency_decay_rate_test"
    )


def test_fdr_design_matrix_only_d002_applicable() -> None:
    fdr = build_fdr_design_matrix(build_detector_eligibility_matrix())
    applicable = fdr.loc[fdr["fdr_scope"] != "not_applicable", "detector_name"].tolist()

    assert applicable == ["purchase_frequency_decay_rate_test"]


def test_corroboration_level_rules_on_mock_data() -> None:
    multi = pd.DataFrame(
        [
            {
                "detector_name": "purchase_interval_overdue_warning",
                "hit_flag": True,
                "data_quality_status": "evaluated",
            },
            {
                "detector_name": "purchase_frequency_decay_rate_test",
                "hit_flag": True,
                "data_quality_status": "evaluated",
            },
        ]
    )
    stat_only = pd.DataFrame(
        [
            {
                "detector_name": "purchase_frequency_decay_rate_test",
                "hit_flag": True,
                "data_quality_status": "evaluated",
            }
        ]
    )

    assert corroboration_level(multi) == "multi_signal"
    assert corroboration_level(stat_only) == "provisional_fdr_ready"
    assert corroboration_level(multi, l2_guardrail="peer_suppressed") == "suppressed_by_l2"


def test_write_design_outputs_and_missing_inputs_do_not_crash(tmp_path: Path) -> None:
    result = write_l2_l3_design(tmp_path, output_dir=tmp_path / "out")

    assert (tmp_path / "out/l2_l3_design_summary.md").exists()
    assert (tmp_path / "out/l2_l3_open_questions.md").exists()
    assert (tmp_path / "out/l2_l3_implementation_prompt_draft.md").exists()
    assert result["fdr_eligible"] == ["purchase_frequency_decay_rate_test"]


def test_write_design_does_not_modify_existing_input(tmp_path: Path) -> None:
    input_dir = tmp_path / "reports/alive_prediction_status_decision_v1"
    input_dir.mkdir(parents=True)
    input_file = input_dir / "candidate_status_decision.csv"
    input_file.write_text("candidate_id\nc1\n", encoding="utf-8")
    before = input_file.read_text(encoding="utf-8")

    write_l2_l3_design(tmp_path, output_dir=tmp_path / "out")

    assert input_file.read_text(encoding="utf-8") == before
