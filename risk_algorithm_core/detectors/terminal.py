from __future__ import annotations

import pandas as pd

from .base import DetectorOutput, RuntimeDetector, to_frame


class TerminalLossDetector(RuntimeDetector):
    detector_name = "terminal_loss_warning"
    detector_family = "terminal"

    def run(self, candidates: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for row in candidates[candidates["candidate_type"].eq("recurring")].itertuples():
            hit = float(row.churn_probability_H) >= 0.6
            rows.append(
                DetectorOutput(
                    candidate_id=str(row.candidate_id),
                    detector_name=self.detector_name,
                    detector_family=self.detector_family,
                    hit_flag=bool(hit),
                    severity="medium" if hit else "low",
                    confidence="medium",
                    evidence_type="risk_review",
                    reason_code="monthly_risk_score_high" if hit else "risk_score_context",
                    metric_name="churn_probability_H",
                    metric_value=float(row.churn_probability_H),
                    visibility_level="business_visible",
                    caveat="risk review clue, not a definitive churn claim",
                    forbidden_claims="definitive_churn_claim",
                )
            )
        return to_frame(rows)
