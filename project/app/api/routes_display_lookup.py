from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.routes_report_context import get_report_context_service
from app.services.display_lookup_service import (
    DisplayLookupService,
    build_default_display_lookup_service,
)
from app.services.report_context_service import ReportContextService

router = APIRouter(prefix="/api/v1/display-lookup", tags=["display-lookup"])


def get_display_lookup_service() -> DisplayLookupService:
    return build_default_display_lookup_service()


@router.get("/status")
def display_lookup_status(
    service: Annotated[DisplayLookupService, Depends(get_display_lookup_service)],
    report_context_service: Annotated[ReportContextService, Depends(get_report_context_service)],
    report_month: str | None = Query(default=None),
    run_date: str | None = Query(default=None),
    horizon: str | None = Query(default=None),
    manufacturer_code: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
) -> dict:
    context = report_context_service.resolve(
        report_month=report_month,
        run_date=run_date,
        horizon=horizon,
        manufacturer_code=manufacturer_code,
        user_id=user_id,
    )
    return {
        **service.status(),
        "report_context": context,
        "requested_report_month": context.get("requested_report_month"),
        "effective_report_month": context.get("effective_report_month"),
        "requested_run_date": context.get("requested_run_date"),
        "effective_run_date": context.get("effective_run_date"),
        "date_resolution_status": context.get("date_resolution_status"),
    }
