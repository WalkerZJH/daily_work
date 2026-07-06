from __future__ import annotations

from alg.tasks.die_prediction import entity_complete_m_module_closure as closure

from entity_complete_m_module_fixtures import sample_candidates, sample_features, sample_gate


def test_detector_evidence_has_no_probability_columns() -> None:
    candidates = sample_candidates()
    m1 = closure.build_m1_closure(candidates, sample_gate(candidates))
    m3 = closure.build_m3_survival_refinement(m1["recurring_by_horizon"], sample_features())
    m4 = closure.build_m4_detector_evidence(m1["all_by_horizon"], m3, sample_features())

    assert len(m4) == len(m1["all_by_horizon"]) * 3
    assert "probability" not in " ".join(m4.columns)
    assert m4["data_quality_note"].astype(str).str.contains("not probabilities").all()


def test_detector_evidence_keeps_label_for_audit_only() -> None:
    candidates = sample_candidates()
    m1 = closure.build_m1_closure(candidates, sample_gate(candidates))
    m3 = closure.build_m3_survival_refinement(m1["recurring_by_horizon"], sample_features())
    m4 = closure.build_m4_detector_evidence(m1["all_by_horizon"], m3, sample_features())

    assert "label_die_H" in m4.columns
    assert set(m4["detector_name"]) == {
        "terminal_loss_warning",
        "purchase_interval_overdue_warning",
        "purchase_frequency_fluctuation_warning",
    }
