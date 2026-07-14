from __future__ import annotations

import os
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.api.routes_display_lookup import get_display_lookup_service
from app.api.routes_detector_results import get_detector_result_service
from app.api.routes_report_context import get_report_context_service
from app.api.routes_user_top_entities import get_user_top_entity_service
from app.schemas.frontend_pages import (
    MonthlyReportsPayload,
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
from app.services.user_top_entity_service import HorizonNotAvailable, SortMetricUnavailable, TopEntityService

router = APIRouter(prefix="/api/v1", tags=["frontend-pages"])
ALLOWED_CANDIDATE_SORT_FIELDS = {"loss_value", "risk_probability", "involved_amount"}
ALLOWED_SORT_ORDERS = {"asc", "desc"}


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
    observation_date: str | None = Query(default=None),
    report_month: str | None = Query(default=None),
    run_date: str | None = Query(default=None),
    manual_report_month: bool = Query(default=False),
    horizon: str = Query(default="H6"),
    top_n: int = Query(default=20, ge=1, le=100),
    sort_by: str = Query(default="risk_probability"),
    sort_order: str = Query(default="desc"),
) -> dict:
    sort_by, sort_order = _validate_candidate_sort(sort_by, sort_order)
    context = report_context_service.resolve(
        observation_date=observation_date,
        report_month=report_month,
        run_date=run_date,
        horizon=horizon,
        manufacturer_code=_first_query_value(manufacturer_code),
        user_id=user_id or x_user_id,
        manual_report_month=manual_report_month,
    )
    effective_report_month = context.get("effective_report_month") or report_month
    effective_run_date = context.get("effective_run_date") or run_date
    effective_horizon = context.get("effective_horizon") or horizon
    contextual_top_entity_service = _top_entity_service_for_context(
        top_entity_service,
        report_context_service,
        context,
    )
    _assert_horizon_available(contextual_top_entity_service, horizon)
    contextual_display_lookup_service = _display_lookup_service_for_context(
        display_lookup_service,
        report_context_service,
        context,
    )
    contextual_detector_service = _detector_service_for_context(
        detector_service,
        report_context_service,
        context,
    )
    effective_manufacturer_codes = _effective_requested_manufacturer_codes(
        contextual_top_entity_service,
        user_id=user_id or x_user_id or "admin",
        report_month=_report_month_for_top_entity_service(
            contextual_top_entity_service,
            effective_report_month,
            report_month,
        ),
        requested_manufacturer_codes=manufacturer_code,
    )
    if not context.get("probability_batch_available", context.get("ready")):
        if os.getenv("ALLOW_MOCK_PAYLOADS", "").lower() == "true":
            return _with_report_context(
                _with_display_lookup_status(service.workbench(), contextual_display_lookup_service),
                context,
            )
        return _with_report_context(
            _with_display_lookup_status(
                _unavailable_workbench_payload(
                    context,
                    user_id=user_id or x_user_id or "admin",
                    top_n=top_n,
                    horizon=effective_horizon,
                    sort_by=sort_by,
                    manufacturer_codes=manufacturer_code,
                ),
                contextual_display_lookup_service,
            ),
            context,
        )
    try:
        payload = build_workbench_payload_from_top_entities(
            contextual_top_entity_service,
            user_id=user_id or x_user_id or "admin",
            top_n=top_n,
            horizon=effective_horizon,
            report_month=_report_month_for_top_entity_service(
                contextual_top_entity_service,
                effective_report_month,
                report_month,
            ),
            manufacturer_codes=manufacturer_code,
            sort_by=sort_by,
            sort_order=sort_order,
            detector_summary=_detector_summary(
                contextual_detector_service,
                run_date=effective_run_date,
                manufacturer_codes=effective_manufacturer_codes,
            ),
            run_date=effective_run_date,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail={"error_code": str(exc)}) from exc
    except SortMetricUnavailable as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "SORT_METRIC_NOT_AVAILABLE",
                "requested_sort_by": exc.requested_sort_by,
            },
        ) from exc
    except HorizonNotAvailable as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "HORIZON_NOT_AVAILABLE",
                "requested_horizon": exc.requested_horizon,
                "available_horizons": exc.available_horizons,
            },
        ) from exc
    return _with_report_context(
        _with_display_lookup_status(payload, contextual_display_lookup_service),
        context,
    )


@router.get("/risk-entities", response_model=RiskEntitiesPayload)
def frontend_risk_entities(
    service: FrontendPageService = Depends(get_frontend_page_service),
    top_entity_service: TopEntityService = Depends(get_user_top_entity_service),
    display_lookup_service: DisplayLookupService = Depends(get_display_lookup_service),
    report_context_service: ReportContextService = Depends(get_report_context_service),
    x_user_id: Annotated[str | None, Header()] = None,
    user_id: str | None = Query(default=None),
    manufacturer_code: Annotated[list[str] | None, Query()] = None,
    observation_date: str | None = Query(default=None),
    report_month: str | None = Query(default=None),
    run_date: str | None = Query(default=None),
    manual_report_month: bool = Query(default=False),
    horizon: str = Query(default="H6"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=1000),
    sort_by: str = Query(default="risk_probability"),
    sort_order: str = Query(default="desc"),
) -> dict:
    sort_by, sort_order = _validate_candidate_sort(sort_by, sort_order)
    context = report_context_service.resolve(
        observation_date=observation_date,
        report_month=report_month,
        run_date=run_date,
        horizon=horizon,
        manufacturer_code=_first_query_value(manufacturer_code),
        user_id=user_id or x_user_id,
        manual_report_month=manual_report_month,
    )
    contextual_top_entity_service = _top_entity_service_for_context(
        top_entity_service,
        report_context_service,
        context,
    )
    _assert_horizon_available(contextual_top_entity_service, horizon)
    contextual_display_lookup_service = _display_lookup_service_for_context(
        display_lookup_service,
        report_context_service,
        context,
    )
    try:
        top_entity_payload = build_risk_entities_payload_from_top_entities(
            contextual_top_entity_service,
            user_id=user_id or x_user_id or "admin",
            page=page,
            page_size=page_size,
            horizon=context.get("effective_horizon") or horizon,
            report_month=_report_month_for_top_entity_service(
                contextual_top_entity_service,
                context.get("effective_report_month"),
                report_month,
            ),
            manufacturer_codes=manufacturer_code,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail={"error_code": str(exc)}) from exc
    except SortMetricUnavailable as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "SORT_METRIC_NOT_AVAILABLE",
                "requested_sort_by": exc.requested_sort_by,
            },
        ) from exc
    except HorizonNotAvailable as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "HORIZON_NOT_AVAILABLE",
                "requested_horizon": exc.requested_horizon,
                "available_horizons": exc.available_horizons,
            },
        ) from exc
    return _with_report_context(_with_display_lookup_status(top_entity_payload, contextual_display_lookup_service), context)


@router.get("/risk-entities/{entity_id}", response_model=RiskEntityDetailPayload)
def frontend_risk_entity_detail(
    entity_id: str,
    service: FrontendPageService = Depends(get_frontend_page_service),
    top_entity_service: TopEntityService = Depends(get_user_top_entity_service),
    report_context_service: ReportContextService = Depends(get_report_context_service),
    x_user_id: Annotated[str | None, Header()] = None,
    observation_date: str | None = Query(default=None),
    report_month: str | None = Query(default=None),
    run_date: str | None = Query(default=None),
    manual_report_month: bool = Query(default=False),
    manufacturer_code: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    horizon: str = Query(default="H6"),
) -> dict:
    context = report_context_service.resolve(
        observation_date=observation_date,
        report_month=report_month,
        run_date=run_date,
        horizon=horizon,
        manufacturer_code=manufacturer_code,
        user_id=user_id,
        manual_report_month=manual_report_month,
    )
    contextual_page_service = _frontend_page_service_for_context(service, report_context_service, context)
    try:
        _assert_entity_scope(
            contextual_page_service,
            top_entity_service,
            entity_id=entity_id,
            manufacturer_code=manufacturer_code,
            user_id=user_id or x_user_id or "admin",
        )
        return _with_report_context(
            contextual_page_service.risk_entity_detail(entity_id, horizon=context.get("effective_horizon") or horizon),
            context,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown risk entity: {entity_id}") from exc


@router.get("/risk-entities/{entity_id}/probability-trend")
def frontend_risk_entity_probability_trend(
    entity_id: str,
    service: FrontendPageService = Depends(get_frontend_page_service),
    top_entity_service: TopEntityService = Depends(get_user_top_entity_service),
    report_context_service: ReportContextService = Depends(get_report_context_service),
    x_user_id: Annotated[str | None, Header()] = None,
    observation_date: str | None = Query(default=None),
    report_month: str | None = Query(default=None),
    run_date: str | None = Query(default=None),
    manual_report_month: bool = Query(default=False),
    manufacturer_code: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    horizon: str = Query(default="H6"),
) -> dict:
    context = report_context_service.resolve(
        observation_date=observation_date,
        report_month=report_month,
        run_date=run_date,
        horizon=horizon,
        manufacturer_code=manufacturer_code,
        user_id=user_id,
        manual_report_month=manual_report_month,
    )
    contextual_page_service = _frontend_page_service_for_context(service, report_context_service, context)
    try:
        _assert_entity_scope(
            contextual_page_service,
            top_entity_service,
            entity_id=entity_id,
            manufacturer_code=manufacturer_code,
            user_id=user_id or x_user_id or "admin",
        )
        return _with_report_context(
            contextual_page_service.probability_trend(
                entity_id,
                horizon=context.get("effective_horizon") or horizon,
            ),
            context,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown risk entity: {entity_id}") from exc


@router.get("/my/manufacturers")
def my_manufacturers(
    top_entity_service: TopEntityService = Depends(get_user_top_entity_service),
    report_context_service: ReportContextService = Depends(get_report_context_service),
    x_user_id: Annotated[str | None, Header()] = None,
    user_id: str | None = Query(default=None),
    observation_date: str | None = Query(default=None),
    report_month: str | None = Query(default=None),
    run_date: str | None = Query(default=None),
    manual_report_month: bool = Query(default=False),
    horizon: str | None = Query(default=None),
    manufacturer_code: Annotated[list[str] | None, Query()] = None,
) -> dict:
    context = report_context_service.resolve(
        observation_date=observation_date,
        report_month=report_month,
        run_date=run_date,
        horizon=horizon,
        manufacturer_code=None,
        user_id=user_id or x_user_id,
        manual_report_month=manual_report_month,
    )
    payload = top_entity_service.list_visible_manufacturers(
        user_id=user_id or x_user_id or "admin",
        report_month=None,
        manufacturer_codes=None,
    )
    return _with_report_context(payload, context)


@router.get("/oneshot-terminals")
def frontend_oneshot_terminals(
    service: FrontendPageService = Depends(get_frontend_page_service),
    report_context_service: ReportContextService = Depends(get_report_context_service),
    observation_date: str | None = Query(default=None),
    report_month: str | None = Query(default=None),
    run_date: str | None = Query(default=None),
    manual_report_month: bool = Query(default=False),
    manufacturer_code: Annotated[list[str] | None, Query()] = None,
    user_id: str | None = Query(default=None),
    horizon: str = Query(default="H6"),
    top_n: int = Query(default=20, ge=1, le=100),
) -> dict:
    context = report_context_service.resolve(
        observation_date=observation_date,
        report_month=report_month,
        run_date=run_date,
        horizon=horizon,
        manufacturer_code=_first_query_value(manufacturer_code),
        user_id=user_id,
        manual_report_month=manual_report_month,
    )
    contextual_page_service = _frontend_page_service_for_context(service, report_context_service, context)
    payload = contextual_page_service.oneshot_terminals(
        manufacturer_codes=manufacturer_code,
        report_month=context.get("effective_report_month") or report_month,
        observation_date=context.get("observation_date") or context.get("effective_observation_date"),
        top_n=top_n,
    )
    return _with_report_context(payload, context)


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
    enriched = {
        **payload,
        "report_context": report_context,
        "observation_date": report_context.get("observation_date"),
        "probability_report_month": report_context.get("probability_report_month"),
        "expected_probability_report_month": report_context.get("expected_probability_report_month"),
        "effective_probability_report_month": report_context.get("effective_probability_report_month"),
        "probability_batch_available": report_context.get("probability_batch_available"),
        "detector_run_date": report_context.get("detector_run_date"),
        "detector_run_available": report_context.get("detector_run_available"),
        "context_status": report_context.get("context_status"),
        "manual_selection_required": report_context.get("manual_selection_required"),
        "partial_ready": report_context.get("partial_ready", False),
        "requested_report_month": report_context.get("requested_report_month"),
        "effective_report_month": report_context.get("effective_report_month"),
        "effective_observation_date": report_context.get("effective_observation_date"),
        "requested_run_date": report_context.get("requested_run_date"),
        "effective_run_date": report_context.get("effective_run_date"),
        "date_resolution_status": report_context.get("date_resolution_status"),
    }
    if "rows" in enriched:
        rows = list(enriched.get("rows") or [])
        summary = dict(enriched.get("detector_summary") or {})
        detector_ready = bool(report_context.get("detector_run_available"))
        summary.setdefault("ready", detector_ready)
        summary.setdefault("partial_ready", bool(report_context.get("partial_ready")))
        summary.setdefault("detector_run_date", report_context.get("detector_run_date"))
        summary.setdefault("context_status", report_context.get("context_status"))
        if not detector_ready:
            summary["detector_clue_count"] = 0
            summary["highest_detector_score"] = None
            summary["top_clues"] = []
        enriched["current_observation_date"] = (
            report_context.get("observation_date")
            or report_context.get("effective_observation_date")
            or report_context.get("effective_run_date")
            or report_context.get("detector_run_date")
        )
        enriched.setdefault("risk_entities", rows)
        enriched["daily_detector_summary"] = summary
        enriched.setdefault("top_rule_clues", list(summary.get("top_clues") or [])[:5])
        enriched.setdefault(
            "today_focus",
            {
                "observation_date": report_context.get("observation_date"),
                "probability_report_month": report_context.get("probability_report_month"),
                "detector_run_date": report_context.get("detector_run_date"),
                "context_status": report_context.get("context_status"),
            },
        )
    return enriched


def _top_entity_service_for_context(
    service: TopEntityService,
    report_context_service: ReportContextService,
    context: dict,
) -> TopEntityService:
    if _is_in_memory_repository(service.repository):
        return service
    repository = report_context_service.probability_repository(context)
    if repository is None:
        return service
    return TopEntityService(repository, scope_service=service.scope_service)


def _display_lookup_service_for_context(
    service: DisplayLookupService,
    report_context_service: ReportContextService,
    context: dict,
) -> DisplayLookupService:
    if _is_in_memory_repository(service.repository):
        return service
    repository = report_context_service.probability_repository(context)
    return DisplayLookupService(repository) if repository is not None else service


def _detector_service_for_context(
    service: DetectorResultService,
    report_context_service: ReportContextService,
    context: dict,
) -> DetectorResultService:
    if _is_in_memory_repository(service.repository):
        return service
    repository = report_context_service.detector_repository(context)
    return DetectorResultService(repository) if repository is not None else service


def _frontend_page_service_for_context(
    service: FrontendPageService,
    report_context_service: ReportContextService,
    context: dict,
) -> FrontendPageService:
    if service._repository is not None and _is_in_memory_repository(service._repository):
        return service
    repository = report_context_service.probability_repository(context)
    return FrontendPageService(repository=repository) if repository is not None else service


def _unavailable_workbench_payload(
    context: dict,
    *,
    user_id: str,
    top_n: int,
    horizon: str,
    sort_by: str,
    manufacturer_codes: list[str] | None,
) -> dict:
    return {
        "ready": False,
        "data_source": "unavailable",
        "demo_mode": False,
        "batch_context": {
            "report_month": context.get("probability_report_month") or "",
            "score_as_of_date": context.get("probability_report_month") or "",
            "data_watermark_at": context.get("observation_date") or "",
            "score_batch_id": context.get("probability_batch_id") or "",
            "result_batch_id": context.get("probability_batch_id") or "",
            "primary_horizon": horizon or "H6",
            "primary_horizon_label": horizon or "H6",
            "involved_amount_definition": "selected horizon window consumption",
        },
        "overview_metrics": [],
        "rows": [],
        "scope": {"manufacturer_count": 0, "manufacturer_codes": manufacturer_codes or []},
        "query": {"horizon": horizon, "top_n": top_n, "sort_by": sort_by},
        "detector_summary": {
            "detector_clue_count": 0,
            "latest_detector_run_date": context.get("detector_run_date"),
            "detector_status_summary": context.get("context_status"),
        },
        "current_user_id": user_id,
        "current_manufacturer_code": _first_query_value(manufacturer_codes),
        "current_observation_date": context.get("observation_date"),
        "horizon": horizon,
        "top_n": top_n,
        "sort_by": sort_by,
        "today_clue_count": 0,
        "highest_detector_score": None,
        "priority_risk_entity_count": 0,
        "today_high_score_rule_clues": [],
        "monthly_risk_entities": [],
        "warnings": list(context.get("warnings") or []),
    }


def _is_in_memory_repository(repository: object) -> bool:
    return repository.__class__.__name__ == "InMemoryRiskResultRepository"


def _report_month_for_top_entity_service(
    service: TopEntityService,
    effective_report_month: str | None,
    requested_report_month: str | None,
) -> str | None:
    return effective_report_month or requested_report_month


def _first_query_value(values: list[str] | None) -> str | None:
    return values[0] if values else None


def _validate_candidate_sort(sort_by: str, sort_order: str) -> tuple[str, str]:
    normalized_sort = str(sort_by or "").strip()
    normalized_order = str(sort_order or "").strip().lower()
    if normalized_sort not in ALLOWED_CANDIDATE_SORT_FIELDS:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "SORT_METRIC_NOT_AVAILABLE",
                "requested_sort_by": normalized_sort,
                "allowed_sort_by": sorted(ALLOWED_CANDIDATE_SORT_FIELDS),
            },
        )
    if normalized_order not in ALLOWED_SORT_ORDERS:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "SORT_ORDER_NOT_AVAILABLE",
                "requested_sort_order": normalized_order,
                "allowed_sort_order": sorted(ALLOWED_SORT_ORDERS),
            },
        )
    return normalized_sort, normalized_order


def _assert_horizon_available(top_entity_service: TopEntityService, horizon: str | None) -> None:
    requested = str(horizon or "").strip()
    if not requested:
        return
    try:
        available = getattr(top_entity_service.repository.manifest(), "available_horizons", None) or []
    except (FileNotFoundError, NotImplementedError, ValueError, AttributeError):
        available = []
    available_horizons = [str(item) for item in available]
    if available_horizons and requested not in available_horizons:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "HORIZON_NOT_AVAILABLE",
                "requested_horizon": requested,
                "available_horizons": available_horizons,
            },
        )


def _assert_entity_scope(
    page_service: FrontendPageService,
    top_entity_service: TopEntityService,
    *,
    entity_id: str,
    manufacturer_code: str | None,
    user_id: str,
) -> None:
    repository = getattr(page_service, "_repository", None)
    if repository is None and getattr(page_service, "_builder", None) is not None:
        repository = page_service._builder.repository
    if repository is None:
        raise KeyError(entity_id)
    entity = repository.get_risk_entity(entity_id)
    if entity is None:
        raise KeyError(entity_id)
    entity_manufacturer = str(entity.get("manufacturer_code") or "")
    if manufacturer_code and entity_manufacturer != str(manufacturer_code):
        raise HTTPException(status_code=403, detail={"error_code": "MANUFACTURER_SCOPE_FORBIDDEN"})
    visible = top_entity_service.list_visible_manufacturers(user_id=user_id, report_month=None, manufacturer_codes=None)
    allowed = {str(item.get("manufacturer_code")) for item in visible.get("manufacturers", [])}
    if allowed and entity_manufacturer not in allowed:
        raise HTTPException(status_code=403, detail={"error_code": "MANUFACTURER_SCOPE_FORBIDDEN"})


def _effective_requested_manufacturer_codes(
    top_entity_service: TopEntityService,
    *,
    user_id: str,
    report_month: str | None,
    requested_manufacturer_codes: list[str] | None,
) -> list[str] | None:
    requested = [str(code) for code in requested_manufacturer_codes or [] if str(code).strip()]
    if not requested:
        return None
    entities = top_entity_service.repository.list_risk_entities()
    if report_month and not entities.empty and "report_month" in entities.columns:
        entities = entities[entities["report_month"].astype(str).eq(str(report_month))]
    available_codes = (
        entities.get("manufacturer_code")
        .dropna()
        .astype(str)
        .drop_duplicates()
        .tolist()
        if not entities.empty and "manufacturer_code" in entities.columns
        else []
    )
    scope, _ = top_entity_service.scope_service.resolve_scope(
        user_id=user_id,
        requested_manufacturer_codes=requested,
        available_manufacturer_codes=available_codes,
    )
    return [item.manufacturer_code for item in scope]


def _detector_summary(
    detector_service: DetectorResultService,
    *,
    run_date: str | None,
    manufacturer_codes: list[str] | None,
) -> dict[str, object]:
    runs = detector_service.runs(run_date=run_date, limit=1)
    latest = runs.get("items", [{}])[0] if runs.get("items") else {}
    clues = detector_service.clues(
        run_date=run_date,
        manufacturer_code=manufacturer_codes[0] if manufacturer_codes and len(manufacturer_codes) == 1 else None,
        sort_by="detector_score",
        page=1,
        page_size=200,
    )
    items = clues.get("items", [])
    if manufacturer_codes:
        allowed = {str(code) for code in manufacturer_codes}
        items = [item for item in items if str(item.get("manufacturer_code")) in allowed]
    clue_count = int(clues.get("total") or len(items))
    scores = [
        float(item["detector_score"])
        for item in items
        if item.get("detector_score") is not None
    ]
    return {
        "detector_clue_count": clue_count,
        "highest_detector_score": max(scores) if scores else None,
        "latest_detector_run_date": latest.get("run_date"),
        "detector_status_summary": "ready" if latest else "missing",
        "top_clues": items[:5],
    }
