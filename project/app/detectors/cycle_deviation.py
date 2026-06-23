from __future__ import annotations

from app.detectors.base import DetectorResult, base_result, missing_features, missing_required_result, number
from app.features.snapshot import FeatureSnapshot
from app.schemas.config import AppConfig


class CycleDeviationDetector:
    name = "cycle_deviation"
    version = "v0"
    required_features = ["inactive_days", "typical_refill_days", "cycle_prior_confidence"]
    supported_grains = ["product_line", "sku"]

    def detect(self, snapshots: list[FeatureSnapshot], config: AppConfig) -> list[DetectorResult]:
        results: list[DetectorResult] = []
        detector_config = config.detectors.cycle_deviation
        for snapshot in snapshots:
            if snapshot.analysis_grain not in self.supported_grains:
                continue
            missing = missing_features(snapshot, self.required_features)
            if missing:
                result = missing_required_result(self.name, snapshot, self.required_features)
                result.warnings.append("MISSING_TREATMENT_CYCLE_PRIOR")
                results.append(result)
                continue
            inactive_days = number(snapshot.features.get("inactive_days"))
            refill_days = max(number(snapshot.features.get("typical_refill_days")), 1)
            cycle_confidence = number(snapshot.features.get("cycle_prior_confidence"))
            threshold = refill_days * detector_config.deviation_multiplier
            hit = inactive_days >= threshold and cycle_confidence >= detector_config.min_cycle_confidence
            results.append(
                base_result(
                    self.name,
                    snapshot,
                    hit=hit,
                    severity=min(100, 50 + (inactive_days / threshold - 1) * 50) if hit else 0,
                    confidence=(0.8 if hit else 0.2) * cycle_confidence,
                    reason_code="CYCLE_DEVIATION_HIGH" if hit else "MISSING_OR_WEAK_CYCLE_PRIOR",
                    metrics={
                        "inactive_days": inactive_days,
                        "typical_refill_days": refill_days,
                        "threshold_days": threshold,
                        "cycle_prior_confidence": cycle_confidence,
                    },
                    warnings=["MISSING_TREATMENT_CYCLE_PRIOR"] if cycle_confidence < 0.3 else [],
                )
            )
        return results
