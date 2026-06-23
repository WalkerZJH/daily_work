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


class IpIntervalDetector:
    name = "ip_interval"
    version = "v0"
    required_features = ["inactive_days", "historical_median_ipi", "historical_mad_ipi", "demand_shape"]
    supported_grains = ["product_line", "sku"]

    def detect(self, snapshots: list[FeatureSnapshot], config: AppConfig) -> list[DetectorResult]:
        results: list[DetectorResult] = []
        detector_config = config.detectors.ip_interval
        for snapshot in snapshots:
            if snapshot.analysis_grain not in self.supported_grains:
                continue
            if missing_features(snapshot, self.required_features):
                results.append(missing_required_result(self.name, snapshot, self.required_features))
                continue
            features = snapshot.features
            inactive_days = number(features.get("inactive_days"))
            median_ipi = number(features.get("historical_median_ipi"))
            mad_ipi = max(number(features.get("historical_mad_ipi")), 1)
            threshold_multiplier, confidence_multiplier = demand_shape_sensitivity(
                features.get("demand_shape")
            )
            robust_z = (inactive_days - median_ipi) / (1.4826 * mad_ipi)
            z_hit = detector_config.z_hit * threshold_multiplier
            z_full = detector_config.z_full * threshold_multiplier
            hit = robust_z >= z_hit
            severity = 0 if not hit else min(100, 35 + (robust_z - z_hit) / max(z_full - z_hit, 1) * 65)
            results.append(
                base_result(
                    self.name,
                    snapshot,
                    hit=hit,
                    severity=severity,
                    confidence=(0.8 if hit else 0.45) * confidence_multiplier,
                    reason_code="IPI_ROBUST_Z_HIGH" if hit else "IPI_WITHIN_RANGE",
                    metrics={
                        "inactive_days": inactive_days,
                        "historical_median_ipi": median_ipi,
                        "historical_mad_ipi": mad_ipi,
                        "robust_z": robust_z,
                        "z_hit": z_hit,
                        "demand_shape": features.get("demand_shape"),
                    },
                )
            )
        return results
