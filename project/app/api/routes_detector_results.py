from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas.detector_results import (
    DailyDetectorCluesResponse,
    DailyDetectorRunsResponse,
    DailyDetectorStatusResponse,
    DetectorCatalogResponse,
    DetectorConfigStatusResponse,
    RiskEntityDetectorEvidenceResponse,
)
from app.services.detector_result_service import (
    DetectorResultService,
    build_default_detector_result_service,
)

router = APIRouter(prefix="/api/v1", tags=["detector-results"])


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
    report_month: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    return service.run_dates(report_month=report_month, limit=limit)


@router.get("/daily-detector/status", response_model=DailyDetectorStatusResponse)
def daily_detector_status(
    service: Annotated[DetectorResultService, Depends(get_detector_result_service)],
) -> dict:
    return service.status()


@router.get("/detectors/clues", response_model=DailyDetectorCluesResponse)
def detector_clues(
    service: Annotated[DetectorResultService, Depends(get_detector_result_service)],
    detector_run_id: str | None = None,
    run_date: str | None = None,
    detector_id: str | None = None,
    detector_family: str | None = None,
    manufacturer_code: str | None = None,
    hospital_code: str | None = None,
    drug_group: str | None = None,
    only_monthly_high_risk: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> dict:
    return service.clues(
        detector_run_id=detector_run_id,
        run_date=run_date,
        detector_id=detector_id,
        detector_family=detector_family,
        manufacturer_code=manufacturer_code,
        hospital_code=hospital_code,
        drug_group=drug_group,
        only_monthly_high_risk=only_monthly_high_risk,
        page=page,
        page_size=page_size,
    )


@router.get("/daily-detector/clues", response_model=DailyDetectorCluesResponse)
def daily_detector_clues(
    service: Annotated[DetectorResultService, Depends(get_detector_result_service)],
    run_date: str | None = None,
    detector_id: str | None = None,
    detector_family: str | None = None,
    only_monthly_high_risk: bool | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    return service.clues(
        run_date=run_date,
        detector_id=detector_id,
        detector_family=detector_family,
        only_monthly_high_risk=only_monthly_high_risk,
        page=1,
        page_size=limit,
    )


@router.get(
    "/risk-entities/{risk_entity_id}/detector-evidence",
    response_model=RiskEntityDetectorEvidenceResponse,
)
def risk_entity_detector_evidence(
    risk_entity_id: str,
    service: Annotated[DetectorResultService, Depends(get_detector_result_service)],
    detector_run_id: str | None = None,
    run_date: str | None = None,
    detector_family: str | None = None,
    detector_id: str | None = None,
) -> dict:
    try:
        return service.risk_entity_detector_evidence(
            risk_entity_id=risk_entity_id,
            detector_run_id=detector_run_id,
            run_date=run_date,
            detector_family=detector_family,
            detector_id=detector_id,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"Unknown risk entity: {risk_entity_id}"
        ) from exc


@router.get("/detectors/config-status", response_model=DetectorConfigStatusResponse)
def detector_config_status(
    service: Annotated[DetectorResultService, Depends(get_detector_result_service)],
) -> dict:
    return service.config_status()
