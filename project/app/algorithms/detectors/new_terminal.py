from __future__ import annotations

from datetime import date

import pandas as pd

from app.algorithms.baseline import as_of_day_bounds
from app.algorithms.detectors.helpers import order_refs
from app.schemas.algorithm import BaselineMetrics, DetectorResult
from app.schemas.config import NewTerminalConfig


def detect_new_terminal(
    unit_orders: pd.DataFrame,
    metrics: BaselineMetrics,
    as_of_date: date,
    config: NewTerminalConfig,
) -> DetectorResult:
    del config
    as_of_start, as_of_end = as_of_day_bounds(as_of_date)
    recent_start = as_of_start - pd.Timedelta(days=(as_of_start.date() - metrics.recent_start).days)

    orders = unit_orders.copy()
    orders["order_time"] = pd.to_datetime(orders.get("order_time"), errors="coerce")
    orders = orders[(orders["order_time"].notna()) & (orders["order_time"] <= as_of_end)]
    orders = orders.sort_values("order_time")
    recent_orders = orders[
        (orders["order_time"] > recent_start) & (orders["order_time"] <= as_of_end)
    ]
    prior_orders = orders[orders["order_time"] <= recent_start]
    first_order_time = (
        None if orders.empty else pd.Timestamp(orders["order_time"].min()).to_pydatetime()
    )

    hit = bool(not recent_orders.empty and prior_orders.empty)
    severity = 40.0 if hit else 0.0
    confidence = min(1.0, 0.55 + len(recent_orders) / 8) if hit else 0.4

    return DetectorResult(
        detector_name="new_terminal",
        hit=hit,
        severity=severity,
        confidence=float(confidence),
        reason_code="NEW_TERMINAL" if hit else "NOT_NEW_TERMINAL",
        metrics={
            "is_new_terminal": hit,
            "first_order_time": first_order_time.isoformat() if first_order_time else None,
            "baseline_orders": metrics.baseline_orders,
            "prior_orders": int(len(prior_orders)),
            "recent_orders": int(len(recent_orders)),
        },
        evidence_refs=order_refs(recent_orders.head(5)),
        warnings=[],
    )
