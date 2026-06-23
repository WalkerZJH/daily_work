from __future__ import annotations

from app.detectors.base import DetectorResult, base_result, missing_features, missing_required_result
from app.features.snapshot import FeatureSnapshot
from app.schemas.config import AppConfig


class NewTerminalDetector:
    name = "new_terminal"
    version = "v0"
    required_features = ["has_recent_order", "has_baseline_order", "first_order_date"]
    supported_grains = ["product_line", "sku"]

    def detect(self, snapshots: list[FeatureSnapshot], config: AppConfig) -> list[DetectorResult]:
        results: list[DetectorResult] = []
        for snapshot in snapshots:
            if snapshot.analysis_grain not in self.supported_grains:
                continue
            if missing_features(snapshot, self.required_features):
                results.append(missing_required_result(self.name, snapshot, self.required_features))
                continue
            features = snapshot.features
            hit = bool(features.get("has_recent_order")) and not bool(features.get("has_baseline_order"))
            results.append(
                base_result(
                    self.name,
                    snapshot,
                    hit=hit,
                    severity=42 if hit else 0,
                    confidence=0.9 if hit else 0.5,
                    reason_code="RECENT_FIRST_PURCHASE" if hit else "NOT_NEW_TERMINAL",
                    metrics={
                        "is_new_terminal": hit,
                        "first_order_time": features.get("first_order_date"),
                        "has_recent_order": features.get("has_recent_order"),
                        "has_baseline_order": features.get("has_baseline_order"),
                    },
                )
            )
        return results
