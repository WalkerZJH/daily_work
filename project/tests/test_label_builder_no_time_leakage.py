from __future__ import annotations

from datetime import date

import pandas as pd

from app.features.unit_snapshot_builder import UnitSnapshotBuilder
from app.features.label_builder import build_churn_label


def test_origin_future_orders_only_affect_label_not_features() -> None:
    orders = pd.DataFrame(
        [
            _row("O1", "2026-01-01", 10),
            _row("O2", "2026-02-01", 20),
        ]
    )
    origin = date(2026, 1, 15)
    units = pd.DataFrame([{"org_code": "ORG_A", "product_line_code": "PL_A"}])

    features = UnitSnapshotBuilder().build_for_units(orders, units, origin)
    label, debug = build_churn_label(
        orders,
        org_code="ORG_A",
        product_line_code="PL_A",
        origin_date=origin,
        horizon_days=90,
        max_data_date=date(2026, 5, 1),
    )

    assert features.loc[0, "purchase_count_90d"] == 1
    assert features.loc[0, "qty_90d"] == 10
    assert label == 0
    assert debug["future_purchase_count"] == 1


def _row(order_id: str, order_time: str, qty: float) -> dict:
    return {
        "order_id": order_id,
        "org_code": "ORG_A",
        "product_line_code": "PL_A",
        "drug_code": "D1",
        "order_time": order_time,
        "purchase_qty": qty,
        "purchase_amount": qty * 10,
        "purchase_price": 10,
        "void_qty": 0,
    }
