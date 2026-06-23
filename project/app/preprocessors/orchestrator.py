from __future__ import annotations

from collections import Counter

from app.features.lineage import FeatureLineageRecord
from app.features.snapshot import FeatureSnapshot
from app.preprocessors.base import PreprocessContext
from app.preprocessors.registry import PreprocessorRegistry


class PreprocessOrchestrator:
    def __init__(self, registry: PreprocessorRegistry) -> None:
        self.registry = registry

    def run(
        self,
        context: PreprocessContext,
        enabled_preprocessors: list[str] | None = None,
    ) -> tuple[list[FeatureSnapshot], list[FeatureLineageRecord]]:
        selected_names = enabled_preprocessors or self._enabled_names_from_config(context)
        lineage: list[FeatureLineageRecord] = []
        for name in selected_names:
            preprocessor = self.registry.get(name)
            snapshots = preprocessor.run(context)
            context.feature_store.put_many(snapshots)
            warnings = list(dict.fromkeys(w for snapshot in snapshots for w in snapshot.warnings))
            lineage.append(
                FeatureLineageRecord(
                    preprocessor_name=name,
                    version=preprocessor.version,
                    output_features=preprocessor.output_features,
                    snapshot_count=len(snapshots),
                    warnings=warnings,
                )
            )
        return context.feature_store.query(as_of_date=context.as_of_date), lineage

    def warning_summary(self, snapshots: list[FeatureSnapshot]) -> dict[str, int]:
        counter: Counter[str] = Counter()
        for snapshot in snapshots:
            counter.update(snapshot.warnings)
        return dict(counter)

    @staticmethod
    def _enabled_names_from_config(context: PreprocessContext) -> list[str]:
        preprocessors = context.config.preprocessors
        order = [
            "unit_builder",
            "temporal_window",
            "demand_shape",
            "drug_grouping",
            "treatment_cycle",
            "substitution_features",
            "cohort_context",
            "seasonality",
        ]
        return [
            name
            for name in order
            if getattr(preprocessors, name).enabled
        ]
