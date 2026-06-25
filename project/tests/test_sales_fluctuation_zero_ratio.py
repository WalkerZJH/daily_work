from __future__ import annotations

from datetime import date

import pandas as pd

from app.core.config import load_config
from app.detectors.registry import DETECTOR_META
from app.schemas.api import DetectorRunRequest
from app.services.detector_run_service import DetectorRunService


def test_quantity_drop_from_nonzero_to_zero_hits_drop() -> None:
    result = _run_qty([_row("P1", "2026-05-10", 971)])[0]

    assert result.hit is True
    assert result.reason_code == "SALES_QTY_DROP"
    assert result.metrics["drop_rate"] == 1.0
    assert "下降比例" in result.narrative


def test_quantity_zero_to_zero_does_not_hit() -> None:
    result = _run_qty([_row("O1", "2026-04-01", 100)])[0]

    assert result.hit is False
    assert result.reason_code == "SALES_QTY_NO_ACTIVITY_BOTH_WINDOWS"


def test_quantity_from_zero_baseline_is_low_confidence_spike() -> None:
    result = _run_qty([_row("C1", "2026-06-10", 100)])[0]

    assert result.hit is True
    assert result.reason_code == "SALES_QTY_FROM_ZERO_BASELINE"
    assert result.confidence < 0.5
    assert "无法计算稳定倍数" in result.narrative


def test_quantity_same_windows_does_not_hit() -> None:
    result = _run_qty([_row("P1", "2026-05-10", 100), _row("C1", "2026-06-10", 100)])[0]

    assert result.hit is False
    assert result.reason_code == "SALES_QTY_STABLE"
    assert "变化比例为 0.0" not in result.narrative


def _run_qty(rows: list[dict]):
    frame = pd.DataFrame(rows)
    frame["order_time"] = pd.to_datetime(frame["order_time"], errors="coerce")
    request = DetectorRunRequest(
        source_type="csv",
        dataset_name="sample",
        as_of_date=date(2026, 6, 24),
        lookback_days=30,
        enabled_detectors=["purchase_quantity_fluctuation_warning"],
    )
    return DetectorRunService(load_config())._run_one(
        DETECTOR_META["purchase_quantity_fluctuation_warning"],
        frame,
        request,
    )


def _row(order_id: str, order_time: str, qty: float) -> dict:
    return {
        "order_id": order_id,
        "org_code": "ORG_A",
        "product_line_code": "PL_A",
        "order_time": order_time,
        "purchase_qty": qty,
        "purchase_amount": qty * 10,
    }
