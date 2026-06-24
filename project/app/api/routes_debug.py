from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_app_config
from app.schemas.api import (
    DataQualityReport,
    DataQualityRequest,
    DataSourceRequest,
    PreprocessRunRequest,
)
from app.schemas.config import AppConfig
from app.services.debug_service import DebugService

router = APIRouter(prefix="/api/v0/debug", tags=["debug"])


@router.post("/data-quality", response_model=DataQualityReport)
def data_quality(
    request: DataQualityRequest,
    config: AppConfig = Depends(get_app_config),
) -> DataQualityReport:
    return DebugService(config).data_quality(request)


@router.get("/unit/{org_code}/{product_line_code}")
def inspect_unit(
    org_code: str,
    product_line_code: str,
    as_of_date: date = Query(...),
    dataset_name: str | None = Query("sample"),
    csv_path: str | None = Query(None),
    config: AppConfig = Depends(get_app_config),
) -> dict[str, Any]:
    source = DataSourceRequest(dataset_name=dataset_name, csv_path=csv_path)
    return DebugService(config).inspect_unit(source, org_code, product_line_code, as_of_date)


@router.get("/features/{org_code}/{analysis_grain}/{target_code}")
def feature_snapshot(
    org_code: str,
    analysis_grain: str,
    target_code: str,
    as_of_date: date = Query(...),
    dataset_name: str | None = Query("sample"),
    csv_path: str | None = Query(None),
    config: AppConfig = Depends(get_app_config),
) -> dict[str, Any]:
    source = DataSourceRequest(dataset_name=dataset_name, csv_path=csv_path)
    return DebugService(config).feature_snapshot(
        source, org_code, analysis_grain, target_code, as_of_date
    )


@router.post("/preprocess/run")
def run_preprocess(
    request: PreprocessRunRequest,
    config: AppConfig = Depends(get_app_config),
) -> dict[str, Any]:
    source = DataSourceRequest(dataset_name=request.dataset_name, csv_path=request.csv_path)
    return DebugService(config).run_preprocess_debug(
        source,
        request.as_of_date,
        enabled_preprocessors=request.enabled_preprocessors,
    )


@router.get("/detectors")
def detector_specs(config: AppConfig = Depends(get_app_config)) -> list[dict[str, Any]]:
    return DebugService(config).detector_specs()


@router.get("/unit/{org_code}/{analysis_grain}/{target_code}")
def inspect_feature_unit(
    org_code: str,
    analysis_grain: str,
    target_code: str,
    as_of_date: date = Query(...),
    dataset_name: str | None = Query("sample"),
    csv_path: str | None = Query(None),
    config: AppConfig = Depends(get_app_config),
) -> dict[str, Any]:
    source = DataSourceRequest(dataset_name=dataset_name, csv_path=csv_path)
    return DebugService(config).inspect_feature_unit(
        source, org_code, analysis_grain, target_code, as_of_date
    )
