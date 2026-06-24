from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd


def effective_purchase_mask(orders: pd.DataFrame) -> pd.Series:
    qty = pd.to_numeric(orders.get("purchase_qty", pd.Series(index=orders.index)), errors="coerce")
    if "void_qty" in orders.columns:
        void_qty = pd.to_numeric(orders["void_qty"], errors="coerce").fillna(0)
    else:
        void_qty = pd.Series(0, index=orders.index)
    return (qty > 0) & (void_qty == 0)


def filter_effective_purchases(orders: pd.DataFrame) -> pd.DataFrame:
    if orders.empty:
        return orders.copy()
    return orders[effective_purchase_mask(orders)].copy()


def build_churn_label(
    orders: pd.DataFrame,
    *,
    org_code: str,
    product_line_code: str,
    origin_date: date,
    horizon_days: int,
    max_data_date: date | None = None,
) -> tuple[int | None, dict[str, Any]]:
    if max_data_date is not None and (pd.Timestamp(origin_date) + pd.Timedelta(days=horizon_days)).date() > max_data_date:
        return None, {"label_status": "label_unknown", "reason": "FUTURE_WINDOW_INCOMPLETE"}

    scoped = filter_effective_purchases(orders)
    scoped["order_time"] = pd.to_datetime(scoped["order_time"], errors="coerce")
    scoped = scoped[
        (scoped["org_code"].astype(str) == str(org_code))
        & (scoped["product_line_code"].astype(str) == str(product_line_code))
    ]
    start = pd.Timestamp(origin_date)
    end = start + pd.Timedelta(days=horizon_days)
    future = scoped[(scoped["order_time"] > start) & (scoped["order_time"] <= end)]
    label = 0 if len(future) > 0 else 1
    return label, {
        "label_status": "known",
        "future_purchase_count": int(len(future)),
        "horizon_days": horizon_days,
        "future_window_start": start.date().isoformat(),
        "future_window_end": end.date().isoformat(),
    }
