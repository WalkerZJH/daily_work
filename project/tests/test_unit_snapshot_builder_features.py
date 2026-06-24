from __future__ import annotations

from datetime import date

import pandas as pd

from app.features.unit_snapshot_builder import UnitSnapshotBuilder


def test_unit_snapshot_builder_calculates_core_features() -> None:
    orders = pd.DataFrame(
        [
            _row("2026-01-01", 10),
            _row("2026-02-01", 20),
            _row("2026-03-01", 30),
        ]
    )

    snapshot = UnitSnapshotBuilder().build_current_snapshot(orders, date(2026, 3, 15)).iloc[0]

    assert snapshot["days_since_last_purchase"] == 14
    assert snapshot["purchase_count_90d"] == 3
    assert snapshot["median_interval_days"] == 29.5
    assert snapshot["last_interval_days"] == 28
    assert snapshot["qty_90d"] == 60


def _row(order_time: str, qty: float) -> dict:
    return {
        "order_id": order_time,
        "org_code": "ORG_A",
        "product_line_code": "PL_A",
        "drug_code": "D1",
        "spec": "10mg",
        "order_time": order_time,
        "purchase_qty": qty,
        "purchase_amount": qty * 10,
        "purchase_price": 10,
        "comparable_unit_price": 10,
        "delivery_qty": qty,
        "receipt_qty": qty,
    }
