from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_app_config
from app.detectors.registry import DETECTOR_META, DetectorMeta
from app.schemas.api import DetectorConfigResponse, DetectorRunRequest, DetectorRunResponse, DetectorRuntimeConfig, DetectorRuntimeConfigPatch
from app.schemas.config import AppConfig
from app.services.detector_config_service import DetectorRuntimeConfigService
from app.services.detector_run_service import DetectorRunService
from app.services.user_config_service import UserConfigService

router = APIRouter(prefix="/api/v0/detectors", tags=["detectors"])


@router.get("/catalog", response_model=list[DetectorMeta])
def detector_catalog() -> list[DetectorMeta]:
    return UserConfigService().detector_catalog()


@router.post("/run", response_model=DetectorRunResponse)
def run_detectors(
    request: DetectorRunRequest,
    config: AppConfig = Depends(get_app_config),
) -> DetectorRunResponse:
    return DetectorRunService(config).run(request)


@router.get("/config", response_model=DetectorConfigResponse)
def detector_configs() -> DetectorConfigResponse:
    service = DetectorRuntimeConfigService()
    configs = service.list_configs()
    return DetectorConfigResponse(
        configs=configs,
        warning_summary=service.warning_summary_for([item.detector_id for item in configs]),
    )


@router.get("/{detector_id}/config", response_model=DetectorRuntimeConfig)
def detector_config(detector_id: str) -> DetectorRuntimeConfig:
    try:
        config, _ = DetectorRuntimeConfigService().get_config(detector_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown detector_id: {detector_id}") from exc
    return config


@router.patch("/{detector_id}/config", response_model=DetectorRuntimeConfig)
def patch_detector_config(detector_id: str, patch: DetectorRuntimeConfigPatch) -> DetectorRuntimeConfig:
    try:
        config, _ = DetectorRuntimeConfigService().patch_config(detector_id, patch)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown detector_id: {detector_id}") from exc
    return config


@router.post("/{detector_id}/run", response_model=DetectorRunResponse)
def run_one_detector(
    detector_id: str,
    request: DetectorRunRequest,
    config: AppConfig = Depends(get_app_config),
) -> DetectorRunResponse:
    if detector_id not in DETECTOR_META:
        raise HTTPException(status_code=404, detail=f"Unknown detector_id: {detector_id}")
    request.enabled_detectors = [detector_id]
    request.category = None
    return DetectorRunService(config).run(request)


@router.post("/run-by-category", response_model=DetectorRunResponse)
def run_by_category(
    request: DetectorRunRequest,
    config: AppConfig = Depends(get_app_config),
) -> DetectorRunResponse:
    if not request.category:
        raise HTTPException(status_code=422, detail="category is required")
    request.enabled_detectors = None
    return DetectorRunService(config).run(request)
