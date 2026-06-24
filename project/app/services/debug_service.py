from __future__ import annotations

from datetime import date
from typing import Any

from app.adapters.canonicalize import prepare_canonical_orders
from app.adapters.quality import DataQualityChecker
from app.detectors.registry import build_default_detector_registry
from app.features.catalog import build_default_feature_catalog
from app.schemas.api import DataQualityReport, DataSourceRequest
from app.schemas.config import AppConfig
from app.services.feature_service import FeatureService
from app.services.inspection_service import InspectionService


class DebugService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def data_quality(self, source: DataSourceRequest) -> DataQualityReport:
        bundle = FeatureService(self.config).load_dataset(source)
        return DataQualityChecker().check_orders(
            prepare_canonical_orders(bundle),
            bundle.dataset_name,
        )

    def inspect_unit(
        self,
        source: DataSourceRequest,
        org_code: str,
        product_line_code: str,
        as_of_date: date,
    ) -> dict[str, Any]:
        return InspectionService(self.config).inspect_unit(
            source, org_code, product_line_code, as_of_date
        )

    def inspect_feature_unit(
        self,
        source: DataSourceRequest,
        org_code: str,
        analysis_grain: str,
        target_code: str,
        as_of_date: date,
    ) -> dict[str, Any]:
        return InspectionService(self.config).inspect_feature_unit(
            source, org_code, analysis_grain, target_code, as_of_date
        )

    def feature_snapshot(
        self,
        source: DataSourceRequest,
        org_code: str,
        analysis_grain: str,
        target_code: str,
        as_of_date: date,
    ) -> dict[str, Any]:
        _, snapshot = FeatureService(self.config).get_snapshot(
            source, org_code, analysis_grain, target_code, as_of_date
        )
        if snapshot is None:
            return {
                "snapshot": None,
                "warnings": ["FEATURE_SNAPSHOT_NOT_FOUND"],
            }
        return snapshot.model_dump(mode="json")

    def run_preprocess_debug(
        self,
        source: DataSourceRequest,
        as_of_date: date,
        enabled_preprocessors: list[str] | None = None,
    ) -> dict[str, Any]:
        run = FeatureService(self.config).run_preprocess(
            source,
            as_of_date,
            enabled_preprocessors=enabled_preprocessors,
        )
        return {
            "dataset_name": run.dataset_name,
            "as_of_date": run.as_of_date.isoformat(),
            "snapshot_count": len(run.snapshots),
            "feature_count": run.feature_count,
            "enabled_preprocessors": run.enabled_preprocessors,
            "feature_count_by_preprocessor": run.feature_count_by_preprocessor,
            "warning_summary": run.warning_summary,
            "lineage": [record.model_dump(mode="json") for record in run.lineage],
            "feature_catalog": [
                spec.model_dump(mode="json") for spec in build_default_feature_catalog().list()
            ],
        }

    def detector_specs(self) -> list[dict[str, Any]]:
        registry = build_default_detector_registry()
        return [meta.model_dump(mode="json") for meta in registry.catalog()]
