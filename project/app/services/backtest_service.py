from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta

from app.schemas.api import BacktestRequest, BacktestResponse, DataSourceRequest
from app.schemas.config import AppConfig
from app.services.inspection_service import InspectionService


class BacktestService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def walk_forward(self, request: BacktestRequest) -> BacktestResponse:
        service = InspectionService(self.config)
        source = DataSourceRequest(dataset_name=request.dataset_name, csv_path=request.csv_path)
        periods = [
            service.dry_run(source, as_of_date)
            for as_of_date in _iter_walk_forward_dates(
                request.start_date,
                request.end_date,
                request.step_days,
            )
        ]
        dataset_name = periods[0].dataset_name if periods else (request.dataset_name or "unknown")
        return BacktestResponse(dataset_name=dataset_name, periods=periods)


def _iter_walk_forward_dates(start_date: date, end_date: date, step_days: int) -> Iterator[date]:
    current = start_date
    while current <= end_date:
        yield current
        current = current + timedelta(days=step_days)
