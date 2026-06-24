from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.detectors.base import DetectorResult
from app.schemas.config import AppConfig


def fuse_detector_results(results: list[DetectorResult], config: AppConfig) -> dict[str, Any]:
    hit_results = [result for result in results if result.hit]
    by_family: dict[str, list[DetectorResult]] = defaultdict(list)
    for result in hit_results:
        by_family[_family_for(result.detector_name, config)].append(result)

    family_scores = {
        family: max(result.severity for result in family_results)
        for family, family_results in by_family.items()
    }
    rule_score = max(family_scores.values(), default=0.0)
    warning_count = sum(len(result.warnings) for result in results)
    confidence_values = [result.confidence for result in hit_results]
    confidence = sum(confidence_values) / len(confidence_values) if confidence_values else 0.0
    confidence = max(0.0, confidence - min(0.3, warning_count * 0.02))
    if confidence < config.fusion.min_confidence_for_alert or rule_score <= 0:
        risk_level = "none"
    elif len(family_scores) >= 2 or rule_score >= config.fusion.orange_score:
        risk_level = "orange"
    elif rule_score >= config.fusion.yellow_score:
        risk_level = "yellow"
    else:
        risk_level = "none"

    return {
        "risk_score": round(rule_score, 2),
        "rule_score": round(rule_score, 2),
        "risk_score_deprecated": round(rule_score, 2),
        "score_semantics": "Uncalibrated rule score for sorting only; not probability.",
        "risk_level": risk_level,
        "confidence": round(confidence, 4),
        "triggered_detectors": [result.detector_name for result in hit_results],
        "triggered_families": sorted(family_scores),
        "family_scores": family_scores,
        "backbone": {
            "backbone_model": "not_available",
            "p_alive": None,
            "backbone_risk_score": None,
            "backbone_confidence": None,
            "warnings": ["PALIVE_NOT_IMPLEMENTED"],
        },
        "reason_code": "DETECTOR_RULE_AGGREGATION" if hit_results else "NO_DETECTOR_HIT",
    }


def _family_for(detector_name: str, config: AppConfig) -> str:
    return str(getattr(getattr(config.detectors, detector_name), "family", detector_name))
