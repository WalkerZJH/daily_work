from __future__ import annotations

from datetime import date

import pandas as pd

from app.algorithms.baseline import as_of_day_bounds
from app.algorithms.detectors.helpers import clamp, order_refs
from app.schemas.algorithm import DetectorResult
from app.schemas.config import IPIntervalConfig


def detect_ip_interval(
    unit_orders: pd.DataFrame,
    as_of_date: date,
    config: IPIntervalConfig,
) -> DetectorResult:
    _, as_of_end = as_of_day_bounds(as_of_date)
    orders = unit_orders.copy()
    orders["order_time"] = pd.to_datetime(orders.get("order_time"), errors="coerce")
    orders = orders[(orders["order_time"].notna()) & (orders["order_time"] <= as_of_end)]
    orders = orders.sort_values("order_time")

    warnings: list[str] = []
    total_orders = int(len(orders))
    if total_orders < config.min_orders:
        warnings.append("Insufficient order count for robust interval anomaly detection.")
        return DetectorResult(
            detector_name="ip_interval",
            hit=False,
            severity=0,
            confidence=min(0.25, total_orders / max(config.min_orders, 1)),
            reason_code="INSUFFICIENT_HISTORY",
            metrics={"order_count": total_orders, "min_orders": config.min_orders},
            evidence_refs=order_refs(orders.tail(3)),
            warnings=warnings,
        )

    event_times = orders["order_time"].reset_index(drop=True)
    intervals = event_times.diff().dt.total_seconds().dropna() / 86400
    intervals = intervals[intervals > 0]
    if intervals.empty:
        warnings.append("No positive purchase intervals found.")
        return DetectorResult(
            detector_name="ip_interval",
            hit=False,
            severity=0,
            confidence=0.2,
            reason_code="NO_POSITIVE_INTERVALS",
            metrics={"order_count": total_orders},
            evidence_refs=order_refs(orders.tail(3)),
            warnings=warnings,
        )

    median_interval = float(intervals.median())
    mad = float((intervals - median_interval).abs().median())
    scale = 1.4826 * mad if mad > 0 else max(1.0, median_interval * 0.25)
    last_order_time = pd.Timestamp(event_times.iloc[-1])
    inactive_days = float((as_of_end - last_order_time).total_seconds() / 86400)
    robust_z = max(0.0, (inactive_days - median_interval) / scale)
    hit = robust_z >= config.z_hit
    severity = 0.0
    if hit:
        severity = clamp(
            ((robust_z - config.z_hit) / max(config.z_full - config.z_hit, 1e-6)) * 100
        )
    confidence = min(1.0, 0.45 + total_orders / 20)

    return DetectorResult(
        detector_name="ip_interval",
        hit=hit,
        severity=severity,
        confidence=float(confidence),
        reason_code="INTERVAL_Z_HIT" if hit else "INTERVAL_WITHIN_RANGE",
        metrics={
            "inactive_days": inactive_days,
            "historical_interval_median_days": median_interval,
            "historical_interval_mad_days": mad,
            "robust_z": robust_z,
            "z_hit": config.z_hit,
            "z_full": config.z_full,
            "order_count": total_orders,
        },
        evidence_refs=order_refs(orders.tail(5)),
        warnings=warnings,
    )
