from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_app_config
from app.schemas.api import (
    DatabaseFreshnessRequest,
    DatabaseFreshnessResponse,
    DatabaseSmokeTestRequest,
    DatabaseSmokeTestResponse,
)
from app.schemas.config import AppConfig
from app.services.data_freshness_service import DataFreshnessService
from app.services.database_smoke_test_service import DatabaseSmokeTestService

router = APIRouter(prefix="/api/v0/smoke-test", tags=["smoke-test"])


@router.post("/database", response_model=DatabaseSmokeTestResponse)
def run_database_smoke_test(
    request: DatabaseSmokeTestRequest,
    config: AppConfig = Depends(get_app_config),
) -> DatabaseSmokeTestResponse:
    return DatabaseSmokeTestService(config).run(request, persist_summary=False)


@router.post("/freshness", response_model=DatabaseFreshnessResponse)
def check_database_freshness(
    request: DatabaseFreshnessRequest,
) -> DatabaseFreshnessResponse:
    return DataFreshnessService().check(request)
