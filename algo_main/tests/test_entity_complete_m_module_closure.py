from __future__ import annotations

from alg.tasks.die_prediction import entity_complete_m_module_closure as closure

from entity_complete_m_module_fixtures import sample_candidates, sample_gate


def test_m_module_closure_module_imports() -> None:
    assert closure.VERSION == "entity_complete_v2_coverage_expansion"
    assert "run_entity_complete_m_module_closure" in closure.__all__


def test_m1_three_candidate_tables_exist_from_builder() -> None:
    candidates = sample_candidates()
    m1 = closure.build_m1_closure(candidates, sample_gate(candidates))

    assert len(m1["recurring_by_horizon"]) == 1
    assert len(m1["one_shot"]) == 1
    assert len(m1["observation"]) == 2
    assert len(m1["worklist"]) == 4
