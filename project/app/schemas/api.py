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
    date_from: date | None = None
    date_to: date | None = None
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
    data_quality_summary: dict[str, Any] = Field(default_factory=dict)


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


class PAliveExperimentConfig(ApiModel):
    interval_prior_k: float = Field(default=5.0, gt=0)
    min_unit_intervals: int = Field(default=2, ge=1)
    min_cohort_intervals: int = Field(default=5, ge=1)
    bgnbd_min_orders: int = Field(default=5, ge=2)
    intermittent_overdue_multiplier: float = Field(default=1.5, gt=0)
    low_confidence_threshold: float = Field(default=0.35, ge=0, le=1)


class PAliveExperimentRequest(DataSourceRequest):
    as_of_date: date
    enabled_models: list[str] | None = None


class PAliveCandidateResult(ApiModel):
    analysis_unit_id: str
    org_code: str
    org_name: str | None = None
    product_line_code: str
    product_line_name: str | None = None
    as_of_date: date
    demand_profile: Literal["smooth", "erratic", "intermittent", "lumpy", "unknown"]
    days_since_last_purchase: float | None = None
    purchase_interval_stats: dict[str, Any] = Field(default_factory=dict)
    p_alive_proxy_interval: float | None = Field(default=None, ge=0, le=1)
    p_alive_bgnbd: float | None = Field(default=None, ge=0, le=1)
    p_alive_intermit_proxy: float | None = Field(default=None, ge=0, le=1)
    selected_p_alive: float | None = Field(default=None, ge=0, le=1)
    selected_model_name: str
    model_confidence: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)
    debug_features: dict[str, Any] = Field(default_factory=dict)


class PAliveExperimentResponse(ApiModel):
    dataset_name: str
    as_of_date: date
    config: PAliveExperimentConfig
    unit_count: int
    results: list[PAliveCandidateResult]
    warning_summary: dict[str, int] = Field(default_factory=dict)


class DatabaseSmokeTestRequest(ApiModel):
    source_type: Literal["csv", "database"] = "database"
    as_of_date: date
    lookback_days: int | None = Field(default=30, ge=1, le=365)
    baseline_days: int = Field(default=180, ge=1, le=730)
    history_start_date: date | None = None
    days: int = Field(default=14, ge=1, le=60)
    row_limit: int = Field(default=5000, ge=1, le=5000)
    enterprise_code: str | None = None
    enterprise_name: str | None = None
    province: str | None = None
    province_code: str | None = None
    province_name: str | None = None
    product_line_code: str | None = None
    include_debug_features: bool = False


class DatabaseSmokeTestResponse(ApiModel):
    summary: dict[str, Any]
    palive_preview: list[dict[str, Any]] = Field(default_factory=list)
    warning_summary: dict[str, int] = Field(default_factory=dict)


class DatabaseFreshnessRequest(ApiModel):
    as_of_date: date | None = None
    days: int = Field(default=14, ge=1, le=60)
    date_from: date | None = None
    date_to: date | None = None
    row_limit: int | None = Field(default=5000, ge=1, le=5000)
    enterprise_code: str | None = None
    province: str | None = None
    province_code: str | None = None


class DatabaseFreshnessResponse(ApiModel):
    source_type: Literal["database"] = "database"
    max_order_time: str | None = None
    row_count: int
    date_from: date | None = None
    date_to: date | None = None
    is_changed_since_last_check: None = None
    note: str = "v0 only reports freshness; no scheduler is implemented"
    warning_summary: dict[str, int] = Field(default_factory=dict)


class DetectorRunRequest(DataSourceRequest):
    source_type: Literal["csv", "database", "sample"] = "csv"
    as_of_date: date
    days: int = Field(default=14, ge=1, le=60)
    lookback_days: int | None = Field(default=None, ge=1, le=365)
    baseline_days: int = Field(default=180, ge=1, le=730)
    history_start_date: date | None = None
    enterprise_name: str | None = None
    province_name: str | None = None
    product_line_code: str | None = None
    enabled_detectors: list[str] | None = None
    category: str | None = None
    include_debug: bool = True


class DailyRiskRunRequest(DetectorRunRequest):
    """Daily exploration request. It is not a formal workflow/work-order request."""


class DetectorRunResult(ApiModel):
    detector_id: str
    detector_name: str
    name_zh: str
    category: str
    status: str
    hit: bool
    severity: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    reason_code: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    evidence_items: list[dict[str, Any]] = Field(default_factory=list)
    related_entities: dict[str, Any] = Field(default_factory=dict)
    sample_order_ids: list[str] = Field(default_factory=list)
    statistics: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    narrative: str
    as_of_date: date | None = None
    lookback_start_date: date | None = None
    baseline_start_date: date | None = None
    baseline_end_date: date | None = None
    run_scope: dict[str, Any] = Field(default_factory=dict)


class DetectorRunResponse(ApiModel):
    summary: dict[str, Any]
    detector_results: list[DetectorRunResult] = Field(default_factory=list)
    warning_summary: dict[str, int] = Field(default_factory=dict)
    debug: dict[str, Any] = Field(default_factory=dict)


class DetectorRuntimeConfig(ApiModel):
    detector_id: str
    category: str
    enabled: bool = True
    mode: Literal["rule", "auto_baseline", "rule_first", "ml_first", "dl_first"] = "rule"
    params: dict[str, Any] = Field(default_factory=dict)
    scope_type: str = "global"
    scope_value: str | None = None
    updated_by: str | None = None
    updated_at: str | None = None


class DetectorRuntimeConfigPatch(ApiModel):
    enabled: bool | None = None
    mode: Literal["rule", "auto_baseline", "rule_first", "ml_first", "dl_first"] | None = None
    params: dict[str, Any] | None = None
    scope_type: str | None = None
    scope_value: str | None = None
    updated_by: str | None = None


class DetectorConfigResponse(ApiModel):
    configs: list[DetectorRuntimeConfig]
    warning_summary: dict[str, int] = Field(default_factory=dict)


class OptionItem(ApiModel):
    code: str | None = None
    name: str


class DetectorCategoryOption(ApiModel):
    category_id: str
    category_name: str
    detector_count: int


class DetectorOption(ApiModel):
    detector_id: str
    name_zh: str
    enabled: bool
    mode: str
    implemented: bool
