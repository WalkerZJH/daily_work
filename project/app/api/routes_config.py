from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi import Query

from app.api.deps import get_app_config
from app.schemas.api import ConfigDryRunRequest, ConfigDryRunResponse
from app.schemas.config import AppConfig
from app.services.config_service import ConfigService
from app.services.user_config_service import UserConfigService

router = APIRouter(prefix="/api/v0/config", tags=["config"])


@router.get("")
def get_config(config: AppConfig = Depends(get_app_config)) -> dict[str, Any]:
    return ConfigService(config).current_config()


@router.get("/effective")
def effective_config(user_id: str | None = Query(None)) -> dict[str, Any]:
    return UserConfigService().effective_detector_config(user_id or "admin")


@router.post("/dry-run", response_model=ConfigDryRunResponse)
def config_dry_run(
    request: ConfigDryRunRequest,
    config: AppConfig = Depends(get_app_config),
) -> ConfigDryRunResponse:
    return ConfigService(config).dry_run_patch(request)
