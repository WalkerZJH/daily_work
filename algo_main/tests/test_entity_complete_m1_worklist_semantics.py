from __future__ import annotations

from alg.tasks.die_prediction import entity_complete_m_module_closure as closure

from entity_complete_m_module_fixtures import sample_candidates, sample_gate


def test_demand_shape_observation_is_not_high_risk() -> None:
    candidates = sample_candidates()
    m1 = closure.build_m1_closure(candidates, sample_gate(candidates))

    observation = m1["observation"]
    assert not observation.empty
    assert observation["is_high_risk"].eq(False).all()
    assert observation["display_section"].eq("demand_shape_observation").all()


def test_manufacturer_worklist_observation_fill_not_high_risk() -> None:
    candidates = sample_candidates()
    m1 = closure.build_m1_closure(candidates, sample_gate(candidates))

    fill = m1["worklist"][m1["worklist"]["candidate_type"].ne("recurring")]
    assert not fill.empty
    assert fill["is_high_risk"].eq(False).all()
    assert fill["selection_reason"].astype(str).str.contains("manufacturer_worklist_fill_observation").all()
