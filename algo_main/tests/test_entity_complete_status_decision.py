from __future__ import annotations

from alg.tasks.die_prediction import entity_complete_m_module_closure as closure

from entity_complete_m_module_fixtures import sample_m_pipeline


def test_m5_auto_dispatch_allowed_all_false() -> None:
    _, _, _, m5, _ = sample_m_pipeline()

    assert m5["auto_dispatch_allowed"].eq(False).all()
    assert m5["guardrail_status"].astype(str).str.contains("auto_dispatch_false").all()


def test_m5_one_shot_and_observation_statuses_are_separate() -> None:
    _, _, _, m5, _ = sample_m_pipeline()

    one_shot = m5[m5["candidate_type"].eq("one_shot")]
    observation = m5[m5["candidate_type"].eq("demand_shape_observation")]

    assert not one_shot.empty
    assert set(one_shot["final_candidate_status"]) == {"one_shot_attention"}
    assert not observation.empty
    assert set(observation["final_candidate_status"]).issubset({"observation_only", "not_actionable"})
