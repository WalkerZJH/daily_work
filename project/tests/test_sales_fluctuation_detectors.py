from __future__ import annotations

from datetime import date

import pandas as pd

from app.detectors.order_level import run_order_level_detectors


def test_purchase_qty_spike_outputs_sales_fluctuation_evidence() -> None:
    orders = pd.DataFrame(
        [
            _row("B1", "2026-05-01", 1),
            _row("B2", "2026-05-10", 1),
            _row("R1", "2026-06-20", 20),
        ]
    )

    evidence_by_unit = run_order_level_detectors(
        orders,
        as_of_date=date(2026, 6, 24),
        enabled_detectors=["purchase_qty_spike"],
        recent_days=14,
        fluctuation_ratio_threshold=1.8,
    )

    evidence = evidence_by_unit["ORG_A|product_line|PL_A"][0]
    assert evidence.category == "sales_fluctuation"
    assert evidence.detector_id == "purchase_qty_spike"
    assert evidence.hit is True
    assert evidence.statistics["ratio"] >= 1.8


def test_purchase_freq_drop_outputs_sales_fluctuation_evidence() -> None:
    orders = pd.DataFrame(
        [
            _row("B1", "2026-05-01", 1),
            _row("B2", "2026-05-02", 1),
            _row("B3", "2026-05-03", 1),
        ]
    )

    evidence_by_unit = run_order_level_detectors(
        orders,
        as_of_date=date(2026, 6, 24),
        enabled_detectors=["purchase_freq_drop"],
        recent_days=14,
        fluctuation_ratio_threshold=1.8,
    )

    evidence = evidence_by_unit["ORG_A|product_line|PL_A"][0]
    assert evidence.category == "sales_fluctuation"
    assert evidence.detector_id == "purchase_freq_drop"
    assert evidence.hit is True


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
        "comparable_unit_price": 10,
    }
