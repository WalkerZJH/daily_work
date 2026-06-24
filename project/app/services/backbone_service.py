from __future__ import annotations

from datetime import date

import pandas as pd

from app.adapters.canonicalize import prepare_canonical_orders
from app.features.unit_snapshot_builder import UnitSnapshotBuilder
from app.ml.model_registry import ModelRegistry
from app.schemas.backbone import BackbonePrediction, BackbonePredictRequest
from app.schemas.config import AppConfig
from app.services.feature_service import FeatureService


class BackboneService:
    def __init__(
        self,
        config: AppConfig,
        model_registry: ModelRegistry | None = None,
    ) -> None:
        self.config = config
        self.model_registry = model_registry or ModelRegistry()

    def predict(self, request: BackbonePredictRequest) -> list[BackbonePrediction]:
        bundle = FeatureService(self.config).load_dataset(request, request.as_of_date)
        orders = prepare_canonical_orders(bundle)
        return self.predict_on_orders(orders, request.as_of_date)

    def predict_on_orders(self, orders: pd.DataFrame, as_of_date: date) -> list[BackbonePrediction]:
        features = UnitSnapshotBuilder().build_current_snapshot(orders, as_of_date)
        if features.empty:
            return []
        load_result = self.model_registry.load_active_backbone(features)
        raw_predictions = load_result.predictor.predict(features)
        predictions: list[BackbonePrediction] = []
        feature_lookup = {
            str(row["analysis_unit_id"]): row.to_dict()
            for _, row in features.iterrows()
        }
        for _, row in raw_predictions.iterrows():
            warnings = [
                *load_result.warnings,
                *list(row.get("warnings") or []),
            ]
            unit_id = str(row["analysis_unit_id"])
            predictions.append(
                BackbonePrediction(
                    analysis_unit_id=unit_id,
                    org_code=str(row["org_code"]),
                    org_name=_none_or_str(row.get("org_name")),
                    product_line_code=str(row["product_line_code"]),
                    product_line_name=_none_or_str(row.get("product_line_name")),
                    as_of_date=as_of_date,
                    selected_model_name=_none_or_str(row.get("selected_model_name")) or load_result.predictor.model_name,
                    model_name=load_result.predictor.model_name,
                    model_version=load_result.predictor.model_version,
                    p_alive=_none_or_float(row.get("p_alive")),
                    backbone_risk_score=_none_or_float(row.get("backbone_risk_score")),
                    confidence=float(row.get("confidence") or 0),
                    warnings=list(dict.fromkeys(warnings)),
                    debug_features=feature_lookup.get(unit_id, {}),
                    data_sufficiency=_dict_or_default(row.get("data_sufficiency"), feature_lookup.get(unit_id, {})),
                )
            )
        return predictions


def _none_or_float(value) -> float | None:
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _none_or_str(value) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def _dict_or_default(value, features: dict | None) -> dict:
    if isinstance(value, dict):
        return value
    features = features or {}
    return {
        "purchase_count_365d": features.get("purchase_count_365d"),
        "median_interval_days": features.get("median_interval_days"),
        "demand_profile": features.get("demand_profile"),
    }
