from __future__ import annotations

from datetime import date

import pandas as pd

from app.algorithms.demand_shape import calculate_demand_shape
from app.core.config import load_config


def test_demand_shape_classifies_smooth_monthly_demand() -> None:
    orders = pd.DataFrame(
        {
            "order_id": [f"O{i:03d}" for i in range(1, 13)],
            "order_time": pd.date_range("2025-01-01", periods=12, freq="MS"),
            "purchase_qty": [100] * 12,
        }
    )

    result = calculate_demand_shape(
        orders,
        as_of_date=date(2025, 12, 31),
        config=load_config().demand_shape,
        lookback_days=365,
    )

    assert result.demand_shape == "smooth"
    assert result.adi is not None and result.adi < 1.32
    assert result.cv2 == 0
