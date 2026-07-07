from __future__ import annotations

import pandas as pd

from alg.tasks.die_prediction.mvc_model_package.transformers import transform_m_closure_to_result_tables


def _inputs() -> dict[str, pd.DataFrame]:
    ids = ["c1", "c2", "c3"]
    m5 = pd.DataFrame(
        {
            "candidate_id": ids,
            "candidate_type": ["recurring", "one_shot", "demand_shape_observation"],
            "manufacturer_code": ["m", "m", "m"],
            "hospital_code": ["h1", "h2", "h3"],
            "drug_group": ["d1", "d2", "d3"],
            "drug_group_source": ["drug_code", "drug_code", "drug_code"],
            "cutoff_month": ["2025-12-31"] * 3,
            "horizon": ["H12"] * 3,
            "final_candidate_status": ["priority_review", "one_shot_attention", "observation_only"],
            "review_priority": ["P0", "P2", "P2"],
            "evidence_strength": ["strong", "weak", "weak"],
            "human_review_required": [True, True, True],
            "auto_dispatch_allowed": [False, False, False],
            "survival_state": ["materially_overdue", "", ""],
            "detector_hit_count": [1, 1, 0],
            "strong_detector_hit_count": [1, 0, 0],
        }
    )
    m1 = pd.DataFrame(
        {
            "candidate_id": ids,
            "candidate_type": ["recurring", "one_shot", "demand_shape_observation"],
            "selection_reason": ["p"] * 3,
            "display_section": ["recurring", "one_shot", "observation"],
            "is_high_risk": [True, False, False],
            "user_visible_caveat": ["", "", ""],
            "probability_score": [0.8, 0.7, 0.6],
            "churn_probability_H": [0.8, 0.7, 0.6],
            "demand_shape_label": ["smooth", "cold_start", "lumpy"],
            "history_sufficiency_flag": ["history_sufficient", "history_insufficient", "history_insufficient"],
            "probability_display_level": ["probability_allowed", "hidden_data_insufficient", "hidden_data_insufficient"],
            "display_mode": ["show_probability", "hide_probability", "hide_probability"],
        }
    )
    gate = pd.DataFrame(
        {
            "candidate_id": ids,
            "probability_display_allowed": [True, False, False],
            "model_confidence_bucket": ["high", "hidden", "hidden"],
            "choice_set_caveat": [True, True, True],
            "selected_subset_caveat": [True, True, True],
            "manual_review_required": [True, True, True],
        }
    )
    m4 = pd.DataFrame(
        {
            "candidate_id": ["c1", "c2"],
            "detector_family": ["interval", "frequency"],
            "detector_name": ["purchase_interval_overdue_warning", "purchase_frequency_fluctuation_warning"],
            "hit_flag": [True, True],
            "severity": ["strong", "medium"],
            "confidence": ["evidence_hit", "evidence_hit"],
            "evidence_fields": ["overdue_ratio", "frequency_decay"],
            "evidence_values": ["{}", "{}"],
            "reason_code": ["r1", "r2"],
            "business_interpretation": ["", ""],
            "data_quality_status": ["evaluable", "evaluable"],
            "data_quality_note": ["", ""],
        }
    )
    return {"m1": m1, "m3": pd.DataFrame(), "m4": m4, "m5": m5, "gate": gate}


def test_transformer_preserves_probability_boundaries() -> None:
    tables = transform_m_closure_to_result_tables(_inputs())
    entities = tables["risk_entities"]

    one_shot = entities[entities["candidate_id"].eq("c2")].iloc[0]
    observation = entities[entities["candidate_id"].eq("c3")].iloc[0]

    assert one_shot["palive_display"] == "不展示"
    assert one_shot["is_high_risk"] is False or not bool(one_shot["is_high_risk"])
    assert observation["is_high_risk"] is False or not bool(observation["is_high_risk"])
    assert entities["auto_dispatch_allowed"].eq(False).all()


def test_transformer_builds_cards_and_evidence() -> None:
    tables = transform_m_closure_to_result_tables(_inputs())

    assert len(tables["risk_cards"]) >= 3
    assert len(tables["risk_card_evidence"]) == 2
    assert tables["daily_reports"]["report_type"].eq("monthly").all()
