from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.api.routes_display_lookup import get_display_lookup_service
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
from app.services.frontend_top_entity_adapter import build_risk_entities_payload_from_top_entities
from app.services.display_lookup_service import DisplayLookupService
from app.services.user_top_entity_service import TopEntityService

router = APIRouter(prefix="/api/v1", tags=["frontend-pages"])


@router.get("/workbench", response_model=WorkbenchPayload)
def frontend_workbench(
    service: FrontendPageService = Depends(get_frontend_page_service),
    display_lookup_service: DisplayLookupService = Depends(get_display_lookup_service),
) -> dict:
    return _with_display_lookup_status(service.workbench(), display_lookup_service)


@router.get("/risk-entities", response_model=RiskEntitiesPayload)
def frontend_risk_entities(
    service: FrontendPageService = Depends(get_frontend_page_service),
    top_entity_service: TopEntityService = Depends(get_user_top_entity_service),
    display_lookup_service: DisplayLookupService = Depends(get_display_lookup_service),
    x_user_id: Annotated[str | None, Header()] = None,
    top_n: int = Query(default=20, ge=1, le=100),
) -> dict:
    top_entity_payload = build_risk_entities_payload_from_top_entities(
        top_entity_service,
        user_id=x_user_id or "admin",
        top_n=top_n,
    )
    if top_entity_payload:
        return _with_display_lookup_status(top_entity_payload, display_lookup_service)
    return _with_display_lookup_status(service.risk_entities(), display_lookup_service)


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
