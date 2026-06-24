from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_app_config
from app.detectors.registry import DetectorMeta
from app.schemas.api import DetectorRunRequest, DetectorRunResponse
from app.schemas.config import AppConfig
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
