from __future__ import annotations

import pandas as pd

from app.features.snapshot import FeatureSnapshot
from app.preprocessors.base import PreprocessContext
from app.preprocessors.temporal_window import _filter_unit_orders


class DemandShapePreprocessor:
    name = "demand_shape"
    version = "v0"
    required_inputs = ["canonical_orders", "feature_store"]
    output_features = ["adi", "cv2", "demand_shape", "demand_shape_confidence"]
    output_grain = "unit"
    as_of_date_sensitive = True

    def run(self, context: PreprocessContext) -> list[FeatureSnapshot]:
        orders = context.canonical_orders.copy()
        orders["order_time"] = pd.to_datetime(orders["order_time"], errors="coerce")
        orders["purchase_qty"] = pd.to_numeric(orders["purchase_qty"], errors="coerce").fillna(0)
        orders = orders[orders["order_time"].notna()]
        orders = orders[orders["order_time"].dt.date <= context.as_of_date]

        cfg = context.config.preprocessors.demand_shape
        lookback_days = context.config.preprocessors.temporal_window.baseline_days
        as_of_start = pd.Timestamp(context.as_of_date).normalize()
        lookback_start = as_of_start - pd.Timedelta(days=lookback_days)
        month_index = pd.date_range(
            start=lookback_start.to_period("M").to_timestamp(),
            end=as_of_start.to_period("M").to_timestamp(),
            freq="MS",
        )

        output: list[FeatureSnapshot] = []
        for snapshot in context.feature_store.query(as_of_date=context.as_of_date):
            unit_orders = _filter_unit_orders(
                orders, snapshot.org_code, snapshot.analysis_grain, snapshot.target_code
            )
            unit_orders = unit_orders[unit_orders["order_time"] > lookback_start]
            warnings: list[str] = []
            adi = None
            cv2 = None
            confidence = 0.0
            shape = "unknown"
            if unit_orders.empty:
                warnings.append("NO_DEMAND_HISTORY")
            else:
                monthly = (
                    unit_orders.set_index("order_time")["purchase_qty"].resample("MS").sum().sort_index()
                )
                monthly = monthly.reindex(month_index, fill_value=0)
                nonzero = monthly[monthly > 0]
                if len(nonzero) < cfg.min_nonzero_periods:
                    warnings.append("INSUFFICIENT_NONZERO_PERIODS")
                    confidence = 0.2
                else:
                    adi = float(len(monthly) / len(nonzero))
                    mean_qty = float(nonzero.mean())
                    cv2 = 0.0 if mean_qty == 0 else float((nonzero.std(ddof=0) / mean_qty) ** 2)
                    if adi < cfg.adi_threshold and cv2 < cfg.cv2_threshold:
                        shape = "smooth"
                    elif adi < cfg.adi_threshold and cv2 >= cfg.cv2_threshold:
                        shape = "erratic"
                    elif adi >= cfg.adi_threshold and cv2 < cfg.cv2_threshold:
                        shape = "intermittent"
                    else:
                        shape = "lumpy"
                    confidence = min(1.0, 0.45 + len(nonzero) / 12)
            output.append(
                snapshot.with_features(
                    {
                        "adi": adi,
                        "cv2": cv2,
                        "demand_shape": shape,
                        "demand_shape_confidence": confidence,
                    },
                    self.name,
                    self.version,
                    warnings,
                )
            )
        return output
