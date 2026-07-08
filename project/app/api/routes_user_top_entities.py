from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.services.user_top_entity_service import (
    CandidateType,
    FillPolicy,
    GroupBy,
    RankingStrategy,
    TopEntityService,
    build_default_top_entity_service,
)

router = APIRouter(prefix="/api/risk", tags=["risk-top-entities"])


def get_user_top_entity_service() -> TopEntityService:
    return build_default_top_entity_service()


@router.get("/my/top-entities")
def my_top_entities(
    service: Annotated[TopEntityService, Depends(get_user_top_entity_service)],
    x_user_id: Annotated[str | None, Header()] = None,
    report_month: str | None = Query(default=None),
    horizon: str = Query(default="H6"),
    top_n: int = Query(default=20),
    max_n: int = Query(default=50, ge=1, le=100),
    group_by: GroupBy = Query(default="user_scope"),
    ranking_strategy: RankingStrategy = Query(default="probability"),
    candidate_type: CandidateType = Query(default="recurring"),
    probability_threshold: float | None = Query(default=None, ge=0, le=1),
    include_threshold_overflow: bool = Query(default=False),
    fill_policy: FillPolicy = Query(default="none"),
    manufacturer_codes: list[str] | None = Query(default=None),
) -> dict:
    if top_n < 1:
        raise HTTPException(status_code=400, detail="top_n must be >= 1")
    return service.list_user_top_entities(
        user_id=x_user_id or "admin",
        report_month=report_month,
        horizon=horizon,
        top_n=top_n,
        max_n=max_n,
        group_by=group_by,
        ranking_strategy=ranking_strategy,
        candidate_type=candidate_type,
        probability_threshold=probability_threshold,
        include_threshold_overflow=include_threshold_overflow,
        fill_policy=fill_policy,
        manufacturer_codes=manufacturer_codes,
    )
