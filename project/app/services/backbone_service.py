from __future__ import annotations

from datetime import date
from collections import Counter

import pandas as pd

from app.adapters.canonicalize import prepare_canonical_orders
from app.features.label_builder import filter_effective_purchases
from app.features.unit_snapshot_builder import UnitSnapshotBuilder
from app.ml.model_registry import ModelRegistry
from app.schemas.backbone import BackbonePrediction, BackbonePredictRequest, BackbonePredictResponse
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
        orders = _filter_current_orders(orders, request.as_of_date, request.history_start_date, request.product_line_code)
        effective_orders = filter_effective_purchases(orders)
        return self.predict_on_orders(effective_orders, request.as_of_date, include_debug_features=request.include_debug_features)

    def predict_with_summary(self, request: BackbonePredictRequest) -> BackbonePredictResponse:
        bundle = FeatureService(self.config).load_dataset(request, request.as_of_date)
        orders = prepare_canonical_orders(bundle)
        orders = _filter_current_orders(orders, request.as_of_date, request.history_start_date, request.product_line_code)
        raw_order_rows = int(len(orders))
        effective_orders = filter_effective_purchases(orders)
        effective_order_rows = int(len(effective_orders))
        analysis_unit_count = _analysis_unit_count(effective_orders)
        features = self.build_features(effective_orders, request.as_of_date)
        predictions = self.predict_on_orders(
            effective_orders,
            request.as_of_date,
            include_debug_features=request.include_debug_features,
        )
        warnings = []
        if analysis_unit_count > effective_order_rows or len(predictions) != analysis_unit_count:
            warnings.append("BACKBONE_UNIT_COUNT_INCONSISTENT")
        warning_summary = Counter(warnings)
        for prediction in predictions:
            warning_summary.update(prediction.warnings)
        fallback_used = any("FALLBACK" in warning for prediction in predictions for warning in prediction.warnings)
        summary = {
            "source_type": request.source_type,
            "as_of_date": request.as_of_date.isoformat(),
            "history_start_date": request.history_start_date.isoformat() if request.history_start_date else None,
            "lookback_days": request.lookback_days,
            "baseline_days": request.baseline_days,
            "raw_order_rows": raw_order_rows,
            "effective_order_rows": effective_order_rows,
            "analysis_unit_count": analysis_unit_count,
            "prediction_count": len(predictions),
            "feature_column_count": int(len(features.columns)) if not features.empty else 0,
            "model_name": predictions[0].model_name if predictions else None,
            "model_version": predictions[0].model_version if predictions else None,
            "fallback_used": fallback_used,
            "warnings": warnings,
        }
        return BackbonePredictResponse(summary=summary, predictions=predictions, warning_summary=dict(warning_summary))

    def build_features(self, orders: pd.DataFrame, as_of_date: date) -> pd.DataFrame:
        features = UnitSnapshotBuilder().build_current_snapshot(orders, as_of_date)
        if not features.empty and "analysis_unit_id" in features.columns:
            features = features.drop_duplicates(subset=["analysis_unit_id"], keep="last").reset_index(drop=True)
        return features

    def predict_on_orders(
        self,
        orders: pd.DataFrame,
        as_of_date: date,
        include_debug_features: bool = False,
    ) -> list[BackbonePrediction]:
        features = self.build_features(orders, as_of_date)
        if features.empty:
            return []
        load_result = self.model_registry.load_active_backbone(features)
        raw_predictions = load_result.predictor.predict(features)
        if not raw_predictions.empty and "analysis_unit_id" in raw_predictions.columns:
            raw_predictions = raw_predictions.drop_duplicates(subset=["analysis_unit_id"], keep="last").reset_index(drop=True)
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
                    last_purchase_date=_feature_last_purchase_date(feature_lookup.get(unit_id, {}), as_of_date),
                    days_since_last_purchase=_none_or_float(row.get("days_since_last_purchase"))
                    if _none_or_float(row.get("days_since_last_purchase")) is not None
                    else _none_or_float(feature_lookup.get(unit_id, {}).get("days_since_last_purchase")),
                    selected_model_name=_none_or_str(row.get("selected_model_name")) or load_result.predictor.model_name,
                    model_name=load_result.predictor.model_name,
                    model_version=load_result.predictor.model_version,
                    p_alive=_none_or_float(row.get("p_alive")),
                    backbone_risk_score=_none_or_float(row.get("backbone_risk_score")),
                    confidence=float(row.get("confidence") or 0),
                    warnings=list(dict.fromkeys(warnings)),
                    debug_features=_debug_features(feature_lookup.get(unit_id, {}), include_debug_features),
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


def _feature_last_purchase_date(features: dict | None, as_of_date: date) -> date | None:
    features = features or {}
    days_since = _none_or_float(features.get("days_since_last_purchase"))
    if days_since is None:
        return None
    return (pd.Timestamp(as_of_date) - pd.Timedelta(days=int(days_since))).date()


def _debug_features(features: dict | None, include_full: bool) -> dict:
    features = features or {}
    if include_full:
        return features
    keys = [
        "days_since_last_purchase",
        "purchase_count_90d",
        "purchase_count_365d",
        "median_interval_days",
        "demand_profile",
    ]
    return {key: features.get(key) for key in keys if key in features}


def _filter_current_orders(
    orders: pd.DataFrame,
    as_of_date: date,
    history_start_date: date | None,
    product_line_code: str | None,
) -> pd.DataFrame:
    if orders.empty or "order_time" not in orders.columns:
        return orders
    frame = orders.copy()
    frame["order_time"] = pd.to_datetime(frame["order_time"], errors="coerce")
    frame = frame[frame["order_time"].notna()]
    frame = frame[frame["order_time"].dt.date <= as_of_date]
    if history_start_date is not None:
        frame = frame[frame["order_time"].dt.date >= history_start_date]
    if product_line_code and "product_line_code" in frame.columns:
        frame = frame[frame["product_line_code"].astype(str) == str(product_line_code)]
    return frame


def _analysis_unit_count(orders: pd.DataFrame) -> int:
    if orders.empty or not {"org_code", "product_line_code"}.issubset(orders.columns):
        return 0
    return int(orders[["org_code", "product_line_code"]].dropna().drop_duplicates().shape[0])
