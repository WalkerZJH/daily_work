from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_app_config
from app.schemas.api import DryRunRequest, DryRunResponse
from app.schemas.config import AppConfig
from app.services.inspection_service import InspectionService

router = APIRouter(prefix="/api/v0/inspection", tags=["inspection"])


@router.post("/dry-run", response_model=DryRunResponse)
def dry_run(
    request: DryRunRequest,
    config: AppConfig = Depends(get_app_config),
) -> DryRunResponse:
    return InspectionService(config).dry_run(request, request.as_of_date)
