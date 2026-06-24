from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

RiskLevel = Literal["red", "orange", "yellow", "none"]


class AlgorithmModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceRef(AlgorithmModel):
    ref_type: str
    ref_id: str
    order_id: str | None = None
    event_time: datetime | None = None
    fields: dict[str, Any] = Field(default_factory=dict)


class BaselineMetrics(AlgorithmModel):
    org_code: str
    product_line_code: str
    as_of_date: date
    recent_start: date
    baseline_start: date
    baseline_end: date
    total_orders: int
    recent_orders: int
    baseline_orders: int
    recent_qty: float
    baseline_qty: float
    recent_active_sku_count: int
    baseline_active_sku_count: int
    recent_monthly_order_rate: float
    baseline_monthly_order_rate: float
    last_order_time: datetime | None
    recent_order_ids: list[str] = Field(default_factory=list)
    baseline_order_ids: list[str] = Field(default_factory=list)


class DemandShapeResult(AlgorithmModel):
    demand_shape: Literal["smooth", "erratic", "intermittent", "lumpy", "unknown"]
    adi: float | None
    cv2: float | None
    confidence: float
    reason_code: str
    warnings: list[str] = Field(default_factory=list)


class DetectorResult(AlgorithmModel):
    detector_name: str
    hit: bool
    severity: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    reason_code: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class FusionResult(AlgorithmModel):
    risk_score: float = Field(ge=0, le=100)
    risk_level: RiskLevel
    confidence: float = Field(ge=0, le=1)
    triggered_families: list[str] = Field(default_factory=list)
    reason_code: str


class RiskClue(AlgorithmModel):
    clue_id: str
    org_code: str
    product_line_code: str
    risk_score: float = Field(ge=0, le=100)
    risk_level: RiskLevel
    triggered_detectors: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    evidence_summary_structured: dict[str, Any] = Field(default_factory=dict)
    debug_trace_id: str


class DetectorEvidence(AlgorithmModel):
    detector_id: str
    category: str
    family: str
    hit: bool
    severity: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    reason_code: str
    evidence_items: list[dict[str, Any]] = Field(default_factory=list)
    related_entities: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    sample_order_ids: list[str] = Field(default_factory=list)
    statistics: dict[str, Any] = Field(default_factory=dict)


class BackboneSignal(AlgorithmModel):
    backbone_model: Literal[
        "palive_lgbm",
        "palive_interval_proxy",
        "palive_bgnbd",
        "not_available",
        "heuristic",
    ] = "not_available"
    p_alive: float | None = Field(default=None, ge=0, le=1)
    backbone_risk_score: float | None = Field(default=None, ge=0, le=100)
    backbone_confidence: float | None = Field(default=None, ge=0, le=1)
    warnings: list[str] = Field(default_factory=lambda: ["PALIVE_NOT_IMPLEMENTED"])


class EvidenceFamily(AlgorithmModel):
    category: str
    family: str
    detector_ids: list[str] = Field(default_factory=list)
    max_severity: float = Field(default=0, ge=0, le=100)
    hit_count: int = 0
    reason_codes: list[str] = Field(default_factory=list)


class RiskCardCandidate(AlgorithmModel):
    card_id: str
    as_of_date: date
    category: str
    risk_level: RiskLevel
    title: str
    org_code: str
    org_name: str | None = None
    product_line_code: str
    product_line_name: str | None = None
    province: str | None = None
    city: str | None = None
    county: str | None = None
    backbone: BackboneSignal
    evidence_families: list[EvidenceFamily] = Field(default_factory=list)
    detector_evidence: list[DetectorEvidence] = Field(default_factory=list)
    related_entities: dict[str, Any] = Field(default_factory=dict)
    suggested_action: str
    warnings: list[str] = Field(default_factory=list)
    debug_trace_id: str
    rule_score: float | None = Field(default=None, ge=0, le=100)
    risk_score_deprecated: float | None = Field(default=None, ge=0, le=100)
    triggered_detectors: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0, ge=0, le=1)
    evidence_summary_structured: dict[str, Any] = Field(default_factory=dict)
    llm_context: dict[str, Any] = Field(default_factory=dict)


class UnitInspectionResult(AlgorithmModel):
    profile: dict[str, Any]
    demand_shape: DemandShapeResult
    baseline_metrics: BaselineMetrics
    detector_results: list[DetectorResult]
    fusion: FusionResult
    evidence_json: dict[str, Any]
    clue: RiskClue
