from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas.detector_results import (
    DailyDetectorCluesResponse,
    DailyDetectorClueDetailResponse,
    DailyDetectorRunsResponse,
    DailyDetectorResultsResponse,
    DailyDetectorStatusResponse,
    DetectorCatalogResponse,
    DetectorConfigStatusResponse,
    DetectorEntityDetailResponse,
    DetectorEventAggregatesResponse,
    RiskEntityDetectorEvidenceResponse,
)
from app.services.detector_result_service import (
    DetectorResultService,
    build_default_detector_result_service,
)
from app.api.routes_report_context import get_report_context_service
from app.services.report_context_service import ReportContextService

router = APIRouter(prefix="/api/v1", tags=["detector-results"])
logger = logging.getLogger(__name__)


def _is_true(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def get_detector_result_service() -> DetectorResultService:
    return build_default_detector_result_service()


@router.get("/detectors/catalog", response_model=DetectorCatalogResponse)
def detector_catalog(
    service: Annotated[DetectorResultService, Depends(get_detector_result_service)],
) -> dict:
    return service.catalog()


@router.get("/detectors/runs", response_model=DailyDetectorRunsResponse)
def detector_runs(
    service: Annotated[DetectorResultService, Depends(get_detector_result_service)],
    report_month: str | None = None,
    run_date: str | None = None,
    limit: int = Query(default=20, ge=1, le=200),
) -> dict:
    return service.runs(report_month=report_month, run_date=run_date, limit=limit)


@router.get("/daily-detector/dates")
def daily_detector_dates(
    service: Annotated[DetectorResultService, Depends(get_detector_result_service)],
    report_context_service: Annotated[ReportContextService, Depends(get_report_context_service)],
    report_month: str | None = None,
    limit: int = Query(default=500, ge=1, le=500),
) -> dict:
    if report_context_service.repository is None or report_context_service.batch_root is None:
        return service.run_dates(report_month=report_month, limit=limit)

    try:
        contexts = report_context_service.repository.list_available_observation_contexts(
            batch_root=report_context_service.batch_root,
        )
    except (FileNotFoundError, ValueError, KeyError, NotImplementedError, AttributeError):
        return service.run_dates(report_month=report_month, limit=limit)
    if contexts.empty or "detector_run_date" not in contexts:
        return service.run_dates(report_month=report_month, limit=limit)

    available = contexts.copy()
    if "detector_run_available" in available:
        available = available.loc[available["detector_run_available"].map(_is_true)]
    if report_month and "probability_report_month" in available:
        available = available.loc[
            available["probability_report_month"].astype(str).eq(str(report_month))
        ]
    available = available.sort_values("detector_run_date", ascending=False)
    available = available.drop_duplicates(subset=["detector_run_date"]).head(limit)
    items = [
        {
            "detector_run_id": str(row.get("detector_run_id") or ""),
            "run_date": str(row.get("detector_run_date") or ""),
            "report_month": str(row.get("probability_report_month") or ""),
            "status": "ready",
            "detector_config_version": None,
            "clue_count": None,
            "attached_high_risk_count": None,
        }
        for _, row in available.iterrows()
    ]
    return {
        "ready": bool(items),
        "source": "observation_registry",
        "items": items,
        "semantic_caveats": [
            "Detector dates are exact immutable daily facts; monthly model probabilities do not change daily."
        ],
        "warnings": [] if items else ["DAILY_DETECTOR_RESULT_BATCH_NOT_AVAILABLE"],
    }


@router.get("/daily-detector/status", response_model=DailyDetectorStatusResponse)
def daily_detector_status(
    service: Annotated[DetectorResultService, Depends(get_detector_result_service)],
    report_context_service: Annotated[ReportContextService, Depends(get_report_context_service)],
    observation_date: str | None = None,
    report_month: str | None = None,
    run_date: str | None = None,
    manual_report_month: bool = False,
    horizon: str | None = None,
    manufacturer_code: str | None = None,
    user_id: str | None = None,
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
    if not context.get("detector_run_available"):
        return _with_report_context(
            _missing_detector_status_payload(context),
            context,
        )
    contextual_service = _detector_service_for_context(service, report_context_service, context)
    return _with_report_context(
        contextual_service.status(
            report_month=context.get("effective_report_month") or report_month,
            run_date=context.get("effective_run_date") or run_date,
            manufacturer_code=manufacturer_code,
        ),
        context,
    )


@router.get("/detectors/clues", response_model=DailyDetectorCluesResponse)
def detector_clues(
    service: Annotated[DetectorResultService, Depends(get_detector_result_service)],
    detector_run_id: str | None = None,
    run_date: str | None = None,
    detector_id: str | None = None,
    detector_family: str | None = None,
    detector_category: str | None = None,
    detector_level: str | None = None,
    manufacturer_code: str | None = None,
    hospital_code: str | None = None,
    drug_group: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    sort_by: str = Query(default="detector_score"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
) -> dict:
    return service.clues(
        detector_run_id=detector_run_id,
        run_date=run_date,
        detector_id=detector_id,
        detector_family=detector_family,
        detector_category=detector_category,
        detector_level=detector_level,
        manufacturer_code=manufacturer_code,
        hospital_code=hospital_code,
        drug_group=drug_group,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get("/detectors/results", response_model=DailyDetectorResultsResponse)
def detector_results(
    service: Annotated[DetectorResultService, Depends(get_detector_result_service)],
    observation_date: str | None = None,
    detector_id: str | None = None,
    detector_family: str | None = None,
    manufacturer_code: str | None = None,
    hospital_code: str | None = None,
    drug_code: str | None = None,
    eligibility_status: str | None = None,
    hit_flag: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> dict:
    return service.results(
        observation_date=observation_date,
        detector_id=detector_id,
        detector_family=detector_family,
        manufacturer_code=manufacturer_code,
        hospital_code=hospital_code,
        drug_code=drug_code,
        eligibility_status=eligibility_status,
        hit_flag=hit_flag,
        page=page,
        page_size=page_size,
    )


@router.get("/detectors/event-aggregates", response_model=DetectorEventAggregatesResponse)
def detector_event_aggregates(
    service: Annotated[DetectorResultService, Depends(get_detector_result_service)],
    observation_date: str,
    manufacturer_code: str | None = None,
    hospital_code: str | None = None,
    drug_code: str | None = None,
    historical_detector_id: str | None = None,
    sort_by: str = Query(default="current_detector_count"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> dict:
    return service.event_aggregates(
        observation_date=observation_date,
        manufacturer_code=manufacturer_code,
        hospital_code=hospital_code,
        drug_code=drug_code,
        historical_detector_id=historical_detector_id,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )


@router.get("/daily-detector/clues", response_model=DailyDetectorCluesResponse)
def daily_detector_clues(
    service: Annotated[DetectorResultService, Depends(get_detector_result_service)],
    report_context_service: Annotated[ReportContextService, Depends(get_report_context_service)],
    observation_date: str | None = None,
    report_month: str | None = None,
    run_date: str | None = None,
    manual_report_month: bool = False,
    manufacturer_code: str | None = None,
    horizon: str | None = None,
    top_n: int | None = Query(default=None, ge=1, le=200),
    sort_by: str = Query(default="detector_score"),
    detector_id: str | None = None,
    detector_family: str | None = None,
    detector_category: str | None = None,
    detector_level: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    limit: int | None = Query(default=None, ge=1, le=200),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
) -> dict:
    context = report_context_service.resolve(
        observation_date=observation_date,
        report_month=report_month,
        run_date=run_date,
        horizon=horizon,
        manufacturer_code=manufacturer_code,
        user_id=None,
        manual_report_month=manual_report_month,
    )
    if not context.get("detector_run_available"):
        return _with_report_context(
            _missing_detector_clues_payload(context, page=page, page_size=top_n or limit or page_size),
            context,
        )
    contextual_service = _detector_service_for_context(service, report_context_service, context)
    return _with_report_context(contextual_service.clues(
        run_date=context.get("effective_run_date") or run_date,
        manufacturer_code=manufacturer_code,
        horizon=context.get("effective_horizon") or horizon,
        sort_by=sort_by,
        detector_id=detector_id,
        detector_family=detector_family,
        detector_category=detector_category,
        detector_level=detector_level,
        page=page,
        page_size=top_n or limit or page_size,
        sort_order=sort_order,
    ), context)


@router.get(
    "/detectors/entity-detail",
    response_model=DetectorEntityDetailResponse,
)
def detector_entity_detail(
    service: Annotated[DetectorResultService, Depends(get_detector_result_service)],
    report_context_service: Annotated[ReportContextService, Depends(get_report_context_service)],
    observation_date: str,
    manufacturer_code: str,
    hospital_code: str,
    drug_code: str,
    clue_id: str | None = None,
    report_month: str | None = None,
    manual_report_month: bool = False,
    horizon: str = "H6",
) -> dict:
    context = report_context_service.resolve(
        observation_date=observation_date,
        report_month=report_month,
        run_date=observation_date,
        horizon=horizon,
        manufacturer_code=manufacturer_code,
        user_id=None,
        manual_report_month=manual_report_month,
    )
    if not context.get("detector_run_available"):
        raise HTTPException(status_code=404, detail="Detector run is unavailable for this observation date")
    contextual_service = _detector_service_for_context(service, report_context_service, context)
    payload = contextual_service.entity_detail(
        observation_date=context.get("effective_run_date") or observation_date,
        manufacturer_code=manufacturer_code,
        hospital_code=hospital_code,
        drug_code=drug_code,
        clue_id=clue_id,
        probability_repository=report_context_service.probability_repository(context),
        probability_batch_root=report_context_service.batch_root,
        horizon=context.get("effective_horizon") or horizon,
    )
    return _with_report_context(payload, context)


@router.get(
    "/detectors/clues/{detector_clue_id}",
    response_model=DailyDetectorClueDetailResponse,
)
def detector_clue_detail(
    detector_clue_id: str,
    service: Annotated[DetectorResultService, Depends(get_detector_result_service)],
    detector_run_id: str | None = None,
    run_date: str | None = None,
    manufacturer_code: str | None = None,
) -> dict:
    try:
        return service.clue_detail(
            detector_clue_id=detector_clue_id,
            detector_run_id=detector_run_id,
            run_date=run_date,
            manufacturer_code=manufacturer_code,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Detector clue not found") from exc
    except ValueError as exc:
        logger.exception("Detector clue detail lookup returned duplicate rows", extra={"detector_clue_id": detector_clue_id})
        raise HTTPException(status_code=500, detail="Detector clue detail is unavailable") from exc


@router.get(
    "/risk-entities/{risk_entity_id}/detector-evidence",
    response_model=RiskEntityDetectorEvidenceResponse,
)
def risk_entity_detector_evidence(
    risk_entity_id: str,
    service: Annotated[DetectorResultService, Depends(get_detector_result_service)],
    report_context_service: Annotated[ReportContextService, Depends(get_report_context_service)],
    observation_date: str | None = None,
    report_month: str | None = None,
    detector_run_id: str | None = None,
    run_date: str | None = None,
    manual_report_month: bool = False,
    horizon: str | None = None,
    manufacturer_code: str | None = None,
    user_id: str | None = None,
    detector_family: str | None = None,
    detector_id: str | None = None,
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
    contextual_service = _detector_service_for_context(service, report_context_service, context)
    _assert_risk_entity_manufacturer_scope(
        contextual_service,
        risk_entity_id=risk_entity_id,
        manufacturer_code=manufacturer_code,
    )
    evidence_run_date = (
        run_date
        if contextual_service.repository.__class__.__name__ == "InMemoryRiskResultRepository"
        else context.get("effective_run_date") or run_date
    )
    try:
        payload = contextual_service.risk_entity_detector_evidence(
            risk_entity_id=risk_entity_id,
            detector_run_id=detector_run_id,
            run_date=detector_run_id and run_date or evidence_run_date,
            detector_family=detector_family,
            detector_id=detector_id,
        )
        return _with_report_context(payload, context)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"Unknown risk entity: {risk_entity_id}"
        ) from exc


@router.get("/detectors/config-status", response_model=DetectorConfigStatusResponse)
def detector_config_status(
    service: Annotated[DetectorResultService, Depends(get_detector_result_service)],
) -> dict:
    return service.config_status()


def _with_report_context(payload: dict, report_context: dict) -> dict:
    return {
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


def _detector_service_for_context(
    service: DetectorResultService,
    report_context_service: ReportContextService,
    context: dict,
) -> DetectorResultService:
    if service.repository.__class__.__name__ == "InMemoryRiskResultRepository":
        return service
    repository = report_context_service.detector_repository(context)
    return DetectorResultService(repository) if repository is not None else service


def _assert_risk_entity_manufacturer_scope(
    service: DetectorResultService,
    *,
    risk_entity_id: str,
    manufacturer_code: str | None,
) -> None:
    entity = service.repository.get_risk_entity(risk_entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail=f"Unknown risk entity: {risk_entity_id}")
    if not manufacturer_code:
        return
    effective_manufacturer = str(entity.get("manufacturer_code") or "")
    if effective_manufacturer != str(manufacturer_code):
        raise HTTPException(
            status_code=403,
            detail={"error_code": "MANUFACTURER_SCOPE_FORBIDDEN"},
        )


def _missing_detector_status_payload(context: dict) -> dict:
    return {
        "ready": False,
        "data_source": "risk_model_core",
        "run_date": context.get("detector_run_date"),
        "detector_run_id": context.get("detector_run_id"),
        "detector_config_version": None,
        "clue_count": 0,
        "attached_high_risk_count": 0,
        "highest_detector_score": None,
        "enabled_detectors": None,
        "config_effective_note": "规则参数调整后，将在下一次巡检运行后生效，历史结果不会被静默改写。",
        "source": "risk_model_core",
        "warnings": list(context.get("warnings") or ["DETECTOR_RUN_NOT_AVAILABLE"]),
    }


def _missing_detector_clues_payload(context: dict, *, page: int, page_size: int) -> dict:
    return {
        "ready": False,
        "source": "risk_model_core",
        "data_source": "risk_model_core",
        "items": [],
        "clues": [],
        "total": 0,
        "run_date": context.get("detector_run_date"),
        "detector_run_id": context.get("detector_run_id"),
        "pagination": {"page": page, "page_size": page_size, "total": 0},
        "semantic_caveats": [
            "detector_score is rule inspection score, not probability",
            "daily detector clues do not create risk_entities",
        ],
        "warnings": list(context.get("warnings") or ["DETECTOR_RUN_NOT_AVAILABLE"]),
    }
