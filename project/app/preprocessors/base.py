from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol

import pandas as pd

from app.features.snapshot import FeatureSnapshot
from app.features.store import FeatureStore
from app.schemas.config import AppConfig


@dataclass(frozen=True)
class PreprocessContext:
    canonical_orders: pd.DataFrame
    dim_drug: pd.DataFrame
    dim_org: pd.DataFrame
    product_line_mapping: pd.DataFrame
    optional_tables: dict[str, pd.DataFrame]
    as_of_date: date
    config: AppConfig
    feature_store: FeatureStore


@dataclass(frozen=True)
class PreprocessRunSummary:
    preprocessor_name: str
    version: str
    snapshot_count: int
    output_features: list[str]
    warnings: list[str] = field(default_factory=list)


class BasePreprocessor(Protocol):
    name: str
    version: str
    required_inputs: list[str]
    output_features: list[str]
    output_grain: str
    as_of_date_sensitive: bool

    def run(self, context: PreprocessContext) -> list[FeatureSnapshot]:
        ...


def unit_id(org_code: str, analysis_grain: str, target_code: str) -> str:
    return f"{org_code}|{analysis_grain}|{target_code}"
