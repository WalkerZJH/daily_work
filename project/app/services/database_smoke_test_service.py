from __future__ import annotations

import json
import time
from collections import Counter
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from app.adapters.canonicalize import prepare_canonical_orders
from app.adapters.quality import DataQualityChecker
from app.core.config import PROJECT_ROOT
from app.features.label_builder import filter_effective_purchases
from app.schemas.api import (
    DataSourceRequest,
    DatabaseSmokeTestRequest,
    DatabaseSmokeTestResponse,
)
from app.schemas.config import AppConfig
from app.services.backbone_service import BackboneService
from app.services.feature_service import FeatureService

SMOKE_OUTPUT_ROOT = PROJECT_ROOT / "artifacts" / "smoke_tests"


class DatabaseSmokeTestService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def run(self, request: DatabaseSmokeTestRequest, persist_summary: bool = True) -> DatabaseSmokeTestResponse:
        started = time.perf_counter()
        date_to = request.as_of_date
        lookback_days = request.lookback_days or request.days
        date_from = request.history_start_date or (date_to - timedelta(days=lookback_days + request.baseline_days))
        source = DataSourceRequest(
            source_type=request.source_type,
            dataset_name="database:BS_Agent_DingDan" if request.source_type == "database" else "sample",
            date_from=date_from,
            date_to=date_to,
            row_limit=min(request.row_limit, 5000),
            enterprise_code=request.enterprise_code,
            province=request.province,
            province_code=request.province_code,
        )

        bundle = FeatureService(self.config).load_dataset(source, request.as_of_date)
        orders = prepare_canonical_orders(bundle)
        orders = self._filter_orders(orders, request, date_from)
        raw_order_rows = int(len(orders))
        effective_orders = filter_effective_purchases(orders)
        effective_order_rows = int(len(effective_orders))
        analysis_unit_count = _analysis_unit_count(effective_orders)

        backbone = BackboneService(self.config)
        features = backbone.build_features(effective_orders, request.as_of_date)
        feature_column_count = int(len(features.columns)) if not features.empty else 0
        predictions = backbone.predict_on_orders(
            effective_orders,
            request.as_of_date,
            include_debug_features=request.include_debug_features,
        )
        predictions = _dedupe_predictions(predictions)

        quality_report = DataQualityChecker().check_orders(orders, bundle.dataset_name)
        warning_summary: Counter[str] = Counter()
        for issue in quality_report.issues:
            warning_summary[issue.check_name] += issue.row_count
        for prediction in predictions:
            warning_summary.update(prediction.warnings)
        warnings: list[str] = []
        if raw_order_rows == 0:
            warning_summary["DATABASE_SMOKE_QUERY_RETURNED_EMPTY"] += 1
            warnings.append("DATABASE_SMOKE_QUERY_RETURNED_EMPTY")
        if analysis_unit_count > effective_order_rows or len(predictions) != analysis_unit_count:
            warning_summary["BACKBONE_UNIT_COUNT_INCONSISTENT"] += 1
            warnings.append("BACKBONE_UNIT_COUNT_INCONSISTENT")

        palive_preview = [
            self._prediction_preview(prediction, include_debug_features=request.include_debug_features)
            for prediction in predictions[:10]
        ]
        model_name = predictions[0].model_name if predictions else None
        model_version = predictions[0].model_version if predictions else None
        fallback_used = any("FALLBACK" in warning for prediction in predictions for warning in prediction.warnings)
        summary = {
            "source_type": request.source_type,
            "table": "BS_Agent_DingDan",
            "as_of_date": request.as_of_date.isoformat(),
            "history_start_date": request.history_start_date.isoformat() if request.history_start_date else None,
            "lookback_days": lookback_days,
            "baseline_days": request.baseline_days,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "row_limit": min(request.row_limit, 5000),
            "raw_order_rows": raw_order_rows,
            "effective_order_rows": effective_order_rows,
            "analysis_unit_count": analysis_unit_count,
            "prediction_count": len(predictions),
            "feature_column_count": feature_column_count,
            "model_name": model_name,
            "model_version": model_version,
            "fallback_used": fallback_used,
            "warnings": warnings,
            # Legacy aliases kept for existing front-end cards.
            "loaded_rows": raw_order_rows,
            "valid_order_rows": effective_order_rows,
            "unit_count": analysis_unit_count,
            "feature_count": feature_column_count,
            "risk_card_count": 0,
            "palive_preview": palive_preview,
            "warning_summary": dict(warning_summary),
            "elapsed_seconds": round(time.perf_counter() - started, 4),
        }
        if persist_summary:
            self._write_summary(summary)
        return DatabaseSmokeTestResponse(
            summary=summary,
            palive_preview=palive_preview,
            warning_summary=dict(warning_summary),
        )

    @staticmethod
    def _prediction_preview(prediction, include_debug_features: bool) -> dict[str, Any]:
        payload = prediction.model_dump(mode="json")
        return payload

    @staticmethod
    def _filter_orders(orders, request: DatabaseSmokeTestRequest, date_from):
        if orders.empty or "order_time" not in orders.columns:
            return orders
        frame = orders.copy()
        frame["order_time"] = pd.to_datetime(frame["order_time"], errors="coerce")
        frame = frame[frame["order_time"].notna()]
        frame = frame[frame["order_time"].dt.date <= request.as_of_date]
        frame = frame[frame["order_time"].dt.date >= date_from]
        if request.product_line_code and "product_line_code" in frame.columns:
            frame = frame[frame["product_line_code"].astype(str) == str(request.product_line_code)]
        return frame

    @staticmethod
    def _write_summary(summary: dict[str, Any]) -> Path:
        timestamp = time.strftime("%Y%m%d%H%M%S")
        output_dir = SMOKE_OUTPUT_ROOT / timestamp
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "summary.json"
        with output_path.open("w", encoding="utf-8") as file:
            json.dump(summary, file, ensure_ascii=False, indent=2)
        return output_path


def _analysis_unit_count(orders) -> int:
    if orders.empty or not {"org_code", "product_line_code"}.issubset(orders.columns):
        return 0
    return int(orders[["org_code", "product_line_code"]].dropna().drop_duplicates().shape[0])


def _dedupe_predictions(predictions):
    seen = set()
    output = []
    for prediction in predictions:
        if prediction.analysis_unit_id in seen:
            continue
        seen.add(prediction.analysis_unit_id)
        output.append(prediction)
    return output
