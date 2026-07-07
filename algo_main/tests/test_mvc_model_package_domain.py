from __future__ import annotations

from alg.tasks.die_prediction.mvc_model_package import DOMAIN_OBJECTS, RiskCard, RiskEntity, RiskEvidence
from alg.tasks.die_prediction.mvc_model_package.enums import RiskLevel
from alg.tasks.die_prediction.mvc_model_package.schemas import RISK_CARD_COLUMNS, RISK_ENTITY_COLUMNS, RISK_EVIDENCE_COLUMNS


def test_domain_objects_importable() -> None:
    assert len(DOMAIN_OBJECTS) == 9
    assert RiskEntity
    assert RiskCard
    assert RiskEvidence


def test_schema_constants_exist() -> None:
    assert "risk_entity_id" in RISK_ENTITY_COLUMNS
    assert "risk_card_id" in RISK_CARD_COLUMNS
    assert "evidence_text" in RISK_EVIDENCE_COLUMNS
    assert RiskLevel.RED.value == "red"
