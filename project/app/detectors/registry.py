from __future__ import annotations

from app.detectors.base import BaseDetector
from app.detectors.cycle_deviation import CycleDeviationDetector
from app.detectors.frequency_drop import FrequencyDropDetector
from app.detectors.inactive_terminal import InactiveTerminalDetector
from app.detectors.ip_interval import IpIntervalDetector
from app.detectors.new_terminal import NewTerminalDetector
from app.detectors.sku_shrink import SkuShrinkDetector
from app.detectors.substitution_risk import SubstitutionRiskDetector


class DetectorRegistry:
    def __init__(self) -> None:
        self._detectors: dict[str, BaseDetector] = {}

    def register(self, detector: BaseDetector) -> None:
        if detector.name in self._detectors:
            raise ValueError(f"Duplicate detector name: {detector.name}")
        self._detectors[detector.name] = detector

    def get(self, name: str) -> BaseDetector:
        return self._detectors[name]

    def list(self) -> list[BaseDetector]:
        return list(self._detectors.values())

    def names(self) -> list[str]:
        return list(self._detectors.keys())


def build_default_detector_registry() -> DetectorRegistry:
    registry = DetectorRegistry()
    for detector in [
        InactiveTerminalDetector(),
        NewTerminalDetector(),
        IpIntervalDetector(),
        FrequencyDropDetector(),
        SkuShrinkDetector(),
        SubstitutionRiskDetector(),
        CycleDeviationDetector(),
    ]:
        registry.register(detector)
    return registry
