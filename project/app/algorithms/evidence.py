from __future__ import annotations

from typing import Any

from app.schemas.algorithm import BaselineMetrics, DemandShapeResult, DetectorResult


def build_structured_evidence(
    metrics: BaselineMetrics,
    demand_shape: DemandShapeResult,
    detector_results: list[DetectorResult],
) -> dict[str, Any]:
    return {
        "analysis_unit": {
            "org_code": metrics.org_code,
            "product_line_code": metrics.product_line_code,
        },
        "windows": {
            "as_of_date": metrics.as_of_date.isoformat(),
            "recent_start": metrics.recent_start.isoformat(),
            "baseline_start": metrics.baseline_start.isoformat(),
            "baseline_end": metrics.baseline_end.isoformat(),
        },
        "baseline_metrics": metrics.model_dump(mode="json"),
        "demand_shape": demand_shape.model_dump(mode="json"),
        "detectors": [
            {
                "detector_name": result.detector_name,
                "hit": result.hit,
                "severity": result.severity,
                "confidence": result.confidence,
                "reason_code": result.reason_code,
                "metrics": result.metrics,
                "evidence_refs": [ref.model_dump(mode="json") for ref in result.evidence_refs],
                "warnings": result.warnings,
            }
            for result in detector_results
        ],
    }
