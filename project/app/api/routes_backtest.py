from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_app_config
from app.schemas.api import BacktestRequest, BacktestResponse
from app.schemas.config import AppConfig
from app.services.backtest_service import BacktestService

router = APIRouter(prefix="/api/v0/backtest", tags=["backtest"])


@router.post("/walk-forward", response_model=BacktestResponse)
def walk_forward(
    request: BacktestRequest,
    config: AppConfig = Depends(get_app_config),
) -> BacktestResponse:
    return BacktestService(config).walk_forward(request)
