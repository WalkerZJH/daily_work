from __future__ import annotations

from app.services.detector_narrative_service import DetectorNarrativeService


def test_implemented_detector_returns_chinese_narrative() -> None:
    narrative = DetectorNarrativeService().build(
        detector_id="low_delivery_rate_warning",
        hit=True,
        reason_code="DELIVERY_RATE_BELOW_THRESHOLD",
        metrics={"delivery_rate": 0.62, "threshold": 0.8},
        warnings=[],
    )

    assert "配送率" in narrative
    assert "建议" in narrative


def test_missing_fields_narrative_explains_insufficient_evidence() -> None:
    narrative = DetectorNarrativeService().build(
        detector_id="low_delivery_rate_warning",
        hit=False,
        reason_code="MISSING_REQUIRED_FIELDS",
        metrics={"missing_fields": ["delivery_qty"]},
        warnings=["缺少字段：delivery_qty"],
    )

    assert "当前证据不足" in narrative
    assert "delivery_qty" in narrative

