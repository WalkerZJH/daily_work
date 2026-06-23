from __future__ import annotations

from app.algorithms.detectors.helpers import clamp
from app.schemas.algorithm import BaselineMetrics, DetectorResult, EvidenceRef
from app.schemas.config import SkuShrinkConfig


def detect_sku_shrink(metrics: BaselineMetrics, config: SkuShrinkConfig) -> DetectorResult:
    warnings: list[str] = []
    base_count = metrics.baseline_active_sku_count
    recent_count = metrics.recent_active_sku_count
    if base_count < config.min_base_sku_count:
        warnings.append("Baseline active SKU/spec count is below detector minimum.")
        return DetectorResult(
            detector_name="sku_shrink",
            hit=False,
            severity=0,
            confidence=0.25,
            reason_code="BASELINE_SKU_TOO_FEW",
            metrics={
                "baseline_active_sku_count": base_count,
                "recent_active_sku_count": recent_count,
                "min_base_sku_count": config.min_base_sku_count,
            },
            evidence_refs=_metric_refs(metrics),
            warnings=warnings,
        )

    shrink_ratio = 1 - (recent_count / base_count)
    hit = shrink_ratio >= config.shrink_threshold
    severity = (
        clamp((shrink_ratio - config.shrink_threshold) / (1 - config.shrink_threshold) * 100)
        if hit
        else 0
    )
    confidence = min(1.0, 0.5 + base_count / 10)

    return DetectorResult(
        detector_name="sku_shrink",
        hit=hit,
        severity=severity,
        confidence=float(confidence),
        reason_code="SKU_SHRINK" if hit else "SKU_STABLE",
        metrics={
            "baseline_active_sku_count": base_count,
            "recent_active_sku_count": recent_count,
            "shrink_ratio": shrink_ratio,
            "shrink_threshold": config.shrink_threshold,
        },
        evidence_refs=_metric_refs(metrics),
        warnings=warnings,
    )


def _metric_refs(metrics: BaselineMetrics) -> list[EvidenceRef]:
    refs: list[EvidenceRef] = []
    for order_id in (metrics.baseline_order_ids[-4:] + metrics.recent_order_ids[-4:])[:8]:
        refs.append(EvidenceRef(ref_type="order", ref_id=order_id, order_id=order_id))
    return refs
