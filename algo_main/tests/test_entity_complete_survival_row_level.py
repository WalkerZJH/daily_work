from __future__ import annotations

from alg.tasks.die_prediction import entity_complete_m_module_closure as closure

from entity_complete_m_module_fixtures import sample_candidates, sample_features, sample_gate


def test_one_shot_does_not_enter_recurring_survival() -> None:
    candidates = sample_candidates()
    m1 = closure.build_m1_closure(candidates, sample_gate(candidates))
    m3 = closure.build_m3_survival_refinement(m1["recurring_by_horizon"], sample_features())

    assert len(m3) == len(m1["recurring_by_horizon"])
    assert set(m3["candidate_id"]).isdisjoint(set(m1["one_shot"]["candidate_id"]))


def test_survival_confidence_is_not_probability_value() -> None:
    candidates = sample_candidates()
    m1 = closure.build_m1_closure(candidates, sample_gate(candidates))
    m3 = closure.build_m3_survival_refinement(m1["recurring_by_horizon"], sample_features())

    assert "survival_confidence" in m3.columns
    assert m3["survival_confidence"].astype(str).str.contains("probability").eq(False).all()
    assert m3["survival_note"].astype(str).str.contains("not a calibrated probability").all()
