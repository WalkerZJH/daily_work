"""Domain objects for a minimal MVC-facing risk model layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RiskEntity:
    risk_entity_id: str
    candidate_id: str
    tenant_id: str
    enterprise_id: str
    manufacturer_code: str
    hospital_code: str
    drug_group: str
    report_month: str
    risk_level: str
    review_status: str
    final_candidate_status: str
    auto_dispatch_allowed: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RiskCard:
    risk_card_id: str
    risk_entity_id: str
    candidate_id: str
    card_type: str
    card_title: str
    card_level: str
    source_module: str
    is_primary: bool = False


@dataclass(slots=True)
class RiskEvidence:
    evidence_id: str
    risk_card_id: str
    risk_entity_id: str
    candidate_id: str
    evidence_type: str
    evidence_text: str
    visibility_level: str


@dataclass(slots=True)
class RiskTimelinePoint:
    timeline_id: str
    risk_entity_id: str
    candidate_id: str
    month: str
    display_note: str


@dataclass(slots=True)
class HospitalAggregate:
    tenant_id: str
    hospital_code: str
    hospital_display_name: str
    risk_entity_count: int
    high_risk_count: int


@dataclass(slots=True)
class DrugAggregate:
    tenant_id: str
    drug_group: str
    drug_group_source: str
    risk_entity_count: int
    high_risk_count: int


@dataclass(slots=True)
class DailyReport:
    daily_report_id: str
    report_type: str
    report_month: str
    title: str
    summary_text: str


@dataclass(slots=True)
class ProofCase:
    proof_case_id: str
    risk_entity_id: str
    candidate_id: str
    proof_status: str


@dataclass(slots=True)
class WorkOrderReserved:
    work_order_id: str
    risk_entity_id: str
    candidate_id: str
    work_order_status: str
    auto_dispatch_allowed: bool = False


DOMAIN_OBJECTS = [
    RiskEntity,
    RiskCard,
    RiskEvidence,
    RiskTimelinePoint,
    HospitalAggregate,
    DrugAggregate,
    DailyReport,
    ProofCase,
    WorkOrderReserved,
]
