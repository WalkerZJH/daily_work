from __future__ import annotations

import json

import pandas as pd

from risk_algorithm_core.clickhouse_result_writer import write_dataframe_to_clickhouse_or_fallback


def test_clickhouse_write_falls_back_to_csv_when_write_permission_fails(tmp_path) -> None:
    class DeniedClient:
        def write_dataframe(self, table_name: str, frame: pd.DataFrame) -> None:
            raise PermissionError("read-only user")

    status = write_dataframe_to_clickhouse_or_fallback(
        pd.DataFrame([{"id": "row-1", "value": 1}]),
        table_name="risk_algorithm_core_write_probe",
        fallback_dir=tmp_path,
        client=DeniedClient(),
    )

    assert status["write_status"] == "fallback_csv"
    assert status["clickhouse_table"] == "risk_algorithm_core_write_probe"
    assert (tmp_path / "risk_algorithm_core_write_probe.csv").exists()
    assert json.loads((tmp_path / "risk_algorithm_core_write_probe_write_status.json").read_text(encoding="utf-8"))["write_status"] == "fallback_csv"
