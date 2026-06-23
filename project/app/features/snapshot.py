from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FeatureSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit_id: str
    org_code: str
    analysis_grain: str
    target_code: str
    as_of_date: date
    features: dict[str, Any] = Field(default_factory=dict)
    feature_versions: dict[str, str] = Field(default_factory=dict)
    produced_by: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)

    def with_features(
        self,
        features: dict[str, Any],
        produced_by: str,
        version: str,
        warnings: list[str] | None = None,
    ) -> FeatureSnapshot:
        merged_features = dict(self.features)
        merged_versions = dict(self.feature_versions)
        merged_producers = dict(self.produced_by)
        for name, value in features.items():
            merged_features[name] = value
            merged_versions[name] = version
            merged_producers[name] = produced_by
        merged_warnings = list(dict.fromkeys([*self.warnings, *(warnings or [])]))
        return self.model_copy(
            update={
                "features": merged_features,
                "feature_versions": merged_versions,
                "produced_by": merged_producers,
                "warnings": merged_warnings,
            }
        )


class FeatureFrame(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    snapshots: list[FeatureSnapshot] = Field(default_factory=list)
