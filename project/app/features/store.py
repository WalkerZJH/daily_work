from __future__ import annotations

from datetime import date

from app.features.snapshot import FeatureSnapshot


class FeatureStore:
    def __init__(self) -> None:
        self._snapshots: dict[tuple[str, date], FeatureSnapshot] = {}

    def put(self, snapshot: FeatureSnapshot) -> None:
        key = (snapshot.unit_id, snapshot.as_of_date)
        existing = self._snapshots.get(key)
        if existing is None:
            self._snapshots[key] = snapshot
            return
        merged_features = {**existing.features, **snapshot.features}
        merged_versions = {**existing.feature_versions, **snapshot.feature_versions}
        merged_producers = {**existing.produced_by, **snapshot.produced_by}
        merged_warnings = list(dict.fromkeys([*existing.warnings, *snapshot.warnings]))
        self._snapshots[key] = existing.model_copy(
            update={
                "features": merged_features,
                "feature_versions": merged_versions,
                "produced_by": merged_producers,
                "warnings": merged_warnings,
            }
        )

    def put_many(self, snapshots: list[FeatureSnapshot]) -> None:
        for snapshot in snapshots:
            self.put(snapshot)

    def get(self, unit_id: str, as_of_date: date) -> FeatureSnapshot | None:
        return self._snapshots.get((unit_id, as_of_date))

    def query(
        self,
        as_of_date: date | None = None,
        feature_names: list[str] | None = None,
        grain: str | None = None,
    ) -> list[FeatureSnapshot]:
        snapshots = list(self._snapshots.values())
        if as_of_date is not None:
            snapshots = [snapshot for snapshot in snapshots if snapshot.as_of_date == as_of_date]
        if grain is not None:
            snapshots = [snapshot for snapshot in snapshots if snapshot.analysis_grain == grain]
        if feature_names:
            snapshots = [
                snapshot
                for snapshot in snapshots
                if all(name in snapshot.features for name in feature_names)
            ]
        return snapshots

    def clear(self) -> None:
        self._snapshots.clear()
