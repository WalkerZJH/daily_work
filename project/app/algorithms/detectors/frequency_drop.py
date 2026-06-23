from __future__ import annotations

from app.algorithms.detectors.helpers import clamp
from app.schemas.algorithm import BaselineMetrics, DetectorResult, EvidenceRef
from app.schemas.config import FrequencyDropConfig


def detect_frequency_drop(
    metrics: BaselineMetrics,
    config: FrequencyDropConfig,
) -> DetectorResult:
    warnings: list[str] = []
    base_rate = metrics.baseline_monthly_order_rate
    recent_rate = metrics.recent_monthly_order_rate
    if base_rate < config.min_base_monthly_orders:
        warnings.append("Baseline monthly order rate is below detector minimum.")
        return DetectorResult(
            detector_name="frequency_drop",
            hit=False,
            severity=0,
            confidence=0.25,
            reason_code="BASELINE_TOO_SPARSE",
            metrics={
                "baseline_monthly_order_rate": base_rate,
                "recent_monthly_order_rate": recent_rate,
                "min_base_monthly_orders": config.min_base_monthly_orders,
            },
            evidence_refs=_metric_refs(metrics),
            warnings=warnings,
        )

    rate_ratio = recent_rate / base_rate if base_rate > 0 else 0.0
    hit = rate_ratio < config.drop_threshold
    severity = (
        clamp((config.drop_threshold - rate_ratio) / config.drop_threshold * 100) if hit else 0
    )
    confidence = min(1.0, 0.45 + metrics.baseline_orders / 20)

    return DetectorResult(
        detector_name="frequency_drop",
        hit=hit,
        severity=severity,
        confidence=float(confidence),
        reason_code="FREQUENCY_DROP" if hit else "FREQUENCY_STABLE",
        metrics={
            "baseline_monthly_order_rate": base_rate,
            "recent_monthly_order_rate": recent_rate,
            "rate_ratio": rate_ratio,
            "drop_threshold": config.drop_threshold,
            "baseline_orders": metrics.baseline_orders,
            "recent_orders": metrics.recent_orders,
        },
        evidence_refs=_metric_refs(metrics),
        warnings=warnings,
    )


def _metric_refs(metrics: BaselineMetrics) -> list[EvidenceRef]:
    refs: list[EvidenceRef] = []
    for order_id in (metrics.baseline_order_ids[-3:] + metrics.recent_order_ids[-3:])[:6]:
        refs.append(EvidenceRef(ref_type="order", ref_id=order_id, order_id=order_id))
    return refs
