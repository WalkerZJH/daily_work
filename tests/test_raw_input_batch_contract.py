from __future__ import annotations

import pandas as pd
import yaml

from risk_algorithm_core.raw_input import ClickHouseRawTableReader, RawInputManifest, SqlRawTableReader, read_raw_input_batch
from tests.risk_algorithm_core_test_utils import RAW_FIXTURE, SCHEMA_MAPPING


CLICKHOUSE_SCHEMA_MAPPING = "configs/risk_algorithm_core/schema_mapping.clickhouse_drug_purchase_orders.yaml"


def test_raw_input_batch_reads_local_csv_tables() -> None:
    batch = read_raw_input_batch(RAW_FIXTURE, SCHEMA_MAPPING)
    assert batch.manifest.raw_batch_id == "raw_fixture_monthly_v1"
    assert len(batch.tables["orders"]) >= 1
    assert "order_date" in batch.tables["orders"].columns


def test_sql_and_clickhouse_reader_interfaces_are_reserved() -> None:
    assert SqlRawTableReader is not None
    assert ClickHouseRawTableReader is not None


def test_clickhouse_reader_uses_manifest_query_and_limit_clause() -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.queries: list[str] = []

        def query_df(self, sql: str) -> pd.DataFrame:
            self.queries.append(sql)
            return pd.DataFrame(
                [
                    {
                        "order_date": "2025-12-01",
                        "manufacturer_code": "m1",
                        "hospital_code": "h1",
                        "drug_code": "d1",
                        "order_quantity": 1,
                        "order_amount": 10,
                    }
                ]
            )

    manifest = RawInputManifest(
        raw_batch_id="clickhouse-smoke",
        source_system="clickhouse",
        data_as_of_date="2025-12-31",
        table_format="clickhouse",
        table_paths={"orders": "drug_purchase_orders"},
        raw={
            "from_date": "2025-12-01",
            "to_date": "2025-12-31",
            "row_limit": 10,
            "table_queries": {
                "orders": "SELECT purchase_time AS order_date FROM {table} WHERE purchase_time >= toDateTime('{from_date}') {limit_clause}"
            },
        },
    )

    reader = ClickHouseRawTableReader(client=FakeClient())
    frame = reader.read(manifest, "orders")

    assert len(frame) == 1
    assert "LIMIT 10" in reader.client.queries[0]
    assert "drug_purchase_orders" in reader.client.queries[0]


def test_clickhouse_reader_returns_empty_for_unconfigured_optional_tables() -> None:
    class FakeClient:
        def query_df(self, sql: str) -> pd.DataFrame:
            raise AssertionError("unconfigured optional table should not query source table")

    manifest = RawInputManifest(
        raw_batch_id="clickhouse-smoke",
        source_system="clickhouse",
        data_as_of_date="2025-12-31",
        table_format="clickhouse",
        table_paths={"orders": "drug_purchase_orders"},
        raw={"source_table": "drug_purchase_orders"},
    )

    reader = ClickHouseRawTableReader(client=FakeClient())
    frame = reader.read(manifest, "fact_entity_month")

    assert frame.empty


def test_clickhouse_mapping_uses_province_as_business_region() -> None:
    with open(CLICKHOUSE_SCHEMA_MAPPING, encoding="utf-8") as file:
        mapping = yaml.safe_load(file)

    assert mapping["orders"]["columns"]["province_code"] == "region_code"
    assert mapping["orders"]["columns"]["province"] == "region_name"
    assert mapping["hospital_master"]["columns"]["province_code"] == "region_code"
    assert mapping["hospital_master"]["columns"]["province"] == "region_name"
    assert mapping["orders"]["columns"]["generic_name"] == "drug_name"
