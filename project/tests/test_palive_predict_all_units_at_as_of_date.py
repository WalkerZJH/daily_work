from __future__ import annotations

from datetime import date

import pandas as pd

from app.core.config import load_config
from app.schemas.backbone import BackbonePredictRequest
from app.services.backbone_service import BackboneService


def test_palive_predict_all_units_at_as_of_date_with_history_start() -> None:
    service = BackboneService(load_config())
    orders = pd.DataFrame(
        [
            _row("O1", "ORG_A", "PL_A", "2026-01-01"),
            _row("O2", "ORG_A", "PL_A", "2026-06-01"),
            _row("O3", "ORG_B", "PL_B", "2026-06-10"),
            _row("OLD", "ORG_OLD", "PL_OLD", "2025-01-01"),
        ]
    )
    request = BackbonePredictRequest(
        source_type="csv",
        dataset_name="sample",
        as_of_date=date(2026, 6, 24),
        history_start_date=date(2026, 1, 1),
    )
    orders["order_time"] = pd.to_datetime(orders["order_time"], errors="coerce")
    scoped = orders[orders["order_time"].dt.date >= request.history_start_date]

    predictions = service.predict_on_orders(scoped, request.as_of_date)

    unit_ids = {item.analysis_unit_id for item in predictions}
    assert "ORG_A|product_line|PL_A" in unit_ids
    assert "ORG_B|product_line|PL_B" in unit_ids
    assert "ORG_OLD|product_line|PL_OLD" not in unit_ids
    assert all(item.as_of_date == date(2026, 6, 24) for item in predictions)
    assert all(item.days_since_last_purchase is not None for item in predictions)
    assert any("FALLBACK_INTERVAL_PROXY_USED" in item.warnings for item in predictions)


def _row(order_id: str, org_code: str, product_line_code: str, order_time: str) -> dict:
    return {
        "order_id": order_id,
        "org_code": org_code,
        "org_name": org_code,
        "product_line_code": product_line_code,
        "product_line_name": product_line_code,
        "drug_code": product_line_code,
        "order_time": order_time,
        "purchase_qty": 1,
        "void_qty": 0,
        "purchase_amount": 10,
        "purchase_price": 10,
        "comparable_unit_price": 10,
    }
