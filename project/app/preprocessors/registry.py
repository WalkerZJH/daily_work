from __future__ import annotations

from app.preprocessors.base import BasePreprocessor
from app.preprocessors.cohort_context import CohortContextPreprocessor
from app.preprocessors.demand_shape import DemandShapePreprocessor
from app.preprocessors.drug_grouping import DrugGroupingPreprocessor
from app.preprocessors.seasonality import SeasonalityPreprocessor
from app.preprocessors.substitution_features import SubstitutionFeaturePreprocessor
from app.preprocessors.temporal_window import TemporalWindowPreprocessor
from app.preprocessors.treatment_cycle import TreatmentCyclePreprocessor
from app.preprocessors.unit_builder import UnitBuilderPreprocessor


class PreprocessorRegistry:
    def __init__(self) -> None:
        self._preprocessors: dict[str, BasePreprocessor] = {}

    def register(self, preprocessor: BasePreprocessor) -> None:
        if preprocessor.name in self._preprocessors:
            raise ValueError(f"Duplicate preprocessor name: {preprocessor.name}")
        duplicate_features = self._find_duplicate_output_features(preprocessor)
        if duplicate_features:
            raise ValueError(
                f"Duplicate output feature(s) from {preprocessor.name}: "
                f"{', '.join(duplicate_features)}"
            )
        self._preprocessors[preprocessor.name] = preprocessor

    def get(self, name: str) -> BasePreprocessor:
        return self._preprocessors[name]

    def list(self) -> list[BasePreprocessor]:
        return list(self._preprocessors.values())

    def names(self) -> list[str]:
        return list(self._preprocessors.keys())

    def _find_duplicate_output_features(self, preprocessor: BasePreprocessor) -> list[str]:
        existing = {
            feature
            for registered in self._preprocessors.values()
            for feature in registered.output_features
        }
        return [feature for feature in preprocessor.output_features if feature in existing]


def build_default_preprocessor_registry() -> PreprocessorRegistry:
    registry = PreprocessorRegistry()
    for preprocessor in [
        UnitBuilderPreprocessor(),
        TemporalWindowPreprocessor(),
        DemandShapePreprocessor(),
        DrugGroupingPreprocessor(),
        TreatmentCyclePreprocessor(),
        SubstitutionFeaturePreprocessor(),
        CohortContextPreprocessor(),
        SeasonalityPreprocessor(),
    ]:
        registry.register(preprocessor)
    return registry
