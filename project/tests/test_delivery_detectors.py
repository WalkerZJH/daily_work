from __future__ import annotations

from datetime import date

import pandas as pd

from app.core.config import load_config
from app.detectors.registry import DETECTOR_META
from app.services.detector_run_service import DetectorRunService


def test_low_delivery_rate_uses_delivery_qty_divided_by_purchase_qty() -> None:
    result = _run_on_orders(
        pd.DataFrame(
            [
                {
                    **_row(),
                    "purchase_qty": 10,
                    "delivery_qty": 4,
                }
            ]
        ),
        ["low_delivery_rate_warning"],
    ).detector_results[0]

    assert result.hit is True
    assert result.metrics["delivery_rate"] == 0.4


def test_low_delivery_rate_handles_zero_purchase_qty() -> None:
    result = _run_on_orders(
        pd.DataFrame([{**_row(), "purchase_qty": 0, "delivery_qty": 0}]),
        ["low_delivery_rate_warning"],
    ).detector_results[0]

    assert result.hit is False
    assert result.reason_code == "PURCHASE_QTY_NOT_POSITIVE"


def test_low_delivery_rate_missing_delivery_qty_returns_missing_fields() -> None:
    frame = pd.DataFrame([{key: value for key, value in _row().items() if key != "delivery_qty"}])

    result = _run_on_orders(frame, ["low_delivery_rate_warning"]).detector_results[0]

    assert result.reason_code == "MISSING_REQUIRED_FIELDS"
    assert "缺少字段：delivery_qty" in result.warnings


def _run_on_orders(frame: pd.DataFrame, detectors: list[str]):
    service = DetectorRunService(load_config())
    frame = frame.copy()
    if "order_time" in frame.columns:
        frame["order_time"] = pd.to_datetime(frame["order_time"], errors="coerce")
    class _Response:
        detector_results = []

    response = _Response()
    for detector_id in detectors:
        response.detector_results.extend(
            service._run_one(DETECTOR_META[detector_id], frame, _request())
        )
    return response


def _request():
    from app.schemas.api import DetectorRunRequest

    return DetectorRunRequest(
        source_type="csv",
        dataset_name="sample",
        as_of_date=date(2026, 6, 24),
        enabled_detectors=["low_delivery_rate_warning"],
    )


def _row() -> dict:
    return {
        "order_id": "O1",
        "order_time": "2026-06-20",
        "org_code": "ORG_A",
        "product_line_code": "PL_A",
        "purchase_qty": 1,
        "delivery_qty": 1,
        "purchase_price": 10,
        "purchase_amount": 10,
        "comparable_unit_price": 10,
    }
