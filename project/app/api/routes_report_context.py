from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.services.report_context_service import (
    ReportContextService,
    build_default_report_context_service,
)

router = APIRouter(prefix="/api/v1", tags=["report-context"])


def get_report_context_service() -> ReportContextService:
    return build_default_report_context_service()


@router.get("/report-context")
def report_context(
    service: Annotated[ReportContextService, Depends(get_report_context_service)],
    report_month: str | None = Query(default=None),
    run_date: str | None = Query(default=None),
    horizon: str | None = Query(default=None),
    manufacturer_code: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
) -> dict:
    return service.resolve(
        report_month=report_month,
        run_date=run_date,
        horizon=horizon,
        manufacturer_code=manufacturer_code,
        user_id=user_id,
    )
