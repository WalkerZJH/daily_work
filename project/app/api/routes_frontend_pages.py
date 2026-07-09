from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.api.routes_display_lookup import get_display_lookup_service
from app.api.routes_detector_results import get_detector_result_service
from app.api.routes_report_context import get_report_context_service
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
from app.services.report_context_service import ReportContextService
from app.services.user_top_entity_service import TopEntityService

router = APIRouter(prefix="/api/v1", tags=["frontend-pages"])
WorkbenchSortBy = Literal["loss_value", "risk_probability", "detector_score", "involved_amount"]


@router.get("/workbench", response_model=WorkbenchPayload)
def frontend_workbench(
    service: FrontendPageService = Depends(get_frontend_page_service),
    top_entity_service: TopEntityService = Depends(get_user_top_entity_service),
    detector_service: DetectorResultService = Depends(get_detector_result_service),
    display_lookup_service: DisplayLookupService = Depends(get_display_lookup_service),
    report_context_service: ReportContextService = Depends(get_report_context_service),
    x_user_id: Annotated[str | None, Header()] = None,
    user_id: str | None = Query(default=None),
    manufacturer_code: Annotated[list[str] | None, Query()] = None,
    report_month: str | None = Query(default=None),
    run_date: str | None = Query(default=None),
    horizon: str = Query(default="H6"),
    top_n: int = Query(default=20, ge=1, le=100),
    sort_by: WorkbenchSortBy = Query(default="risk_probability"),
) -> dict:
    context = report_context_service.resolve(
        report_month=report_month,
        run_date=run_date,
        horizon=horizon,
        manufacturer_code=_first_query_value(manufacturer_code),
        user_id=user_id or x_user_id,
    )
    effective_report_month = context.get("effective_report_month") or report_month
    effective_run_date = context.get("effective_run_date") or run_date
    effective_horizon = context.get("effective_horizon") or horizon
    payload = build_workbench_payload_from_top_entities(
        top_entity_service,
        user_id=user_id or x_user_id or "admin",
        top_n=top_n,
        horizon=effective_horizon,
        report_month=effective_report_month,
        manufacturer_codes=manufacturer_code,
        sort_by=sort_by,
        detector_summary=_detector_summary(
            detector_service,
            run_date=effective_run_date,
            manufacturer_codes=manufacturer_code,
        ),
        run_date=effective_run_date,
    )
    if payload:
        return _with_report_context(
            _with_display_lookup_status(payload, display_lookup_service),
            context,
        )
    return _with_report_context(_with_display_lookup_status(service.workbench(), display_lookup_service), context)


@router.get("/risk-entities", response_model=RiskEntitiesPayload)
def frontend_risk_entities(
    service: FrontendPageService = Depends(get_frontend_page_service),
    top_entity_service: TopEntityService = Depends(get_user_top_entity_service),
    display_lookup_service: DisplayLookupService = Depends(get_display_lookup_service),
    report_context_service: ReportContextService = Depends(get_report_context_service),
    x_user_id: Annotated[str | None, Header()] = None,
    user_id: str | None = Query(default=None),
    manufacturer_code: Annotated[list[str] | None, Query()] = None,
    report_month: str | None = Query(default=None),
    run_date: str | None = Query(default=None),
    horizon: str = Query(default="H6"),
    top_n: int = Query(default=20, ge=1, le=100),
    sort_by: WorkbenchSortBy = Query(default="risk_probability"),
) -> dict:
    context = report_context_service.resolve(
        report_month=report_month,
        run_date=run_date,
        horizon=horizon,
        manufacturer_code=_first_query_value(manufacturer_code),
        user_id=user_id or x_user_id,
    )
    top_entity_payload = build_risk_entities_payload_from_top_entities(
        top_entity_service,
        user_id=user_id or x_user_id or "admin",
        top_n=top_n,
        horizon=context.get("effective_horizon") or horizon,
        report_month=context.get("effective_report_month") or report_month,
        manufacturer_codes=manufacturer_code,
        sort_by=sort_by,
    )
    if top_entity_payload:
        return _with_report_context(_with_display_lookup_status(top_entity_payload, display_lookup_service), context)
    return _with_report_context(_with_display_lookup_status(service.risk_entities(), display_lookup_service), context)


@router.get("/risk-entities/{entity_id}", response_model=RiskEntityDetailPayload)
def frontend_risk_entity_detail(
    entity_id: str,
    service: FrontendPageService = Depends(get_frontend_page_service),
    report_context_service: ReportContextService = Depends(get_report_context_service),
    report_month: str | None = Query(default=None),
    run_date: str | None = Query(default=None),
    manufacturer_code: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    horizon: str = Query(default="H6"),
) -> dict:
    context = report_context_service.resolve(
        report_month=report_month,
        run_date=run_date,
        horizon=horizon,
        manufacturer_code=manufacturer_code,
        user_id=user_id,
    )
    try:
        return _with_report_context(
            service.risk_entity_detail(entity_id, horizon=context.get("effective_horizon") or horizon),
            context,
        )
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
    report_context_service: ReportContextService = Depends(get_report_context_service),
    x_user_id: Annotated[str | None, Header()] = None,
    user_id: str | None = Query(default=None),
    report_month: str | None = Query(default=None),
    run_date: str | None = Query(default=None),
    horizon: str | None = Query(default=None),
    manufacturer_code: Annotated[list[str] | None, Query()] = None,
) -> dict:
    context = report_context_service.resolve(
        report_month=report_month,
        run_date=run_date,
        horizon=horizon,
        manufacturer_code=_first_query_value(manufacturer_code),
        user_id=user_id or x_user_id,
    )
    payload = top_entity_service.list_visible_manufacturers(
        user_id=user_id or x_user_id or "admin",
        report_month=context.get("effective_report_month") or report_month,
        manufacturer_codes=manufacturer_code,
    )
    if not context.get("ready"):
        payload = {
            **payload,
            "ready": False,
            "scope_source": "result_batch_unavailable",
            "warnings": [
                *list(payload.get("warnings") or []),
                "RISK_RESULT_BATCH_DIR_NOT_CONFIGURED_OR_UNREADABLE",
            ],
        }
    return _with_report_context(payload, context)


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


def _with_report_context(payload: dict, report_context: dict) -> dict:
    return {
        **payload,
        "report_context": report_context,
        "requested_report_month": report_context.get("requested_report_month"),
        "effective_report_month": report_context.get("effective_report_month"),
        "requested_run_date": report_context.get("requested_run_date"),
        "effective_run_date": report_context.get("effective_run_date"),
        "date_resolution_status": report_context.get("date_resolution_status"),
    }


def _first_query_value(values: list[str] | None) -> str | None:
    return values[0] if values else None


def _detector_summary(
    detector_service: DetectorResultService,
    *,
    run_date: str | None,
    manufacturer_codes: list[str] | None,
) -> dict[str, object]:
    runs = detector_service.runs(run_date=run_date, limit=1)
    latest = runs.get("items", [{}])[0] if runs.get("items") else {}
    clues = detector_service.clues(run_date=run_date, sort_by="detector_score", page=1, page_size=200)
    items = clues.get("items", [])
    if manufacturer_codes:
        allowed = {str(code) for code in manufacturer_codes}
        items = [item for item in items if str(item.get("manufacturer_code")) in allowed]
    scores = [
        float(item["detector_score"])
        for item in items
        if item.get("detector_score") is not None
    ]
    return {
        "detector_clue_count": len(items),
        "highest_detector_score": max(scores) if scores else None,
        "latest_detector_run_date": latest.get("run_date"),
        "detector_status_summary": "ready" if latest else "missing",
        "top_clues": items[:5],
    }
