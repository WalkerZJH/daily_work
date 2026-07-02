from __future__ import annotations

from pathlib import Path

import pandas as pd

from alg.tasks.die_prediction.detector_completion_design import (
    build_detector_gap_matrix,
    build_next_prompt_md,
    field_availability_rows,
    write_detector_completion_audit,
)


def test_detector_gap_matrix_generation_handles_missing_fields(tmp_path: Path) -> None:
    matrix = build_detector_gap_matrix(tmp_path, schema={"survival": {"overdue_ratio", "drug_group"}})

    assert not matrix.empty
    assert "field_availability" in matrix.columns
    assert "purchase_interval_overdue_warning" in set(matrix["detector_name"])


def test_field_availability_audit_marks_missing_fields() -> None:
    fields = field_availability_rows({"survival": {"overdue_ratio"}})
    row = fields.loc[fields["field"] == "purchase_price"].iloc[0]

    assert row["available"] is False or row["available"] == False
    assert row["availability_note"] == "missing_from_current_reports"


def test_sku_narrowing_requires_product_line_mapping_at_drug_code_grain(tmp_path: Path) -> None:
    schema = {"candidate": {"drug_group", "drug_code"}}
    matrix = build_detector_gap_matrix(tmp_path, schema=schema)
    row = matrix.loc[matrix["detector_name"] == "sku_narrowing_warning"].iloc[0]

    assert row["entity_grain_feasibility"] == "requires_product_line_mapping"
    assert row["implementation_priority"] == "design_first"
    assert row["recommended_action"] == "requires_product_line_mapping"


def test_delivery_detectors_are_skipped_by_user_decision(tmp_path: Path) -> None:
    matrix = build_detector_gap_matrix(tmp_path, schema={"candidate": set()})
    rows = matrix.loc[matrix["leader_design_category"] == "delivery_response"]

    assert set(rows["current_status"]) == {"skipped_by_user_decision"}
    assert set(rows["implementation_priority"]) == {"skip_current_stage"}


def test_price_detector_unreliable_is_interface_only(tmp_path: Path) -> None:
    matrix = build_detector_gap_matrix(tmp_path, schema={"candidate": {"purchase_price", "specification"}})
    row = matrix.loc[matrix["detector_name"] == "low_price_purchase_warning"].iloc[0]

    assert row["implementation_priority"] == "interface_only"
    assert "price" in row["data_reliability"]


def test_next_implementation_prompt_generation(tmp_path: Path) -> None:
    schema = {
        "survival": {
            "overdue_ratio",
            "median_purchase_interval_days_asof_cutoff",
            "order_count_last_3m_asof_cutoff",
            "order_count_last_12m_asof_cutoff",
        }
    }
    matrix = build_detector_gap_matrix(tmp_path, schema=schema)
    prompt = build_next_prompt_md(matrix)

    assert "purchase_interval_overdue_warning" in prompt
    assert "purchase_frequency_decay_rate_test" in prompt
    assert "Do not implement L2/L3" in prompt


def test_write_detector_completion_audit_outputs_reports(tmp_path: Path) -> None:
    reports = tmp_path / "reports/alive_prediction_detectors_v1"
    reports.mkdir(parents=True)
    pd.DataFrame(
        [
            {"detector_name": "terminal_loss_warning", "detector_status": "implemented"},
            {"detector_name": "low_price_purchase_warning", "detector_status": "interface_only"},
        ]
    ).to_csv(reports / "detector_family_summary.csv", index=False)
    survival = tmp_path / "reports/alive_prediction_survival_lite_v1"
    survival.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "overdue_ratio": 1.5,
                "median_purchase_interval_days_asof_cutoff": 30,
                "order_count_last_3m_asof_cutoff": 1,
                "order_count_last_12m_asof_cutoff": 6,
                "drug_group": "d1",
                "drug_group_source": "drug_code",
            }
        ]
    ).to_csv(survival / "survival_refinement_results.csv", index=False)

    result = write_detector_completion_audit(tmp_path)

    assert result["matrix_rows"] >= 11
    assert (tmp_path / "reports/alive_prediction_detector_completion_design_v1/detector_completion_summary.md").exists()
    assert (tmp_path / "reports/alive_prediction_detector_completion_design_v1/detector_next_implementation_prompt.md").exists()
