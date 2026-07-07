from __future__ import annotations

from risk_algorithm_core.raw_input import ClickHouseRawTableReader, SqlRawTableReader, read_raw_input_batch
from tests.risk_algorithm_core_test_utils import RAW_FIXTURE, SCHEMA_MAPPING


def test_raw_input_batch_reads_local_csv_tables() -> None:
    batch = read_raw_input_batch(RAW_FIXTURE, SCHEMA_MAPPING)
    assert batch.manifest.raw_batch_id == "raw_fixture_monthly_v1"
    assert len(batch.tables["orders"]) >= 1
    assert "order_date" in batch.tables["orders"].columns


def test_sql_and_clickhouse_reader_interfaces_are_reserved() -> None:
    assert SqlRawTableReader is not None
    assert ClickHouseRawTableReader is not None
