from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

from app.schemas.algorithm import DetectorResult, FusionResult, RiskClue
from app.schemas.config import FusionConfig


def fuse_detector_results(
    detector_results: list[DetectorResult],
    config: FusionConfig,
) -> FusionResult:
    triggered = [result for result in detector_results if result.hit]
    if not triggered:
        return FusionResult(
            risk_score=0,
            risk_level="none",
            confidence=0,
            triggered_families=[],
            reason_code="NO_DETECTOR_HIT",
        )

    rule_score = max(result.severity for result in triggered)
    confidence = max(result.confidence for result in triggered)
    risk_level = _level_for_score(rule_score, confidence, config)

    return FusionResult(
        risk_score=float(round(rule_score, 4)),
        risk_level=risk_level,
        confidence=float(round(confidence, 4)),
        triggered_families=[result.detector_name for result in triggered],
        reason_code="LEGACY_RULE_SCORE_NOT_PROBABILITY",
    )


def build_risk_clue(
    org_code: str,
    product_line_code: str,
    as_of_date: date,
    config_version: str,
    fusion: FusionResult,
    evidence_summary: dict[str, Any],
) -> RiskClue:
    trace_source = f"{org_code}|{product_line_code}|{as_of_date.isoformat()}|{config_version}"
    trace_hash = hashlib.sha1(trace_source.encode("utf-8")).hexdigest()[:12]
    return RiskClue(
        clue_id=f"clue-{trace_hash}",
        org_code=org_code,
        product_line_code=product_line_code,
        risk_score=fusion.risk_score,
        risk_level=fusion.risk_level,
        triggered_detectors=fusion.triggered_families,
        confidence=fusion.confidence,
        evidence_summary_structured=evidence_summary,
        debug_trace_id=trace_hash,
    )


def _level_for_score(score: float, confidence: float, config: FusionConfig) -> str:
    if confidence < config.min_confidence_for_alert:
        return "none"
    if score >= config.red_score:
        return "red"
    if score >= config.orange_score:
        return "orange"
    if score >= config.yellow_score:
        return "yellow"
    return "none"
