from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import pandas as pd


@dataclass(frozen=True)
class ModelLoadResult:
    predictor: "BackbonePredictor"
    warnings: list[str] = field(default_factory=list)


class BackbonePredictor(Protocol):
    model_name: str
    model_version: str
    required_features: list[str]

    def predict(self, features: pd.DataFrame) -> pd.DataFrame:
        ...
