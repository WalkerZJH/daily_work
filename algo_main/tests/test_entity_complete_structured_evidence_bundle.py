from __future__ import annotations

from alg.tasks.die_prediction import entity_complete_m_module_closure as closure

from entity_complete_m_module_fixtures import sample_m_pipeline


def test_m7_forbidden_claims_contains_required_boundaries() -> None:
    m1, m3, m4, m5, gate = sample_m_pipeline()
    m7 = closure.build_m7_structured_evidence_bundle(m5, m3, m4, gate)

    text = " ".join(m7["forbidden_claims"].astype(str).head(1))
    for claim in closure.FORBIDDEN_CLAIMS:
        assert claim in text


def test_m7_bundle_keeps_timeline_and_llm_unimplemented() -> None:
    m1, m3, m4, m5, gate = sample_m_pipeline()
    m7 = closure.build_m7_structured_evidence_bundle(m5, m3, m4, gate)

    assert m7["auto_dispatch_allowed"].eq(False).all()
    assert m7["evidence_timeline_available"].eq(False).all()
    assert m7["evidence_persistence_summary"].eq("not_implemented_in_v1").all()
    assert m7["model_limitations_note"].astype(str).str.contains("no customer-facing probability service").all()


def test_m8_service_gate_blocks_customer_probability() -> None:
    m1, m3, m4, m5, gate = sample_m_pipeline()
    m7 = closure.build_m7_structured_evidence_bundle(m5, m3, m4, gate)
    m8 = closure.build_m8_validation_for_frames(m1, m3, m4, m5, m7)

    assert m8["service"]["internal_diagnostic_view"] is True
    assert m8["service"]["customer_facing_probability_service"] is False
    assert m8["service"]["auto_dispatch"] is False
