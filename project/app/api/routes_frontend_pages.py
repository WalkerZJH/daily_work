from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.schemas.frontend_pages import (
    MonthlyReportsPayload,
    OneshotPayload,
    ProofCasesPayload,
    RiskEntitiesPayload,
    RiskEntityDetailPayload,
    WorkbenchPayload,
)
from app.services.frontend_page_service import FrontendPageService, get_frontend_page_service

router = APIRouter(prefix="/api/v1", tags=["frontend-pages"])


@router.get("/workbench", response_model=WorkbenchPayload)
def frontend_workbench(service: FrontendPageService = Depends(get_frontend_page_service)) -> dict:
    return service.workbench()


@router.get("/risk-entities", response_model=RiskEntitiesPayload)
def frontend_risk_entities(service: FrontendPageService = Depends(get_frontend_page_service)) -> dict:
    return service.risk_entities()


@router.get("/risk-entities/{entity_id}", response_model=RiskEntityDetailPayload)
def frontend_risk_entity_detail(
    entity_id: str,
    service: FrontendPageService = Depends(get_frontend_page_service),
) -> dict:
    try:
        return service.risk_entity_detail(entity_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown risk entity: {entity_id}") from exc


@router.get("/oneshot-terminals", response_model=OneshotPayload)
def frontend_oneshot_terminals(service: FrontendPageService = Depends(get_frontend_page_service)) -> dict:
    return service.oneshot_terminals()


@router.get("/monthly-reports", response_model=MonthlyReportsPayload)
def frontend_monthly_reports(service: FrontendPageService = Depends(get_frontend_page_service)) -> dict:
    return service.monthly_reports()


@router.get("/proof-cases", response_model=ProofCasesPayload)
def frontend_proof_cases(service: FrontendPageService = Depends(get_frontend_page_service)) -> dict:
    return service.proof_cases()
