from __future__ import annotations

from tests.test_daily_detector_contract_utils import build_detector_fixture

from risk_algorithm_core.daily_detector_runner import build_daily_detector_tables


def test_high_risk_detector_evidence_only_attaches_existing_risk_entities() -> None:
    fixture = build_detector_fixture(include_non_high_risk_scan=True)
    tables = build_daily_detector_tables(**fixture)
    evidence = tables["high_risk_detector_evidence"]
    entity_ids = set(fixture["risk_entities"]["risk_entity_id"].astype(str))

    assert not evidence.empty
    assert set(evidence["risk_entity_id"].astype(str)).issubset(entity_ids)
    assert evidence["risk_entity_id"].notna().all()
