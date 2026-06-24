from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.api import DataSourceRequest


class BackboneModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BackbonePredictRequest(DataSourceRequest):
    as_of_date: date


class BackbonePrediction(BackboneModel):
    analysis_unit_id: str
    org_code: str
    product_line_code: str
    as_of_date: date
    model_name: str
    model_version: str
    p_alive: float | None = Field(default=None, ge=0, le=1)
    backbone_risk_score: float | None = Field(default=None, ge=0, le=100)
    confidence: float = Field(default=0, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)
    debug_features: dict[str, Any] = Field(default_factory=dict)
