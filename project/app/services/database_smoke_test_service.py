from __future__ import annotations

import json
import time
from collections import Counter
from datetime import timedelta
from pathlib import Path
from typing import Any

from app.adapters.quality import DataQualityChecker
from app.core.config import PROJECT_ROOT
from app.features.label_builder import effective_purchase_mask
from app.schemas.api import (
    DataSourceRequest,
    DatabaseSmokeTestRequest,
    DatabaseSmokeTestResponse,
)
from app.schemas.config import AppConfig
from app.services.backbone_service import BackboneService
from app.services.feature_service import FeatureService
from app.services.inspection_service import InspectionService

SMOKE_OUTPUT_ROOT = PROJECT_ROOT / "artifacts" / "smoke_tests"


class DatabaseSmokeTestService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def run(self, request: DatabaseSmokeTestRequest, persist_summary: bool = True) -> DatabaseSmokeTestResponse:
        started = time.perf_counter()
        date_to = request.as_of_date
        date_from = date_to - timedelta(days=request.days)
        source = DataSourceRequest(
            source_type="database",
            dataset_name="database:BS_Agent_DingDan",
            date_from=date_from,
            date_to=date_to,
            row_limit=min(request.row_limit, 5000),
            enterprise_code=request.enterprise_code,
            province=request.province,
            province_code=request.province_code,
        )

        feature_run = FeatureService(self.config).run_preprocess(source, request.as_of_date)
        orders = feature_run.prepared_orders
        loaded_rows = int(len(orders))
        valid_order_rows = int(effective_purchase_mask(orders).sum()) if loaded_rows else 0

        quality_report = DataQualityChecker().check_orders(orders, feature_run.dataset_name)
        predictions = BackboneService(self.config).predict_on_orders(orders, request.as_of_date)
        dry_run = InspectionService(self.config).dry_run(source, request.as_of_date)

        warning_summary: Counter[str] = Counter(feature_run.warning_summary)
        for issue in quality_report.issues:
            warning_summary[issue.check_name] += issue.row_count
        for prediction in predictions:
            warning_summary.update(prediction.warnings)
        warning_summary.update(dry_run.warning_summary)
        if loaded_rows == 0:
            warning_summary["DATABASE_SMOKE_QUERY_RETURNED_EMPTY"] += 1

        palive_preview = [
            self._prediction_preview(prediction, include_debug_features=request.include_debug_features)
            for prediction in predictions[:10]
        ]
        summary = {
            "source_type": "database",
            "table": "BS_Agent_DingDan",
            "as_of_date": request.as_of_date.isoformat(),
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "row_limit": min(request.row_limit, 5000),
            "loaded_rows": loaded_rows,
            "valid_order_rows": valid_order_rows,
            "unit_count": len(feature_run.snapshots),
            "feature_count": feature_run.feature_count,
            "prediction_count": len(predictions),
            "risk_card_count": dry_run.clue_count,
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
        if not include_debug_features:
            payload["debug_features"] = {}
        return payload

    @staticmethod
    def _write_summary(summary: dict[str, Any]) -> Path:
        timestamp = time.strftime("%Y%m%d%H%M%S")
        output_dir = SMOKE_OUTPUT_ROOT / timestamp
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "summary.json"
        with output_path.open("w", encoding="utf-8") as file:
            json.dump(summary, file, ensure_ascii=False, indent=2)
        return output_path
