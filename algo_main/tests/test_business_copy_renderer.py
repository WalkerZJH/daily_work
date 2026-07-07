from __future__ import annotations

import pytest

from alg.tasks.die_prediction.mvc_model_package.business_copy_renderer import BusinessCopyRenderer, contains_forbidden_claims


def test_renderer_does_not_emit_forbidden_claims() -> None:
    renderer = BusinessCopyRenderer()
    payload = renderer.render_for_row(
        {
            "candidate_type": "recurring",
            "final_candidate_status": "priority_review",
            "detector_hit_count": 2,
            "survival_state": "materially_overdue",
            "detector_evidence_list": "purchase_frequency_fluctuation_warning",
        }
    )
    text = str(payload)

    assert "医院已经确定流失" not in text
    assert "竞品替代" not in text
    assert "XGBoost" not in text
    assert not contains_forbidden_claims(text)


def test_renderer_marks_one_shot_as_attention_not_churn() -> None:
    renderer = BusinessCopyRenderer()
    payload = renderer.render_for_row({"candidate_type": "one_shot", "final_candidate_status": "one_shot_attention"})

    assert "新进终端关注" in payload["risk_card_title"]
    assert "recurring churn" in payload["caveat_text"]


def test_renderer_rejects_unsafe_payload() -> None:
    renderer = BusinessCopyRenderer()

    with pytest.raises(ValueError):
        renderer.assert_safe({"text": "XGBoost AUC 医院已经确定流失"})


def test_detector_renderer_uses_business_copy_and_disabled_notes() -> None:
    renderer = BusinessCopyRenderer()
    interval = renderer.render_detector_evidence("purchase_interval_overdue_warning")
    disabled = renderer.render_detector_evidence("delayed_response_warning", gate_status="disabled")

    assert "历史常规采购节奏" in interval["evidence_text"]
    assert "配送/到货时间字段缺失率较高" in disabled["evidence_text"]
    assert not contains_forbidden_claims(str(interval))
    assert not contains_forbidden_claims(str(disabled))

