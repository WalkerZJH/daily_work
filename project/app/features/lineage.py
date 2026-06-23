from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FeatureLineageRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preprocessor_name: str
    version: str
    output_features: list[str] = Field(default_factory=list)
    snapshot_count: int
    warnings: list[str] = Field(default_factory=list)
