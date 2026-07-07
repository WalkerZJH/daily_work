from __future__ import annotations

import pandas as pd

from .base import DetectorOutput, RuntimeDetector, to_frame


class OneShotAttentionDetector(RuntimeDetector):
    detector_name = "new_terminal_detection"
    detector_family = "one_shot"

    def run(self, candidates: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for row in candidates[candidates["candidate_type"].eq("one_shot")].itertuples():
            rows.append(
                DetectorOutput(
                    candidate_id=str(row.candidate_id),
                    detector_name=self.detector_name,
                    detector_family=self.detector_family,
                    hit_flag=True,
                    severity="info",
                    confidence="medium",
                    evidence_type="new_terminal_attention",
                    reason_code="one_shot_selected_for_attention",
                    metric_name="one_shot_attention_score",
                    metric_value=float(getattr(row, "one_shot_attention_score", 0) or 0),
                    visibility_level="business_visible",
                    caveat="new terminal attention is not recurring churn",
                    forbidden_claims="recurring_churn_probability_claim",
                )
            )
        return to_frame(rows)
