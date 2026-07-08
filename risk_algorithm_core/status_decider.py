"""Candidate status decision for monthly worklists."""

from __future__ import annotations

import numpy as np
import pandas as pd


class StatusDecider:
    def decide(self, candidates: pd.DataFrame, features: pd.DataFrame, detector_outputs: pd.DataFrame) -> pd.DataFrame:
        out = candidates.copy()
        hit_counts = detector_outputs.groupby("candidate_id").agg(
            detector_hit_count=("hit_flag", lambda x: int(pd.Series(x).fillna(False).sum())),
            strong_detector_hit_count=("severity", lambda x: int(pd.Series(x).eq("high").sum())),
        ).reset_index() if not detector_outputs.empty else pd.DataFrame(columns=["candidate_id", "detector_hit_count", "strong_detector_hit_count"])
        out = out.merge(hit_counts, on="candidate_id", how="left")
        out["detector_hit_count"] = out["detector_hit_count"].fillna(0).astype(int)
        out["strong_detector_hit_count"] = out["strong_detector_hit_count"].fillna(0).astype(int)
        out["is_one_shot"] = out["candidate_type"].eq("one_shot")
        out["is_observation"] = out["candidate_type"].isin(["observation", "demand_shape_observation"])
        out["is_high_risk"] = out["candidate_type"].eq("recurring") & (out["churn_probability_H"] >= 0.6)
        out["final_candidate_status"] = np.select(
            [
                out["is_one_shot"],
                out["is_observation"],
                out["is_high_risk"],
                out["candidate_type"].eq("recurring"),
            ],
            ["one_shot_attention", "observation_only", "priority_review", "manual_review"],
            default="not_actionable",
        )
        out["review_priority"] = np.select(
            [out["final_candidate_status"].eq("priority_review"), out["final_candidate_status"].eq("manual_review"), out["final_candidate_status"].eq("observation_only")],
            ["P1", "P2", "P3"],
            default="P3",
        )
        out["risk_level"] = np.select(
            [out["is_high_risk"], out["final_candidate_status"].eq("manual_review"), out["is_observation"], out["is_one_shot"]],
            ["orange", "yellow", "observation", "attention"],
            default="insufficient",
        )
        out["risk_color"] = np.select(
            [out["risk_level"].eq("orange"), out["risk_level"].eq("yellow"), out["risk_level"].eq("observation")],
            ["orange", "yellow", "gray"],
            default="gray",
        )
        out["probability_display_mode"] = np.where(out["is_one_shot"] | out["is_observation"], "hide_probability", "show_risk_band")
        out["evidence_strength"] = np.select(
            [out["detector_hit_count"] >= 2, out["detector_hit_count"] == 1],
            ["medium", "weak"],
            default="insufficient",
        )
        out["auto_dispatch_allowed"] = False
        out["customer_facing_probability_service_allowed"] = False
        return out.reset_index(drop=True)
