from __future__ import annotations

from fastapi import APIRouter, Depends

from app.services.display_lookup_service import (
    DisplayLookupService,
    build_default_display_lookup_service,
)

router = APIRouter(prefix="/api/v1/display-lookup", tags=["display-lookup"])


def get_display_lookup_service() -> DisplayLookupService:
    return build_default_display_lookup_service()


@router.get("/status")
def display_lookup_status(
    service: DisplayLookupService = Depends(get_display_lookup_service),
) -> dict:
    return service.status()
