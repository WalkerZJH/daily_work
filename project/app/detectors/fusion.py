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
    score = min(100.0, sum(family_scores.values()) / max(len(family_scores), 1) if family_scores else 0.0)
    warning_count = sum(len(result.warnings) for result in results)
    confidence_values = [result.confidence for result in hit_results]
    confidence = sum(confidence_values) / len(confidence_values) if confidence_values else 0.0
    confidence = max(0.0, confidence - min(0.3, warning_count * 0.02))
    if confidence < config.fusion.min_confidence_for_alert or score <= 0:
        risk_level = "none"
    elif score >= config.fusion.red_score:
        risk_level = "red"
    elif score >= config.fusion.orange_score:
        risk_level = "orange"
    elif score >= config.fusion.yellow_score:
        risk_level = "yellow"
    else:
        risk_level = "none"

    return {
        "risk_score": round(score, 2),
        "risk_level": risk_level,
        "confidence": round(confidence, 4),
        "triggered_detectors": [result.detector_name for result in hit_results],
        "triggered_families": sorted(family_scores),
        "family_scores": family_scores,
        "reason_code": "DETECTOR_FAMILY_FUSION" if hit_results else "NO_DETECTOR_HIT",
    }


def _family_for(detector_name: str, config: AppConfig) -> str:
    return str(getattr(getattr(config.detectors, detector_name), "family", detector_name))
