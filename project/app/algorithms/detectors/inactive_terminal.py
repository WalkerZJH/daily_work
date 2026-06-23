from __future__ import annotations

from datetime import date

import pandas as pd

from app.algorithms.baseline import as_of_day_bounds
from app.algorithms.detectors.helpers import clamp, order_refs
from app.schemas.algorithm import DetectorResult
from app.schemas.config import InactiveTerminalConfig


def detect_inactive_terminal(
    unit_orders: pd.DataFrame,
    as_of_date: date,
    config: InactiveTerminalConfig,
) -> DetectorResult:
    _, as_of_end = as_of_day_bounds(as_of_date)
    orders = unit_orders.copy()
    orders["order_time"] = pd.to_datetime(orders.get("order_time"), errors="coerce")
    orders = orders[(orders["order_time"].notna()) & (orders["order_time"] <= as_of_end)]
    orders = orders.sort_values("order_time")

    if orders.empty:
        return DetectorResult(
            detector_name="inactive_terminal",
            hit=False,
            severity=0,
            confidence=0,
            reason_code="NO_HISTORY",
            metrics={},
            evidence_refs=[],
            warnings=["No historical orders for this analysis unit."],
        )

    event_times = orders["order_time"].reset_index(drop=True)
    intervals = event_times.diff().dt.total_seconds().dropna() / 86400
    intervals = intervals[intervals > 0]
    expected_interval = float(intervals.median()) if not intervals.empty else 30.0
    last_order_time = pd.Timestamp(event_times.iloc[-1])
    inactive_days = float((as_of_end - last_order_time).total_seconds() / 86400)
    threshold = max(config.min_inactive_days, expected_interval * config.inactive_multiplier)
    hit = inactive_days >= threshold
    severity = 0.0
    if hit:
        severity = clamp(50 + (inactive_days - threshold) / max(threshold, 1e-6) * 50)
    confidence = min(1.0, 0.35 + len(intervals) / 10)
    warnings = [] if len(intervals) >= 2 else ["Limited interval history; confidence is reduced."]

    return DetectorResult(
        detector_name="inactive_terminal",
        hit=hit,
        severity=severity,
        confidence=float(confidence),
        reason_code="INACTIVE_TERMINAL" if hit else "ACTIVE_WITHIN_EXPECTED_INTERVAL",
        metrics={
            "inactive_days": inactive_days,
            "expected_interval_days": expected_interval,
            "inactive_threshold_days": threshold,
            "last_order_time": last_order_time.isoformat(),
            "order_count": int(len(orders)),
        },
        evidence_refs=order_refs(orders.tail(5)),
        warnings=warnings,
    )
