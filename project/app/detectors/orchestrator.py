from __future__ import annotations

from dataclasses import dataclass

from app.detectors.base import DetectorResult
from app.detectors.registry import DetectorRegistry
from app.features.snapshot import FeatureSnapshot
from app.schemas.config import AppConfig


@dataclass(frozen=True)
class DetectorRunSummary:
    results: list[DetectorResult]
    skipped_due_to_missing_features: int


class DetectorOrchestrator:
    def __init__(self, registry: DetectorRegistry) -> None:
        self.registry = registry

    def run(
        self,
        snapshots: list[FeatureSnapshot],
        config: AppConfig,
        enabled_detectors: list[str] | None = None,
    ) -> DetectorRunSummary:
        selected_names = enabled_detectors or self._enabled_names_from_config(config)
        results: list[DetectorResult] = []
        for name in selected_names:
            detector = self.registry.get(name)
            results.extend(detector.detect(snapshots, config))
        skipped = sum(1 for result in results if result.required_features_missing)
        return DetectorRunSummary(results=results, skipped_due_to_missing_features=skipped)

    @staticmethod
    def _enabled_names_from_config(config: AppConfig) -> list[str]:
        order = [
            "inactive_terminal",
            "new_terminal",
            "ip_interval",
            "frequency_drop",
            "sku_shrink",
            "substitution_risk",
            "cycle_deviation",
        ]
        return [name for name in order if getattr(config.detectors, name).enabled]
