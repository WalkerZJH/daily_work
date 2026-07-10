from __future__ import annotations

from risk_algorithm_core.result_assembler import _build_detector_tables_for_dates
from tests.test_daily_detector_contract_utils import build_detector_fixture


def test_result_assembler_materializes_configured_daily_detector_run_dates() -> None:
    fixture = build_detector_fixture()
    tables = _build_detector_tables_for_dates(
        risk_entities=fixture["risk_entities"],
        scan_features=fixture["scan_features"],
        report_month="2025-11",
        run_dates=["2025-12-01", "2025-12-02"],
        source_raw_batch_id="raw",
        source_result_batch_id="batch",
    )

    assert set(tables["daily_detector_runs"]["run_date"].astype(str)) == {"2025-12-01", "2025-12-02"}
    assert set(tables["daily_detector_clues"]["run_date"].astype(str)) == {"2025-12-01", "2025-12-02"}
    assert "采购" in str(tables["daily_detector_clues"].iloc[0]["root_cause_label"])
