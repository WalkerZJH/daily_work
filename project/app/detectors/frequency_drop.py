from __future__ import annotations

from app.detectors.base import DetectorResult, base_result, missing_features, missing_required_result, number
from app.features.snapshot import FeatureSnapshot
from app.schemas.config import AppConfig


class FrequencyDropDetector:
    name = "frequency_drop"
    version = "v0"
    required_features = ["recent_order_count", "baseline_order_count"]
    supported_grains = ["product_line", "sku"]

    def detect(self, snapshots: list[FeatureSnapshot], config: AppConfig) -> list[DetectorResult]:
        results: list[DetectorResult] = []
        detector_config = config.detectors.frequency_drop
        recent_months = config.preprocessors.temporal_window.recent_days / 30.4375
        baseline_months = config.preprocessors.temporal_window.baseline_days / 30.4375
        for snapshot in snapshots:
            if snapshot.analysis_grain not in self.supported_grains:
                continue
            if missing_features(snapshot, self.required_features):
                results.append(missing_required_result(self.name, snapshot, self.required_features))
                continue
            recent_rate = number(snapshot.features.get("recent_order_count")) / recent_months
            baseline_rate = number(snapshot.features.get("baseline_order_count")) / baseline_months
            rate_ratio = recent_rate / baseline_rate if baseline_rate > 0 else 1.0
            hit = (
                baseline_rate >= detector_config.min_base_monthly_orders
                and rate_ratio < detector_config.drop_threshold
            )
            severity = min(100, (1 - rate_ratio / detector_config.drop_threshold) * 100) if hit else 0
            results.append(
                base_result(
                    self.name,
                    snapshot,
                    hit=hit,
                    severity=severity,
                    confidence=0.82 if hit else 0.5,
                    reason_code="ORDER_FREQUENCY_DROP" if hit else "ORDER_FREQUENCY_STABLE",
                    metrics={
                        "recent_monthly_order_rate": recent_rate,
                        "baseline_monthly_order_rate": baseline_rate,
                        "rate_ratio": rate_ratio,
                    },
                )
            )
        return results
