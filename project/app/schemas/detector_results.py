from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DetectorResultModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DetectorCatalogItem(DetectorResultModel):
    detector_id: str
    detector_family: str
    detector_name: str
    status: str
    enabled_by_default: bool
    method: str
    required_fields: Any
    optional_fields: Any
    output_schema_version: str
    caveat: str | None = None


class DetectorCatalogResponse(DetectorResultModel):
    ready: bool
    source: str
    items: list[DetectorCatalogItem]
    semantic_caveats: list[str]
    warnings: list[str]


class DailyDetectorRunItem(DetectorResultModel):
    detector_run_id: str
    run_date: str
    report_month: str
    source_result_batch_id: str | None = None
    detector_config_version: str
    enabled_detectors: Any
    scanned_entity_count: int = Field(ge=0)
    clue_count: int = Field(ge=0)
    attached_high_risk_count: int = Field(ge=0)
    created_at: str | None = None


class DailyDetectorRunsResponse(DetectorResultModel):
    ready: bool
    source: str
    items: list[DailyDetectorRunItem]
    warnings: list[str]


class DailyDetectorStatusResponse(DetectorResultModel):
    ready: bool
    data_source: str = "risk_model_core"
    run_date: str | None = None
    detector_run_id: str | None = None
    detector_config_version: str | None = None
    clue_count: int = Field(default=0, ge=0)
    attached_high_risk_count: int = Field(default=0, ge=0)
    highest_detector_score: float | None = None
    enabled_detectors: Any = None
    config_effective_note: str | None = None
    source: str
    warnings: list[str]
    report_context: dict[str, Any] = Field(default_factory=dict)
    observation_date: str | None = None
    effective_observation_date: str | None = None
    probability_report_month: str | None = None
    expected_probability_report_month: str | None = None
    effective_probability_report_month: str | None = None
    probability_batch_available: bool | None = None
    detector_run_date: str | None = None
    detector_run_available: bool | None = None
    context_status: str | None = None
    manual_selection_required: bool | None = None
    partial_ready: bool = False
    requested_report_month: str | None = None
    effective_report_month: str | None = None
    requested_run_date: str | None = None
    effective_run_date: str | None = None
    date_resolution_status: str | None = None


class DailyDetectorClueItem(DetectorResultModel):
    clue_id: str | None = None
    detector_clue_id: str
    detector_run_id: str
    run_date: str
    tenant_id: str | None = None
    manufacturer_code: str | None = None
    manufacturer_display_name: str | None = None
    manufacturer_name: str | None = None
    hospital_code: str | None = None
    hospital_display_name: str | None = None
    hospital_name: str | None = None
    drug_group: str | None = None
    drug_display_name: str | None = None
    drug_name: str | None = None
    region_display_name: str | None = None
    product_line_name: str | None = None
    detector_id: str
    detector_family: str
    detector_family_label: str | None = None
    detector_name_label: str | None = None
    detector_score: float | None = None
    detector_score_label: str | None = None
    detector_level: str | None = None
    confidence: float | None = None
    hit_flag: bool
    root_cause_label: str | None = None
    evidence_text: str | None = None
    evidence_payload: Any = None
    is_monthly_high_risk_entity: bool
    risk_entity_id: str | None = None
    monthly_risk_probability: float | None = None
    monthly_loss_value: float | None = None
    action: str | None = None
    display_rank: int | None = None
    caveat: str | None = None
    created_at: str | None = None
    evaluation: DailyDetectorResultItem | None = None


class DailyDetectorCluesResponse(DetectorResultModel):
    ready: bool
    source: str
    data_source: str = "risk_model_core"
    clues: list[DailyDetectorClueItem] = Field(default_factory=list)
    items: list[DailyDetectorClueItem]
    total: int = Field(default=0, ge=0)
    run_date: str | None = None
    detector_run_id: str | None = None
    pagination: dict[str, int]
    sort: dict[str, str] = Field(default_factory=dict)
    semantic_caveats: list[str]
    warnings: list[str]
    report_context: dict[str, Any] = Field(default_factory=dict)
    observation_date: str | None = None
    effective_observation_date: str | None = None
    probability_report_month: str | None = None
    expected_probability_report_month: str | None = None
    effective_probability_report_month: str | None = None
    probability_batch_available: bool | None = None
    detector_run_date: str | None = None
    detector_run_available: bool | None = None
    context_status: str | None = None
    manual_selection_required: bool | None = None
    partial_ready: bool = False
    requested_report_month: str | None = None
    effective_report_month: str | None = None
    requested_run_date: str | None = None
    effective_run_date: str | None = None
    date_resolution_status: str | None = None


class DailyDetectorResultItem(DetectorResultModel):
    detector_result_id: str
    run_id: str
    source_raw_batch_id: str | None = None
    observation_date: str
    manufacturer_code: str
    hospital_code: str
    drug_code: str
    purchase_unit: str | None = None
    detector_family: str
    detector_id: str
    detector_name: str
    detector_version: str
    config_id: str
    config_hash: str
    hit_flag: bool
    severity: str
    confidence: float | None = None
    eligibility_status: str
    inapplicable_reason: str | None = None
    demand_shape_label: str | None = None
    evidence_window_start: str | None = None
    evidence_window_end: str | None = None
    current_value: float | str | None = None
    baseline_value: float | str | None = None
    comparison_value: float | str | None = None
    threshold_value: float | str | None = None
    threshold_operator: str | None = None
    evidence_payload: Any = None
    evidence_text: str
    hit_reason: str
    caveat: str
    created_at: str | None = None


class DailyDetectorResultsResponse(DetectorResultModel):
    ready: bool
    source: str
    items: list[DailyDetectorResultItem]
    total: int = Field(ge=0)
    pagination: dict[str, int]
    semantic_caveats: list[str]
    warnings: list[str]


class DetectorEventAggregateItem(DetectorResultModel):
    detector_event_aggregate_id: str
    observation_date: str
    manufacturer_code: str
    hospital_code: str
    drug_code: str
    current_detector_count: int = Field(ge=1)
    current_detector_ids: list[str]
    cumulative_hit_count: int = Field(ge=1)
    cumulative_hit_day_count: int = Field(ge=1)
    historical_detector_ids: list[str]
    first_hit_date: str
    last_hit_date: str
    aggregation_schema_version: str
    generated_at: str | None = None


class DetectorEventAggregatesResponse(DetectorResultModel):
    ready: bool
    source: str
    items: list[DetectorEventAggregateItem]
    total: int = Field(ge=0)
    pagination: dict[str, int]
    sort: dict[str, str]
    warnings: list[str]


class DailyDetectorClueDetailResponse(DetectorResultModel):
    ready: bool
    source: str
    item: DailyDetectorClueItem
    semantic_caveats: list[str]
    warnings: list[str]


class HighRiskDetectorEvidenceItem(DetectorResultModel):
    risk_entity_id: str
    detector_run_id: str
    run_date: str
    detector_id: str
    detector_family: str
    detector_family_label: str | None = None
    detector_name: str | None = None
    detector_name_label: str | None = None
    detector_version: str | None = None
    observation_date: str | None = None
    hit_flag: bool = True
    detector_score: float | None = None
    confidence: float | None = None
    root_cause_label: str | None = None
    evidence_text: str | None = None
    evidence_payload: Any = None
    monitoring_logic: dict[str, Any] = Field(default_factory=dict)
    observed_values: dict[str, Any] = Field(default_factory=dict)
    decision: dict[str, Any] = Field(default_factory=dict)
    caveat: str | None = None
    created_at: str | None = None


class RiskEntityDetectorEvidenceResponse(DetectorResultModel):
    risk_entity_id: str
    source: str
    monthly_risk_probability: float | None = None
    monthly_loss_value: float | None = None
    items: list[HighRiskDetectorEvidenceItem]
    catalog_by_detector_id: dict[str, DetectorCatalogItem]
    semantic_caveats: list[str]
    warnings: list[str]
    report_context: dict[str, Any] = Field(default_factory=dict)
    observation_date: str | None = None
    effective_observation_date: str | None = None
    probability_report_month: str | None = None
    expected_probability_report_month: str | None = None
    effective_probability_report_month: str | None = None
    probability_batch_available: bool | None = None
    detector_run_date: str | None = None
    detector_run_available: bool | None = None
    context_status: str | None = None
    manual_selection_required: bool | None = None
    partial_ready: bool = False
    requested_report_month: str | None = None
    effective_report_month: str | None = None
    requested_run_date: str | None = None
    effective_run_date: str | None = None
    date_resolution_status: str | None = None


class DetectorConfigStatusResponse(DetectorResultModel):
    effective_config_version: str | None = None
    latest_run_id: str | None = None
    latest_run_date: str | None = None
    pending_config_version: str | None = None
    pending_config_exists: bool
    pending_config_supported: bool
    next_run_required: bool
    history_rewrite_allowed: bool
    parameter_source: str
    parameter_editable: bool
    personalized_parameter_profiles: str
    display_filter_policy: str
    config_edit_semantics: str
    warnings: list[str]
