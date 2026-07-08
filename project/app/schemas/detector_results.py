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
    run_date: str | None = None
    source: str
    warnings: list[str]


class DailyDetectorClueItem(DetectorResultModel):
    detector_clue_id: str
    detector_run_id: str
    run_date: str
    tenant_id: str | None = None
    manufacturer_code: str | None = None
    hospital_code: str | None = None
    drug_group: str | None = None
    detector_id: str
    detector_family: str
    detector_score: float | None = None
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
    display_rank: int | None = None
    caveat: str | None = None
    created_at: str | None = None


class DailyDetectorCluesResponse(DetectorResultModel):
    ready: bool
    source: str
    items: list[DailyDetectorClueItem]
    pagination: dict[str, int]
    semantic_caveats: list[str]
    warnings: list[str]


class HighRiskDetectorEvidenceItem(DetectorResultModel):
    risk_entity_id: str
    detector_run_id: str
    run_date: str
    detector_id: str
    detector_family: str
    detector_score: float | None = None
    confidence: float | None = None
    root_cause_label: str | None = None
    evidence_text: str | None = None
    evidence_payload: Any = None
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


class DetectorConfigStatusResponse(DetectorResultModel):
    effective_config_version: str | None = None
    latest_run_id: str | None = None
    latest_run_date: str | None = None
    pending_config_version: str | None = None
    pending_config_exists: bool
    pending_config_supported: bool
    next_run_required: bool
    history_rewrite_allowed: bool
    config_edit_semantics: str
    warnings: list[str]
