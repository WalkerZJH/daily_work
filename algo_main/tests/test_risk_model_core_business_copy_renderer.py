from __future__ import annotations

import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def test_business_copy_renderer_handles_candidate_types_safely() -> None:
    from risk_model_core.business_copy_renderer import BusinessCopyRenderer, FORBIDDEN_CLAIMS

    renderer = BusinessCopyRenderer()

    outputs = [
        renderer.render_entity_summary({"is_one_shot": True}),
        renderer.render_entity_summary({"is_observation": True}),
        renderer.render_entity_summary({}),
        renderer.render_card_summary({"card_title": "Monthly risk review"}),
        renderer.render_suggested_action({}, {}, []),
    ]

    for text in outputs:
        assert text
        for claim in FORBIDDEN_CLAIMS:
            assert claim not in text


def test_business_copy_renderer_rejects_forbidden_claims() -> None:
    from risk_model_core.business_copy_renderer import validate_no_forbidden_claims

    with pytest.raises(ValueError):
        validate_no_forbidden_claims("\u533b\u9662\u5df2\u7ecf\u786e\u5b9a\u6d41\u5931")


def test_one_shot_and_observation_copy_semantics() -> None:
    from risk_model_core.business_copy_renderer import BusinessCopyRenderer

    renderer = BusinessCopyRenderer()

    one_shot_text = renderer.render_entity_summary({"is_one_shot": True})
    observation_text = renderer.render_entity_summary({"is_observation": True})

    assert "recurring churn" in one_shot_text
    assert "do not treat it as high risk" in observation_text
