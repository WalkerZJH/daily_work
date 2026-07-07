from __future__ import annotations

import pandas as pd

from .base import DetectorOutput, RuntimeDetector, to_frame


class IntervalOverdueDetector(RuntimeDetector):
    detector_name = "purchase_interval_overdue_warning"
    detector_family = "interval"

    def run(self, candidates: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
        merged = candidates[["candidate_id", "entity_id", "horizon"]].merge(
            features[["entity_id", "horizon", "current_interval_over_median"]],
            on=["entity_id", "horizon"],
            how="left",
        )
        rows = []
        for row in merged.itertuples():
            value = float(getattr(row, "current_interval_over_median", 0) or 0)
            hit = value >= 1.5
            rows.append(
                DetectorOutput(
                    candidate_id=str(row.candidate_id),
                    detector_name=self.detector_name,
                    detector_family=self.detector_family,
                    hit_flag=bool(hit),
                    severity="medium" if hit else "low",
                    confidence="medium",
                    evidence_type="interval_overdue",
                    reason_code="over_historical_interval" if hit else "within_interval_context",
                    metric_name="current_interval_over_median",
                    metric_value=value,
                    visibility_level="business_visible",
                    caveat="interval evidence is not a calibrated probability",
                    forbidden_claims="definitive_churn_claim",
                )
            )
        return to_frame(rows)
