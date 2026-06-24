from __future__ import annotations

from app.detectors.registry import DetectorMeta
from app.services.user_config_service import UserConfigService
from fastapi import APIRouter

router = APIRouter(prefix="/api/v0/detectors", tags=["detectors"])


@router.get("/catalog", response_model=list[DetectorMeta])
def detector_catalog() -> list[DetectorMeta]:
    return UserConfigService().detector_catalog()
