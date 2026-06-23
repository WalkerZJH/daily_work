from __future__ import annotations

from app.detectors.base import DetectorResult, base_result, missing_features, missing_required_result, number
from app.features.snapshot import FeatureSnapshot
from app.schemas.config import AppConfig


class SkuShrinkDetector:
    name = "sku_shrink"
    version = "v0"
    required_features = ["recent_active_sku_count", "baseline_active_sku_count"]
    supported_grains = ["product_line"]

    def detect(self, snapshots: list[FeatureSnapshot], config: AppConfig) -> list[DetectorResult]:
        results: list[DetectorResult] = []
        detector_config = config.detectors.sku_shrink
        for snapshot in snapshots:
            if snapshot.analysis_grain not in self.supported_grains:
                continue
            if missing_features(snapshot, self.required_features):
                results.append(missing_required_result(self.name, snapshot, self.required_features))
                continue
            recent_count = number(snapshot.features.get("recent_active_sku_count"))
            baseline_count = number(snapshot.features.get("baseline_active_sku_count"))
            shrink_ratio = 0.0 if baseline_count <= 0 else max(0.0, (baseline_count - recent_count) / baseline_count)
            hit = baseline_count >= detector_config.min_base_sku_count and shrink_ratio >= detector_config.shrink_threshold
            severity = min(100, shrink_ratio * 100) if hit else 0
            results.append(
                base_result(
                    self.name,
                    snapshot,
                    hit=hit,
                    severity=severity,
                    confidence=0.8 if hit else 0.45,
                    reason_code="ACTIVE_SKU_SHRINK" if hit else "ACTIVE_SKU_STABLE",
                    metrics={
                        "recent_active_sku_count": recent_count,
                        "baseline_active_sku_count": baseline_count,
                        "shrink_ratio": shrink_ratio,
                    },
                )
            )
        return results
