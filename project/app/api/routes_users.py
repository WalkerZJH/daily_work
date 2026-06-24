from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.services.user_config_service import PermissionError, UserConfigService

router = APIRouter(prefix="/api/v0/users", tags=["users"])


class PreferencePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled_detectors: list[str] = Field(default_factory=list)


@router.get("/me/config")
def my_config(x_user_id: str | None = Header(default=None)) -> dict[str, Any]:
    return UserConfigService().get_user_config(x_user_id or "admin")


@router.patch("/{user_id}/preferences")
def patch_preferences(
    user_id: str,
    patch: PreferencePatch,
    x_user_id: str | None = Header(default=None),
) -> dict[str, Any]:
    try:
        return UserConfigService().update_preferences(
            actor_user_id=x_user_id or "admin",
            target_user_id=user_id,
            enabled_detectors=patch.enabled_detectors,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
