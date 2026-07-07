from __future__ import annotations

from risk_algorithm_core.normalization import normalize_raw_tables
from risk_algorithm_core.raw_input import read_raw_input_batch
from tests.risk_algorithm_core_test_utils import RAW_FIXTURE, SCHEMA_MAPPING


def test_normalization_standardizes_orders() -> None:
    batch = read_raw_input_batch(RAW_FIXTURE, SCHEMA_MAPPING)
    normalized, report = normalize_raw_tables(batch.tables, "2026-07-31")
    orders = normalized["orders"]
    assert not orders.empty
    assert orders["order_date"].max().strftime("%Y-%m-%d") <= "2026-07-31"
    assert (orders["order_quantity"] > 0).all()
    assert report.loc[report["metric"].eq("normalized_order_rows"), "value"].iloc[0] == len(orders)
