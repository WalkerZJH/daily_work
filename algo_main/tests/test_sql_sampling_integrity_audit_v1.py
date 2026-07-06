from __future__ import annotations

from pathlib import Path

import pandas as pd

from alg.tasks.die_prediction import sql_sampling_integrity_audit as module
from alg.tasks.die_prediction.sql_sampling_integrity_audit import (
    add_entity_key,
    compare_monthly_distribution,
    compute_history_completeness,
    local_monthly_distribution,
    mask_database_url,
    run_sql_sampling_integrity_audit,
)


def test_module_imports() -> None:
    assert "sql_sampling_integrity_summary.md" in module.OUTPUT_FILES


def test_entity_key_construction_correct() -> None:
    df = pd.DataFrame(
        {
            "manufacturer_code": ["m1"],
            "hospital_code": ["h1"],
            "drug_code": ["d1"],
        }
    )

    keyed = add_entity_key(df)

    assert keyed["entity_key"].iloc[0] == "m1|h1|d1"


def test_local_vs_sql_coverage_ratio_and_history_flag_correct() -> None:
    sampled = pd.DataFrame(
        {
            "manufacturer_code": ["m1", "m2"],
            "hospital_code": ["h1", "h2"],
            "drug_code": ["d1", "d2"],
            "sample_reason": ["unit", "unit"],
        }
    )
    local_agg = pd.DataFrame(
        {
            "manufacturer_code": ["m1", "m2"],
            "hospital_code": ["h1", "h2"],
            "drug_code": ["d1", "d2"],
            "local_order_count_total": [10, 5],
            "local_first_purchase_time": [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-06-01")],
            "local_last_purchase_time": [pd.Timestamp("2024-12-01"), pd.Timestamp("2024-12-01")],
            "local_active_month_count": [10, 5],
            "local_months_observed": [12, 7],
        }
    )
    sql_agg = pd.DataFrame(
        {
            "manufacturer_code": ["m1", "m2"],
            "hospital_code": ["h1", "h2"],
            "drug_code": ["d1", "d2"],
            "sql_order_count_total": [10, 10],
            "sql_first_purchase_time": [pd.Timestamp("2024-01-03"), pd.Timestamp("2024-01-01")],
            "sql_last_purchase_time": [pd.Timestamp("2024-12-02"), pd.Timestamp("2024-12-01")],
            "sql_active_month_count": [10, 10],
        }
    )

    audit = compute_history_completeness(local_agg, sql_agg, sampled)

    assert audit.loc[0, "order_count_coverage_ratio"] == 1.0
    assert audit.loc[0, "history_complete_flag"] is True
    assert audit.loc[1, "order_count_coverage_ratio"] == 0.5
    assert audit.loc[1, "history_complete_flag"] is False


def test_monthly_distribution_comparison_runs() -> None:
    local = pd.DataFrame(
        {
            "manufacturer_code": ["m1", "m1"],
            "hospital_code": ["h1", "h1"],
            "drug_code": ["d1", "d1"],
            "purchase_time": [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-02-01")],
        }
    )
    local_months = local_monthly_distribution(local)
    sql_months = pd.DataFrame(
        {
            "purchase_month": ["2024-01", "2024-02"],
            "sql_row_count": [10, 10],
            "sql_entity_count": [2, 2],
        }
    )

    compared = compare_monthly_distribution(local_months, sql_months)

    assert {"local_row_share", "sql_row_share", "row_share_delta"}.issubset(compared.columns)
    assert len(compared) == 2


def test_sql_unavailable_does_not_crash(tmp_path: Path) -> None:
    output_dir = tmp_path / "reports"

    outputs = run_sql_sampling_integrity_audit(tmp_path, output_dir, skip_sql=True)

    assert outputs["result"].sql_connected is False
    assert (output_dir / "sql_connection_audit.md").exists()
    assert (output_dir / "sql_sampling_integrity_summary.md").exists()
    assert (output_dir / "next_data_action_decision.md").exists()


def test_password_is_not_printed_in_masked_url() -> None:
    masked = mask_database_url("mssql+pyodbc://user:dummy-value@example/db")

    assert "dummy-value" not in masked
    assert "***" in masked


def test_run_does_not_modify_input_files(tmp_path: Path) -> None:
    fact_dir = tmp_path / "data/04_facts/alive_prediction"
    fact_dir.mkdir(parents=True)
    fact_path = fact_dir / "fact_purchase_event__drug_code.parquet"
    df = pd.DataFrame(
        {
            "manufacturer_code": ["m1", "m1"],
            "hospital_code": ["h1", "h1"],
            "drug_code": ["d1", "d1"],
            "purchase_time": [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-02-01")],
            "purchase_month": [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-02-01")],
        }
    )
    df.to_parquet(fact_path, index=False)
    before = fact_path.read_bytes()

    outputs = run_sql_sampling_integrity_audit(tmp_path, tmp_path / "out", skip_sql=True)

    assert outputs["result"].local_row_count == 2
    assert before == fact_path.read_bytes()
