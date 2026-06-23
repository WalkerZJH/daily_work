from __future__ import annotations

from app.detectors.base import (
    DetectorResult,
    base_result,
    demand_shape_sensitivity,
    missing_features,
    missing_required_result,
    number,
)
from app.features.snapshot import FeatureSnapshot
from app.schemas.config import AppConfig


class InactiveTerminalDetector:
    name = "inactive_terminal"
    version = "v0"
    required_features = ["inactive_days", "demand_shape"]
    supported_grains = ["product_line", "sku"]

    def detect(self, snapshots: list[FeatureSnapshot], config: AppConfig) -> list[DetectorResult]:
        results: list[DetectorResult] = []
        detector_config = config.detectors.inactive_terminal
        for snapshot in snapshots:
            if snapshot.analysis_grain not in self.supported_grains:
                continue
            if missing_features(snapshot, self.required_features):
                results.append(missing_required_result(self.name, snapshot, self.required_features))
                continue
            features = snapshot.features
            inactive_days = number(features.get("inactive_days"))
            interval = features.get("typical_refill_days")
            reference_source = "typical_refill_days"
            if interval is None:
                interval = features.get("historical_median_ipi") or features.get("adi")
                reference_source = "historical_median_ipi_or_adi"
            expected_interval = max(number(interval, 30), 1)
            threshold_multiplier, confidence_multiplier = demand_shape_sensitivity(
                features.get("demand_shape")
            )
            threshold = max(
                detector_config.min_inactive_days,
                expected_interval * detector_config.inactive_multiplier * threshold_multiplier,
            )
            ratio = inactive_days / threshold if threshold else 0
            hit = inactive_days >= threshold
            severity = min(100, 45 + (ratio - 1) * 55) if hit else max(0, ratio * 30)
            confidence = (0.85 if hit else 0.45) * confidence_multiplier
            results.append(
                base_result(
                    self.name,
                    snapshot,
                    hit=hit,
                    severity=severity,
                    confidence=confidence,
                    reason_code="INACTIVE_DAYS_EXCEED_EXPECTED" if hit else "WITHIN_EXPECTED_INTERVAL",
                    metrics={
                        "inactive_days": inactive_days,
                        "expected_interval_days": expected_interval,
                        "threshold_days": threshold,
                        "reference_source": reference_source,
                        "demand_shape": features.get("demand_shape"),
                    },
                )
            )
        return results
