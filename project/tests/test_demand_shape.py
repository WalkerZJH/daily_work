from __future__ import annotations

from datetime import date

import pandas as pd

from app.core.config import load_config
from app.features.snapshot import FeatureSnapshot
from app.features.store import FeatureStore
from app.preprocessors.base import PreprocessContext
from app.preprocessors.demand_shape import DemandShapePreprocessor


def test_demand_shape_preprocessor_classifies_smooth_monthly_demand() -> None:
    orders = pd.DataFrame(
        {
            "order_id": [f"O{i:03d}" for i in range(1, 13)],
            "org_code": ["ORG_A"] * 12,
            "product_line_code": ["PL_A"] * 12,
            "drug_code": ["D1"] * 12,
            "order_time": pd.date_range("2025-01-01", periods=12, freq="MS"),
            "purchase_qty": [100] * 12,
        }
    )
    store = FeatureStore()
    store.put(
        FeatureSnapshot(
            unit_id="ORG_A|product_line|PL_A",
            org_code="ORG_A",
            analysis_grain="product_line",
            target_code="PL_A",
            as_of_date=date(2025, 12, 31),
        )
    )
    context = PreprocessContext(
        canonical_orders=orders,
        dim_drug=pd.DataFrame(),
        dim_org=pd.DataFrame(),
        product_line_mapping=pd.DataFrame(),
        optional_tables={},
        as_of_date=date(2025, 12, 31),
        config=load_config(),
        feature_store=store,
    )

    [result] = DemandShapePreprocessor().run(context)

    assert result.features["demand_shape"] == "smooth"
    assert result.features["adi"] is not None and result.features["adi"] < 1.32
    assert result.features["cv2"] == 0
