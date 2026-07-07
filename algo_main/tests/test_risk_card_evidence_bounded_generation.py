from __future__ import annotations

import pandas as pd

from alg.tasks.die_prediction.mvc_model_package.scope_config import FrontendScopeConfig
from alg.tasks.die_prediction.mvc_model_package.selectors import select_frontend_worklist_candidates
from alg.tasks.die_prediction.mvc_model_package.transformers import transform_m_closure_to_result_tables


def test_transformer_filters_to_selected_candidates_and_caps_evidence() -> None:
    ids = ["c1", "c2", "c3"]
    m5 = pd.DataFrame(
        {
            "candidate_id": ids,
            "candidate_type": ["recurring", "recurring", "recurring"],
            "manufacturer_code": ["m"] * 3,
            "hospital_code": ["h1", "h2", "h3"],
            "drug_group": ["d"] * 3,
            "drug_group_source": ["drug_code"] * 3,
            "cutoff_month": ["2025-12-31"] * 3,
            "horizon": ["H12"] * 3,
            "final_candidate_status": ["priority_review"] * 3,
            "review_priority": ["P0"] * 3,
            "evidence_strength": ["strong"] * 3,
            "human_review_required": [True] * 3,
            "auto_dispatch_allowed": [False] * 3,
            "survival_state": ["materially_overdue"] * 3,
            "detector_hit_count": [5] * 3,
            "strong_detector_hit_count": [1] * 3,
        }
    )
    m1 = pd.DataFrame(
        {
            "candidate_id": ids,
            "candidate_type": ["recurring"] * 3,
            "selection_reason": ["p"] * 3,
            "display_section": ["recurring"] * 3,
            "is_high_risk": [True] * 3,
            "user_visible_caveat": [""] * 3,
            "probability_score": [0.8, 0.7, 0.6],
            "churn_probability_H": [0.8, 0.7, 0.6],
            "demand_shape_label": ["smooth"] * 3,
            "history_sufficiency_flag": ["history_sufficient"] * 3,
            "probability_display_level": ["probability_allowed"] * 3,
            "display_mode": ["show_probability"] * 3,
        }
    )
    gate = pd.DataFrame(
        {
            "candidate_id": ids,
            "probability_display_allowed": [True] * 3,
            "model_confidence_bucket": ["high"] * 3,
            "choice_set_caveat": [True] * 3,
            "selected_subset_caveat": [True] * 3,
            "manual_review_required": [True] * 3,
        }
    )
    detector_rows = []
    for idx in range(8):
        detector_rows.append(
            {
                "candidate_id": "c1",
                "detector_family": "frequency",
                "detector_name": f"detector_{idx}",
                "hit_flag": True,
                "severity": "medium",
                "confidence": "evidence_hit",
                "evidence_fields": "x",
                "evidence_values": "{}",
                "reason_code": "r",
                "business_interpretation": "",
                "data_quality_status": "evaluable",
                "data_quality_note": "",
            }
        )
    inputs = {"m1": m1, "worklist": m1[m1["candidate_id"].isin(["c1", "c2"])], "m3": pd.DataFrame(), "m4": pd.DataFrame(detector_rows), "m5": m5, "gate": gate}
    selected = set(select_frontend_worklist_candidates(inputs)["candidate_id"])

    tables = transform_m_closure_to_result_tables(inputs, selected_candidate_ids=selected, max_cards_per_entity=5, max_business_visible_evidence_per_card=3)

    assert set(tables["risk_entities"]["candidate_id"]) == {"c1", "c2"}
    assert tables["risk_cards"].groupby("risk_entity_id").size().max() <= 5
    if not tables["risk_card_evidence"].empty:
        assert tables["risk_card_evidence"].groupby("risk_card_id").size().max() <= 3


def test_selector_caps_one_shot_and_observation_per_manufacturer() -> None:
    worklist = pd.DataFrame(
        {
            "candidate_id": [f"o{i}" for i in range(10)] + [f"w{i}" for i in range(10)] + ["r1"],
            "manufacturer_code": ["m"] * 21,
            "candidate_type": ["one_shot"] * 10 + ["demand_shape_observation"] * 10 + ["recurring"],
            "probability_score": list(range(10)) + list(range(10)) + [99],
        }
    )
    selected = select_frontend_worklist_candidates({"worklist": worklist}, FrontendScopeConfig(one_shot_topn_per_manufacturer=3, observation_topn_per_manufacturer=2))

    assert selected["candidate_type"].eq("one_shot").sum() == 3
    assert selected["candidate_type"].eq("demand_shape_observation").sum() == 2
    assert "r1" in set(selected["candidate_id"])

