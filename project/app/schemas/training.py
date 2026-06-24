from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.api import DataSourceRequest


class TrainingModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TrainingDatasetBuildRequest(DataSourceRequest):
    train_start: date
    train_end: date
    horizon_days: int = Field(default=90, ge=1)
    freq: Literal["M", "W"] = "M"
    output_path: str | None = None


class TrainingDatasetBuildResponse(TrainingModel):
    sample_count: int
    positive_count: int
    negative_count: int
    positive_rate: float | None = None
    train_start: date
    train_end: date
    horizon_days: int
    freq: str
    output_path: str | None = None
    warning_summary: dict[str, int] = Field(default_factory=dict)
    data_quality: dict[str, Any] = Field(default_factory=dict)
