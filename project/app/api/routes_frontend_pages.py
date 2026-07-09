from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.api.routes_display_lookup import get_display_lookup_service
from app.api.routes_detector_results import get_detector_result_service
from app.api.routes_user_top_entities import get_user_top_entity_service
from app.schemas.frontend_pages import (
    MonthlyReportsPayload,
    OneshotPayload,
    ProofCasesPayload,
    RiskEntitiesPayload,
    RiskEntityDetailPayload,
    WorkbenchPayload,
)
from app.services.frontend_page_service import FrontendPageService, get_frontend_page_service
from app.services.frontend_top_entity_adapter import (
    build_risk_entities_payload_from_top_entities,
    build_workbench_payload_from_top_entities,
)
from app.services.display_lookup_service import DisplayLookupService
from app.services.detector_result_service import DetectorResultService
from app.services.user_top_entity_service import TopEntityService

router = APIRouter(prefix="/api/v1", tags=["frontend-pages"])
WorkbenchSortBy = Literal["risk_probability", "involved_amount"]


@router.get("/workbench", response_model=WorkbenchPayload)
def frontend_workbench(
    service: FrontendPageService = Depends(get_frontend_page_service),
    top_entity_service: TopEntityService = Depends(get_user_top_entity_service),
    detector_service: DetectorResultService = Depends(get_detector_result_service),
    display_lookup_service: DisplayLookupService = Depends(get_display_lookup_service),
    x_user_id: Annotated[str | None, Header()] = None,
    manufacturer_code: Annotated[list[str] | None, Query()] = None,
    report_month: str | None = Query(default=None),
    run_date: str | None = Query(default=None),
    horizon: str = Query(default="H6", pattern="^H(3|6|12)$"),
    top_n: int = Query(default=20, ge=1, le=100),
    sort_by: WorkbenchSortBy = Query(default="risk_probability"),
) -> dict:
    payload = build_workbench_payload_from_top_entities(
        top_entity_service,
        user_id=x_user_id or "admin",
        top_n=top_n,
        horizon=horizon,
        report_month=report_month,
        manufacturer_codes=manufacturer_code,
        sort_by=sort_by,
        detector_summary=_detector_summary(
            detector_service,
            run_date=run_date,
            manufacturer_codes=manufacturer_code,
        ),
    )
    if payload:
        return _with_display_lookup_status(payload, display_lookup_service)
    return _with_display_lookup_status(service.workbench(), display_lookup_service)


@router.get("/risk-entities", response_model=RiskEntitiesPayload)
def frontend_risk_entities(
    service: FrontendPageService = Depends(get_frontend_page_service),
    top_entity_service: TopEntityService = Depends(get_user_top_entity_service),
    display_lookup_service: DisplayLookupService = Depends(get_display_lookup_service),
    x_user_id: Annotated[str | None, Header()] = None,
    manufacturer_code: Annotated[list[str] | None, Query()] = None,
    report_month: str | None = Query(default=None),
    horizon: str = Query(default="H6", pattern="^H(3|6|12)$"),
    top_n: int = Query(default=20, ge=1, le=100),
    sort_by: WorkbenchSortBy = Query(default="risk_probability"),
) -> dict:
    top_entity_payload = build_risk_entities_payload_from_top_entities(
        top_entity_service,
        user_id=x_user_id or "admin",
        top_n=top_n,
        horizon=horizon,
        report_month=report_month,
        manufacturer_codes=manufacturer_code,
        sort_by=sort_by,
    )
    if top_entity_payload:
        return _with_display_lookup_status(top_entity_payload, display_lookup_service)
    return _with_display_lookup_status(service.risk_entities(), display_lookup_service)


@router.get("/risk-entities/{entity_id}", response_model=RiskEntityDetailPayload)
def frontend_risk_entity_detail(
    entity_id: str,
    service: FrontendPageService = Depends(get_frontend_page_service),
    horizon: str = Query(default="H6", pattern="^H(3|6|12)$"),
) -> dict:
    try:
        return service.risk_entity_detail(entity_id, horizon=horizon)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown risk entity: {entity_id}") from exc


@router.get("/risk-entities/{entity_id}/probability-trend")
def frontend_risk_entity_probability_trend(
    entity_id: str,
    service: FrontendPageService = Depends(get_frontend_page_service),
    horizon: str = Query(default="H6", pattern="^H(3|6|12)$"),
) -> dict:
    try:
        return service.probability_trend(entity_id, horizon=horizon)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown risk entity: {entity_id}") from exc


@router.get("/my/manufacturers")
def my_manufacturers(
    top_entity_service: TopEntityService = Depends(get_user_top_entity_service),
    x_user_id: Annotated[str | None, Header()] = None,
    report_month: str | None = Query(default=None),
    manufacturer_code: Annotated[list[str] | None, Query()] = None,
) -> dict:
    return top_entity_service.list_visible_manufacturers(
        user_id=x_user_id or "admin",
        report_month=report_month,
        manufacturer_codes=manufacturer_code,
    )


@router.get("/oneshot-terminals", response_model=OneshotPayload)
def frontend_oneshot_terminals(
    service: FrontendPageService = Depends(get_frontend_page_service),
) -> dict:
    return service.oneshot_terminals()


@router.get("/monthly-reports", response_model=MonthlyReportsPayload)
def frontend_monthly_reports(
    service: FrontendPageService = Depends(get_frontend_page_service),
) -> dict:
    return service.monthly_reports()


@router.get("/proof-cases", response_model=ProofCasesPayload)
def frontend_proof_cases(
    service: FrontendPageService = Depends(get_frontend_page_service),
    display_lookup_service: DisplayLookupService = Depends(get_display_lookup_service),
) -> dict:
    return _with_display_lookup_status(service.proof_cases(), display_lookup_service)


def _with_display_lookup_status(
    payload: dict,
    display_lookup_service: DisplayLookupService,
) -> dict:
    return {**payload, "display_lookup_status": display_lookup_service.status()}


def _detector_summary(
    detector_service: DetectorResultService,
    *,
    run_date: str | None,
    manufacturer_codes: list[str] | None,
) -> dict[str, object]:
    runs = detector_service.runs(run_date=run_date, limit=1)
    latest = runs.get("items", [{}])[0] if runs.get("items") else {}
    clues = detector_service.clues(run_date=run_date, page=1, page_size=200)
    items = clues.get("items", [])
    if manufacturer_codes:
        allowed = {str(code) for code in manufacturer_codes}
        items = [item for item in items if str(item.get("manufacturer_code")) in allowed]
    return {
        "detector_clue_count": len(items),
        "latest_detector_run_date": latest.get("run_date"),
        "detector_status_summary": "ready" if latest else "missing",
    }
