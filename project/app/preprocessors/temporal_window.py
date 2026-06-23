from __future__ import annotations

import pandas as pd

from app.features.snapshot import FeatureSnapshot
from app.preprocessors.base import PreprocessContext


class TemporalWindowPreprocessor:
    name = "temporal_window"
    version = "v0"
    required_inputs = ["canonical_orders", "feature_store"]
    output_features = [
        "recent_order_count",
        "baseline_order_count",
        "recent_qty",
        "baseline_qty",
        "recent_active_sku_count",
        "baseline_active_sku_count",
        "last_order_date",
        "inactive_days",
        "first_order_date",
        "has_recent_order",
        "has_baseline_order",
        "historical_median_ipi",
        "historical_mad_ipi",
    ]
    output_grain = "unit"
    as_of_date_sensitive = True

    def run(self, context: PreprocessContext) -> list[FeatureSnapshot]:
        orders = context.canonical_orders.copy()
        orders["order_time"] = pd.to_datetime(orders["order_time"], errors="coerce")
        orders["purchase_qty"] = pd.to_numeric(orders["purchase_qty"], errors="coerce").fillna(0)
        orders = orders[orders["order_time"].notna()]
        orders = orders[orders["order_time"].dt.date <= context.as_of_date]

        recent_days = context.config.preprocessors.temporal_window.recent_days
        baseline_days = context.config.preprocessors.temporal_window.baseline_days
        as_of_start = pd.Timestamp(context.as_of_date).normalize()
        as_of_end = as_of_start + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
        recent_start = as_of_start - pd.Timedelta(days=recent_days)
        baseline_start = recent_start - pd.Timedelta(days=baseline_days)
        baseline_end = recent_start

        snapshots = context.feature_store.query(as_of_date=context.as_of_date)
        output: list[FeatureSnapshot] = []
        for snapshot in snapshots:
            unit_orders = _filter_unit_orders(
                orders, snapshot.org_code, snapshot.analysis_grain, snapshot.target_code
            )
            recent = unit_orders[
                (unit_orders["order_time"] > recent_start) & (unit_orders["order_time"] <= as_of_end)
            ]
            baseline = unit_orders[
                (unit_orders["order_time"] > baseline_start)
                & (unit_orders["order_time"] <= baseline_end)
            ]
            first_order = None
            last_order = None
            inactive_days = None
            if not unit_orders.empty:
                first_order = pd.Timestamp(unit_orders["order_time"].min()).date().isoformat()
                last_ts = pd.Timestamp(unit_orders["order_time"].max())
                last_order = last_ts.date().isoformat()
                inactive_days = float((as_of_end - last_ts).total_seconds() / 86400)

            intervals = unit_orders.sort_values("order_time")["order_time"].diff().dt.days.dropna()
            intervals = intervals[intervals > 0]
            median_ipi = float(intervals.median()) if not intervals.empty else None
            mad_ipi = (
                float((intervals - intervals.median()).abs().median())
                if not intervals.empty
                else None
            )
            features = {
                "recent_order_count": int(len(recent)),
                "baseline_order_count": int(len(baseline)),
                "recent_qty": float(recent["purchase_qty"].sum()),
                "baseline_qty": float(baseline["purchase_qty"].sum()),
                "recent_active_sku_count": _active_sku_count(recent),
                "baseline_active_sku_count": _active_sku_count(baseline),
                "last_order_date": last_order,
                "inactive_days": inactive_days,
                "first_order_date": first_order,
                "has_recent_order": bool(len(recent) > 0),
                "has_baseline_order": bool(len(baseline) > 0),
                "historical_median_ipi": median_ipi,
                "historical_mad_ipi": mad_ipi,
            }
            output.append(snapshot.with_features(features, self.name, self.version))
        return output


def _filter_unit_orders(
    orders: pd.DataFrame,
    org_code: str,
    analysis_grain: str,
    target_code: str,
) -> pd.DataFrame:
    scoped = orders[orders["org_code"].astype(str) == str(org_code)]
    if analysis_grain == "product_line":
        return scoped[scoped["product_line_code"].astype(str) == str(target_code)].copy()
    if analysis_grain == "sku":
        return scoped[scoped["drug_code"].astype(str) == str(target_code)].copy()
    return scoped.iloc[0:0].copy()


def _active_sku_count(frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    if "spec" in frame.columns:
        sku = frame["drug_code"].astype(str) + "|" + frame["spec"].fillna("").astype(str)
        return int(sku.nunique())
    return int(frame["drug_code"].astype(str).nunique())
