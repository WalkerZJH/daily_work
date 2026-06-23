from __future__ import annotations

from app.detectors.base import DetectorResult, base_result, missing_features, missing_required_result, number
from app.features.snapshot import FeatureSnapshot
from app.schemas.config import AppConfig


class SubstitutionRiskDetector:
    name = "substitution_risk"
    version = "v0"
    required_features = [
        "own_recent_qty",
        "own_baseline_qty",
        "same_group_recent_qty",
        "same_group_baseline_qty",
        "substitute_qty_delta",
        "substitution_feature_confidence",
    ]
    supported_grains = ["product_line", "sku"]

    def detect(self, snapshots: list[FeatureSnapshot], config: AppConfig) -> list[DetectorResult]:
        results: list[DetectorResult] = []
        detector_config = config.detectors.substitution_risk
        for snapshot in snapshots:
            if snapshot.analysis_grain not in self.supported_grains:
                continue
            if missing_features(snapshot, self.required_features):
                results.append(missing_required_result(self.name, snapshot, self.required_features))
                continue
            features = snapshot.features
            own_recent = number(features.get("own_recent_qty"))
            own_base = number(features.get("own_baseline_qty"))
            group_recent = number(features.get("same_group_recent_qty"))
            group_base = number(features.get("same_group_baseline_qty"))
            confidence = number(features.get("substitution_feature_confidence"))
            own_ratio = own_recent / own_base if own_base > 0 else 1.0
            group_ratio = group_recent / group_base if group_base > 0 else 1.0
            own_drop = own_base > 0 and own_ratio < detector_config.own_drop_threshold
            group_stable = group_ratio >= detector_config.same_group_stable_threshold
            limited = "LIMITED_TO_OWN_PRODUCTS" in snapshot.warnings or confidence < 0.3
            hit = own_drop and group_stable and not limited
            reason = "POSSIBLE_INTERNAL_SUBSTITUTION" if hit else "INSUFFICIENT_MARKET_DATA"
            warnings = ["LIMITED_TO_OWN_PRODUCTS"] if limited else []
            results.append(
                base_result(
                    self.name,
                    snapshot,
                    hit=hit,
                    severity=55 if hit else 0,
                    confidence=confidence if hit else min(confidence, 0.25),
                    reason_code=reason,
                    metrics={
                        "own_qty_ratio": own_ratio,
                        "same_group_qty_ratio": group_ratio,
                        "substitute_qty_delta": number(features.get("substitute_qty_delta")),
                        "substitution_feature_confidence": confidence,
                    },
                    warnings=warnings,
                )
            )
        return results
