from __future__ import annotations

import pandas as pd

from risk_algorithm_core.status_decider import StatusDecider


def test_status_decider_enforces_safety_flags() -> None:
    candidates = pd.DataFrame(
        [
            {"candidate_id": "c1", "candidate_type": "recurring", "churn_probability_H": 0.8, "risk_score": 0.8},
            {"candidate_id": "c2", "candidate_type": "one_shot", "churn_probability_H": 0.9, "risk_score": 0.9},
            {"candidate_id": "c3", "candidate_type": "observation", "churn_probability_H": 0.7, "risk_score": 0.7},
        ]
    )
    detectors = pd.DataFrame({"candidate_id": ["c1"], "hit_flag": [True], "severity": ["medium"]})
    status = StatusDecider().decide(candidates, pd.DataFrame(), detectors)
    by_id = status.set_index("candidate_id")
    assert by_id.loc["c1", "final_candidate_status"] == "priority_review"
    assert by_id.loc["c2", "final_candidate_status"] == "one_shot_attention"
    assert by_id.loc["c2", "probability_display_mode"] == "hide_probability"
    assert bool(by_id.loc["c3", "is_high_risk"]) is False
    assert status["auto_dispatch_allowed"].eq(False).all()
    assert status["customer_facing_probability_service_allowed"].eq(False).all()
