from __future__ import annotations

from datetime import date

import pandas as pd

from app.schemas.algorithm import BaselineMetrics


def as_of_day_bounds(as_of_date: date) -> tuple[pd.Timestamp, pd.Timestamp]:
    as_of_start = pd.Timestamp(as_of_date).normalize()
    as_of_end = as_of_start + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
    return as_of_start, as_of_end


def filter_unit_orders(
    orders: pd.DataFrame,
    org_code: str,
    product_line_code: str,
    as_of_date: date,
) -> pd.DataFrame:
    _, as_of_end = as_of_day_bounds(as_of_date)
    frame = orders.copy()
    frame["order_time"] = pd.to_datetime(frame["order_time"], errors="coerce")
    frame = frame[frame["order_time"].notna()]
    frame = frame[frame["order_time"] <= as_of_end]
    frame = frame[
        (frame["org_code"].astype(str) == str(org_code))
        & (frame["product_line_code"].astype(str) == str(product_line_code))
    ]
    return frame.sort_values("order_time").reset_index(drop=True)


def calculate_unit_baseline_metrics(
    unit_orders: pd.DataFrame,
    org_code: str,
    product_line_code: str,
    as_of_date: date,
    recent_days: int = 90,
    baseline_days: int = 365,
) -> BaselineMetrics:
    as_of_start, as_of_end = as_of_day_bounds(as_of_date)
    recent_start = as_of_start - pd.Timedelta(days=recent_days)
    baseline_start = recent_start - pd.Timedelta(days=baseline_days)
    baseline_end = recent_start

    orders = unit_orders.copy()
    if orders.empty:
        orders["order_time"] = pd.to_datetime([])
    else:
        orders["order_time"] = pd.to_datetime(orders["order_time"], errors="coerce")
        orders = orders[orders["order_time"].notna()]
        orders = orders[orders["order_time"] <= as_of_end]

    recent_orders = orders[
        (orders["order_time"] > recent_start) & (orders["order_time"] <= as_of_end)
    ]
    baseline_orders = orders[
        (orders["order_time"] > baseline_start) & (orders["order_time"] <= baseline_end)
    ]

    recent_months = max(recent_days / 30.4375, 1e-6)
    baseline_months = max(baseline_days / 30.4375, 1e-6)

    last_order_time = None
    if not orders.empty:
        last_order_time = pd.Timestamp(orders["order_time"].max()).to_pydatetime()

    return BaselineMetrics(
        org_code=org_code,
        product_line_code=product_line_code,
        as_of_date=as_of_start.date(),
        recent_start=recent_start.date(),
        baseline_start=baseline_start.date(),
        baseline_end=baseline_end.date(),
        total_orders=int(len(orders)),
        recent_orders=int(len(recent_orders)),
        baseline_orders=int(len(baseline_orders)),
        recent_qty=float(
            pd.to_numeric(recent_orders.get("purchase_qty"), errors="coerce").fillna(0).sum()
        ),
        baseline_qty=float(
            pd.to_numeric(baseline_orders.get("purchase_qty"), errors="coerce").fillna(0).sum()
        ),
        recent_active_sku_count=_active_sku_count(recent_orders),
        baseline_active_sku_count=_active_sku_count(baseline_orders),
        recent_monthly_order_rate=float(len(recent_orders) / recent_months),
        baseline_monthly_order_rate=float(len(baseline_orders) / baseline_months),
        last_order_time=last_order_time,
        recent_order_ids=_order_ids(recent_orders),
        baseline_order_ids=_order_ids(baseline_orders),
    )


def _active_sku_count(orders: pd.DataFrame) -> int:
    if orders.empty or "drug_code" not in orders.columns:
        return 0
    if "spec" in orders.columns:
        sku = orders["drug_code"].astype(str) + "|" + orders["spec"].fillna("").astype(str)
        return int(sku.nunique())
    return int(orders["drug_code"].astype(str).nunique())


def _order_ids(orders: pd.DataFrame) -> list[str]:
    if orders.empty or "order_id" not in orders.columns:
        return []
    return orders["order_id"].astype(str).tolist()
