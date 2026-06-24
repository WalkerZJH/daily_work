from __future__ import annotations

from datetime import date

import pandas as pd

from app.detectors.order_level import run_order_level_detectors


def test_low_delivery_rate_uses_delivery_qty_divided_by_purchase_qty() -> None:
    evidence_by_unit = run_order_level_detectors(
        pd.DataFrame(
            [
                {
                    **_base_row("O1"),
                    "purchase_qty": 10,
                    "delivery_qty": 4,
                }
            ]
        ),
        as_of_date=date(2026, 6, 24),
        enabled_detectors=["low_delivery_rate"],
        recent_days=14,
        low_delivery_rate_threshold=0.8,
    )

    evidence = evidence_by_unit["ORG_A|product_line|PL_A"][0]
    assert evidence.hit is True
    assert evidence.statistics["delivery_rate"] == 0.4


def test_delivery_delay_marks_approximation_warning() -> None:
    evidence_by_unit = run_order_level_detectors(
        pd.DataFrame(
            [
                {
                    **_base_row("O1"),
                    "order_time": "2026-06-01",
                    "delivery_time": "2026-06-12",
                }
            ]
        ),
        as_of_date=date(2026, 6, 24),
        enabled_detectors=["delivery_delay"],
        recent_days=30,
    )

    evidence = evidence_by_unit["ORG_A|product_line|PL_A"][0]
    assert evidence.hit is True
    assert "DELIVERY_DELAY_USES_DELIVERY_TIME_MINUS_ORDER_TIME_APPROXIMATION" in evidence.warnings


def _base_row(order_id: str) -> dict:
    return {
        "order_id": order_id,
        "org_code": "ORG_A",
        "product_line_code": "PL_A",
        "drug_code": "D1",
        "order_time": "2026-06-20",
        "purchase_qty": 1,
        "purchase_amount": 10,
        "purchase_price": 10,
        "comparable_unit_price": 10,
    }

