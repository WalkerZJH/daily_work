from __future__ import annotations

from alg.tasks.die_prediction.mvc_model_package.business_copy_renderer import BusinessCopyRenderer, contains_forbidden_claims


def test_detector_copy_does_not_use_probability_or_root_cause_claims() -> None:
    renderer = BusinessCopyRenderer()
    names = [
        "terminal_loss_warning",
        "purchase_interval_overdue_warning",
        "purchase_frequency_fluctuation_warning",
        "purchase_quantity_fluctuation_warning",
        "new_terminal_detection",
        "low_delivery_rate_warning",
    ]

    for name in names:
        payload = renderer.render_detector_evidence(name, gate_status="weak_enabled_review_required" if name == "low_delivery_rate_warning" else "enabled")
        text = str(payload)
        assert "概率" not in payload["evidence_text"]
        assert "配送商责任明确" not in text
        assert "配送商导致流失" not in text
        assert not contains_forbidden_claims(text)


def test_disabled_price_and_delivery_copy_is_safe() -> None:
    renderer = BusinessCopyRenderer()
    for name in ["low_price_purchase_warning", "order_price_spread_warning", "delayed_response_warning"]:
        payload = renderer.render_detector_evidence(name, gate_status="disabled")
        text = str(payload)
        assert "未启用" in text
        assert "已确认" not in text
        assert not contains_forbidden_claims(text)

