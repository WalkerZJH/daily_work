from __future__ import annotations

from datetime import date

import pandas as pd

from app.algorithms.baseline import as_of_day_bounds
from app.schemas.algorithm import DemandShapeResult
from app.schemas.config import DemandShapeConfig


def calculate_demand_shape(
    unit_orders: pd.DataFrame,
    as_of_date: date,
    config: DemandShapeConfig,
    lookback_days: int = 365,
) -> DemandShapeResult:
    if unit_orders.empty:
        return DemandShapeResult(
            demand_shape="unknown",
            adi=None,
            cv2=None,
            confidence=0.0,
            reason_code="NO_HISTORY",
            warnings=["No historical orders for this analysis unit."],
        )

    as_of_start, as_of_end = as_of_day_bounds(as_of_date)
    lookback_start = as_of_start - pd.Timedelta(days=lookback_days)

    orders = unit_orders.copy()
    orders["order_time"] = pd.to_datetime(orders["order_time"], errors="coerce")
    orders["purchase_qty"] = pd.to_numeric(orders["purchase_qty"], errors="coerce").fillna(0)
    orders = orders[
        (orders["order_time"].notna())
        & (orders["order_time"] > lookback_start)
        & (orders["order_time"] <= as_of_end)
    ]

    if orders.empty:
        return DemandShapeResult(
            demand_shape="unknown",
            adi=None,
            cv2=None,
            confidence=0.0,
            reason_code="NO_LOOKBACK_ORDERS",
            warnings=["No orders in demand-shape lookback window."],
        )

    monthly = orders.set_index("order_time")["purchase_qty"].resample("MS").sum().sort_index()
    month_index = pd.date_range(
        start=lookback_start.to_period("M").to_timestamp(),
        end=as_of_start.to_period("M").to_timestamp(),
        freq="MS",
    )
    monthly = monthly.reindex(month_index, fill_value=0)
    nonzero = monthly[monthly > 0]

    if len(nonzero) < config.min_nonzero_periods:
        return DemandShapeResult(
            demand_shape="unknown",
            adi=None,
            cv2=None,
            confidence=0.2,
            reason_code="INSUFFICIENT_NONZERO_PERIODS",
            warnings=["Too few non-zero demand periods for stable classification."],
        )

    adi = float(len(monthly) / len(nonzero))
    mean_qty = float(nonzero.mean())
    cv2 = 0.0 if mean_qty == 0 else float((nonzero.std(ddof=0) / mean_qty) ** 2)

    if adi < config.adi_threshold and cv2 < config.cv2_threshold:
        demand_shape = "smooth"
    elif adi < config.adi_threshold and cv2 >= config.cv2_threshold:
        demand_shape = "erratic"
    elif adi >= config.adi_threshold and cv2 < config.cv2_threshold:
        demand_shape = "intermittent"
    else:
        demand_shape = "lumpy"

    confidence = min(1.0, 0.45 + len(nonzero) / 12)
    return DemandShapeResult(
        demand_shape=demand_shape,
        adi=adi,
        cv2=cv2,
        confidence=float(confidence),
        reason_code="CLASSIFIED",
        warnings=[],
    )
