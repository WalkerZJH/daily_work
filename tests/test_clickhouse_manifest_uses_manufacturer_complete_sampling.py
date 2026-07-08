from __future__ import annotations

from pathlib import Path

from risk_algorithm_core.raw_input import _clickhouse_query_for_table, load_raw_manifest


def test_clickhouse_manifest_uses_manufacturer_complete_sampling() -> None:
    manifest = load_raw_manifest(Path("configs/risk_algorithm_core/clickhouse_raw_input_batch"))
    raw = manifest.raw
    orders_query = _clickhouse_query_for_table(manifest, "orders")

    assert raw.get("sampling_strategy") == "manufacturer_complete_time_window"
    assert raw.get("row_limit") in {None, 0, "0", ""}
    assert "manufacturer_code IN" in orders_query
    assert "{limit_clause}" not in orders_query
    assert "LIMIT 5000" not in orders_query
