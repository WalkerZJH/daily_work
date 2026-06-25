from __future__ import annotations

from datetime import date

import pandas as pd

from app.core.config import load_config
from app.services.backbone_service import BackboneService


def test_backbone_debug_features_collapsed_by_default() -> None:
    orders = _orders()
    service = BackboneService(load_config())

    collapsed = service.predict_on_orders(orders, date(2026, 6, 25), include_debug_features=False)[0]
    full = service.predict_on_orders(orders, date(2026, 6, 25), include_debug_features=True)[0]

    assert set(collapsed.debug_features).issubset(
        {"days_since_last_purchase", "purchase_count_90d", "purchase_count_365d", "median_interval_days", "demand_profile"}
    )
    assert len(full.debug_features) > len(collapsed.debug_features)


def test_backbone_prediction_count_equals_unique_unit_count() -> None:
    orders = _orders()
    predictions = BackboneService(load_config()).predict_on_orders(orders, date(2026, 6, 25))
    unit_ids = [item.analysis_unit_id for item in predictions]

    assert len(predictions) == len(set(unit_ids))
    assert len(predictions) == orders[["org_code", "product_line_code"]].drop_duplicates().shape[0]


def _orders() -> pd.DataFrame:
    frame = pd.DataFrame(
        [
            _row("O1", "ORG_A", "PL_A", "2026-01-01"),
            _row("O2", "ORG_A", "PL_A", "2026-06-01"),
            _row("O3", "ORG_B", "PL_B", "2026-06-10"),
        ]
    )
    frame["order_time"] = pd.to_datetime(frame["order_time"], errors="coerce")
    return frame


def _row(order_id: str, org_code: str, product_line_code: str, order_time: str) -> dict:
    return {
        "order_id": order_id,
        "org_code": org_code,
        "org_name": org_code,
        "product_line_code": product_line_code,
        "product_line_name": product_line_code,
        "drug_code": "D1",
        "order_time": order_time,
        "purchase_qty": 1,
        "void_qty": 0,
        "purchase_amount": 10,
        "purchase_price": 10,
        "comparable_unit_price": 10,
    }
