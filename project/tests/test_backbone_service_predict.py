from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from app.core.config import load_config
from app.ml.model_contracts import ModelLoadResult
from app.services.backbone_service import BackboneService


class _MockPredictor:
    model_name = "palive_lgbm"
    model_version = "test"
    required_features: list[str] = []

    def predict(self, features: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "analysis_unit_id": row["analysis_unit_id"],
                    "org_code": row["org_code"],
                    "product_line_code": row["product_line_code"],
                    "p_alive": 0.7,
                    "backbone_risk_score": 30,
                    "confidence": 0.8,
                    "warnings": ["MOCK_MODEL"],
                }
                for _, row in features.iterrows()
            ]
        )


@dataclass
class _MockRegistry:
    def load_active_backbone(self, features: pd.DataFrame) -> ModelLoadResult:
        return ModelLoadResult(_MockPredictor(), [])


def test_backbone_service_predict_returns_complete_prediction() -> None:
    orders = pd.DataFrame([_row("2026-01-01"), _row("2026-02-01")])

    predictions = BackboneService(load_config(), model_registry=_MockRegistry()).predict_on_orders(
        orders,
        date(2026, 3, 1),
    )

    assert predictions
    prediction = predictions[0]
    assert prediction.analysis_unit_id == "ORG_A|product_line|PL_A"
    assert prediction.model_name == "palive_lgbm"
    assert prediction.model_version == "test"
    assert prediction.p_alive == 0.7
    assert prediction.backbone_risk_score == 30
    assert prediction.debug_features


def _row(order_time: str) -> dict:
    return {
        "order_id": order_time,
        "org_code": "ORG_A",
        "product_line_code": "PL_A",
        "drug_code": "D1",
        "order_time": order_time,
        "purchase_qty": 1,
        "purchase_amount": 10,
        "purchase_price": 10,
    }
