from __future__ import annotations

import pandas as pd

from .base import DetectorOutput, RuntimeDetector, to_frame


class QuantityDropDetector(RuntimeDetector):
    detector_name = "purchase_quantity_fluctuation_warning"
    detector_family = "quantity"

    def run(self, candidates: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
        merged = candidates[["candidate_id", "entity_id", "horizon"]].merge(
            features[["entity_id", "horizon", "quantity_ratio"]],
            on=["entity_id", "horizon"],
            how="left",
        )
        rows = []
        for row in merged.itertuples():
            value = float(getattr(row, "quantity_ratio", 1) or 0)
            hit = value < 0.5
            rows.append(
                DetectorOutput(
                    candidate_id=str(row.candidate_id),
                    detector_name=self.detector_name,
                    detector_family=self.detector_family,
                    hit_flag=bool(hit),
                    severity="low" if hit else "info",
                    confidence="low",
                    evidence_type="quantity_drop",
                    reason_code="recent_quantity_below_baseline" if hit else "quantity_context",
                    metric_name="quantity_ratio",
                    metric_value=value,
                    visibility_level="manager_visible",
                    caveat="quantity evidence is auxiliary and review-required",
                    forbidden_claims="causal_claim",
                )
            )
        return to_frame(rows)
