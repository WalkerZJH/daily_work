from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.features.snapshot import FeatureSnapshot
from app.schemas.config import AppConfig


class DetectorResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detector_name: str
    unit_id: str
    org_code: str
    analysis_grain: str
    target_code: str
    as_of_date: str
    hit: bool
    severity: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    reason_code: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    required_features_missing: list[str] = Field(default_factory=list)


class BaseDetector(Protocol):
    name: str
    version: str
    required_features: list[str]
    supported_grains: list[str]

    def detect(self, snapshots: list[FeatureSnapshot], config: AppConfig) -> list[DetectorResult]:
        ...


def missing_features(snapshot: FeatureSnapshot, required_features: list[str]) -> list[str]:
    return [
        feature
        for feature in required_features
        if feature not in snapshot.features or snapshot.features.get(feature) is None
    ]


def missing_required_result(
    detector_name: str,
    snapshot: FeatureSnapshot,
    required_features: list[str],
) -> DetectorResult:
    missing = missing_features(snapshot, required_features)
    return DetectorResult(
        detector_name=detector_name,
        unit_id=snapshot.unit_id,
        org_code=snapshot.org_code,
        analysis_grain=snapshot.analysis_grain,
        target_code=snapshot.target_code,
        as_of_date=snapshot.as_of_date.isoformat(),
        hit=False,
        severity=0,
        confidence=0,
        reason_code="MISSING_REQUIRED_FEATURES",
        metrics={},
        evidence_refs=[],
        warnings=["MISSING_REQUIRED_FEATURES"],
        required_features_missing=missing,
    )


def base_result(
    detector_name: str,
    snapshot: FeatureSnapshot,
    *,
    hit: bool,
    severity: float,
    confidence: float,
    reason_code: str,
    metrics: dict[str, Any] | None = None,
    evidence_refs: list[dict[str, Any]] | None = None,
    warnings: list[str] | None = None,
) -> DetectorResult:
    return DetectorResult(
        detector_name=detector_name,
        unit_id=snapshot.unit_id,
        org_code=snapshot.org_code,
        analysis_grain=snapshot.analysis_grain,
        target_code=snapshot.target_code,
        as_of_date=snapshot.as_of_date.isoformat(),
        hit=hit,
        severity=max(0, min(100, severity)),
        confidence=max(0, min(1, confidence)),
        reason_code=reason_code,
        metrics=metrics or {},
        evidence_refs=evidence_refs or [{"ref_type": "feature_snapshot", "ref_id": snapshot.unit_id}],
        warnings=list(dict.fromkeys([*snapshot.warnings, *(warnings or [])])),
        required_features_missing=[],
    )


def number(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def demand_shape_sensitivity(shape: Any) -> tuple[float, float]:
    if shape in {"intermittent", "lumpy"}:
        return 1.35, 0.75
    if shape == "unknown":
        return 1.2, 0.65
    return 1.0, 1.0
