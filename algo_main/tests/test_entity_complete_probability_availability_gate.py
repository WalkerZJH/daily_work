from __future__ import annotations

import pandas as pd

from alg.tasks.die_prediction.entity_complete_probability_availability_gate import (
    build_probability_availability_gate,
    render_service_gate_decision,
)


def _candidate_rows() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "manufacturer_code": ["m1", "m1", "m2"],
            "hospital_code": ["h1", "h2", "h3"],
            "drug_group": ["d1", "d2", "d3"],
            "drug_group_source": ["drug_code", "drug_code", "drug_code"],
            "cutoff_month": ["2025-01", "2025-01", "2025-01"],
            "horizon": ["H3", "H3", "H3"],
            "probability_score": [0.8, 0.6, 0.4],
            "history_sufficiency_flag": ["history_sufficient", "history_sufficient", "history_insufficient"],
            "demand_shape_label": ["smooth", "smooth", "lumpy"],
            "one_shot_flag": [False, True, False],
            "manufacturer_substitution_context_available": [True, False, False],
        }
    )


def test_probability_gate_hides_one_shot_recurring_probability() -> None:
    gate = build_probability_availability_gate(_candidate_rows())
    one_shot = gate[gate["hospital_code"].eq("h2")].iloc[0]

    assert one_shot["probability_display_level"] == "hidden_data_insufficient"
    assert one_shot["display_mode"] == "hide_probability"
    assert "one_shot_not_recurring_churn" in one_shot["reason_code"]


def test_probability_gate_auto_dispatch_false_and_caveats_present() -> None:
    gate = build_probability_availability_gate(_candidate_rows())

    assert gate["auto_dispatch_allowed"].eq(False).all()
    assert gate["selected_subset_caveat"].eq(True).all()
    assert gate["choice_set_caveat"].any()


def test_probability_gate_allows_only_stable_recurring_probability() -> None:
    gate = build_probability_availability_gate(_candidate_rows())
    stable = gate[gate["hospital_code"].eq("h1")].iloc[0]
    insufficient = gate[gate["hospital_code"].eq("h3")].iloc[0]

    assert stable["probability_display_allowed"] is True or bool(stable["probability_display_allowed"])
    assert insufficient["probability_display_level"] == "hidden_data_insufficient"


def test_service_gate_decision_blocks_customer_facing_service() -> None:
    gate = build_probability_availability_gate(_candidate_rows())
    text = render_service_gate_decision(gate)

    assert "customer_facing_probability_service: false" in text
    assert "auto_dispatch: false" in text
