"""Minimal MVC-facing algorithm model package.

This package intentionally avoids importing training, SQL extraction, feature
engineering, or M-stage experiment modules. It can be copied into a backend
domain/model layer as a stable result-batch reader and payload builder.
"""

from .batch_manifest import ResultBatchManifest
from .business_copy_renderer import BusinessCopyRenderer, contains_forbidden_claims
from .domain import (
    DOMAIN_OBJECTS,
    DailyReport,
    DrugAggregate,
    HospitalAggregate,
    ProofCase,
    RiskCard,
    RiskEntity,
    RiskEvidence,
    RiskTimelinePoint,
    WorkOrderReserved,
)
from .repositories import ClickHouseRiskResultRepository, ParquetRiskResultRepository, RiskResultRepository

__all__ = [
    "BusinessCopyRenderer",
    "ClickHouseRiskResultRepository",
    "DOMAIN_OBJECTS",
    "DailyReport",
    "DrugAggregate",
    "HospitalAggregate",
    "ParquetRiskResultRepository",
    "ProofCase",
    "ResultBatchManifest",
    "RiskCard",
    "RiskEntity",
    "RiskEvidence",
    "RiskResultRepository",
    "RiskTimelinePoint",
    "WorkOrderReserved",
    "contains_forbidden_claims",
]
