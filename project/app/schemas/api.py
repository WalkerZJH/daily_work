from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.algorithm import RiskCardCandidate, RiskClue


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DataSourceRequest(ApiModel):
    source_type: Literal["csv", "database"] = "csv"
    dataset_name: str | None = "sample"
    csv_path: str | None = None
    enterprise_code: str | None = None
    province: str | None = None
    province_code: str | None = None
    row_limit: int | None = Field(default=None, ge=1)


class DataQualityRequest(DataSourceRequest):
    pass


class DataQualityIssue(ApiModel):
    check_name: str
    severity: str
    message: str
    row_count: int
    sample_refs: list[str] = Field(default_factory=list)


class DataQualityReport(ApiModel):
    dataset_name: str
    total_rows: int
    error_count: int
    warning_count: int
    issues: list[DataQualityIssue] = Field(default_factory=list)


class DryRunRequest(DataSourceRequest):
    as_of_date: date
    user_id: str | None = None


class DryRunResponse(ApiModel):
    dataset_name: str
    as_of_date: date
    config_version: str
    unit_count: int
    clue_count: int
    risk_level_distribution: dict[str, int]
    detector_hit_distribution: dict[str, int]
    top_risk_clues: list[RiskClue | RiskCardCandidate]
    risk_card_candidates: list[RiskCardCandidate] = Field(default_factory=list)
    enabled_preprocessors: list[str] = Field(default_factory=list)
    feature_count: int = 0
    detector_skipped_due_to_missing_features: int = 0
    warning_summary: dict[str, int] = Field(default_factory=dict)
    backbone: dict[str, Any] = Field(default_factory=dict)


class PreprocessRunRequest(DataSourceRequest):
    as_of_date: date
    enabled_preprocessors: list[str] | None = None


class BacktestRequest(DataSourceRequest):
    start_date: date
    end_date: date
    step_days: int = Field(default=30, ge=1)


class BacktestResponse(ApiModel):
    dataset_name: str
    periods: list[DryRunResponse]


class ConfigDryRunRequest(DryRunRequest):
    config_patch: dict[str, Any] = Field(default_factory=dict)


class ConfigDryRunResponse(ApiModel):
    default_result: DryRunResponse
    patched_result: DryRunResponse
    delta: dict[str, Any]
