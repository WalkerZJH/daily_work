from __future__ import annotations

from tests.test_daily_detector_contract_utils import build_detector_fixture

from risk_algorithm_core.daily_detector_runner import build_daily_detector_tables


def test_daily_detector_clues_allow_non_high_risk_but_do_not_create_risk_entities() -> None:
    fixture = build_detector_fixture(include_non_high_risk_scan=True)
    tables = build_daily_detector_tables(**fixture)
    clues = tables["daily_detector_clues"]
    non_high = clues[~clues["is_monthly_high_risk_entity"]]

    assert not non_high.empty
    assert non_high["risk_entity_id"].isna().all()
    assert fixture["risk_entities"]["risk_entity_id"].nunique() == 1
    assert "entity_non_high" not in set(fixture["risk_entities"]["risk_entity_id"].astype(str))
