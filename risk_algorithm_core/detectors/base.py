"""Base detector types."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd


@dataclass(frozen=True, slots=True)
class DetectorOutput:
    candidate_id: str
    detector_name: str
    detector_family: str
    hit_flag: bool
    severity: str
    confidence: str
    evidence_type: str
    reason_code: str
    metric_name: str
    metric_value: float | str
    visibility_level: str
    caveat: str
    forbidden_claims: str


class RuntimeDetector:
    detector_name = "base"
    detector_family = "base"

    def run(self, candidates: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError


def to_frame(rows: list[DetectorOutput]) -> pd.DataFrame:
    return pd.DataFrame([asdict(row) for row in rows])
