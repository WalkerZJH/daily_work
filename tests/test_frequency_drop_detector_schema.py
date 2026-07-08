from __future__ import annotations

from tests.test_daily_detector_contract_utils import build_detector_fixture

from risk_algorithm_core.daily_detector_runner import DAILY_DETECTOR_CLUE_COLUMNS, build_daily_detector_tables


def test_frequency_drop_detector_schema() -> None:
    tables = build_daily_detector_tables(**build_detector_fixture())
    clues = tables["daily_detector_clues"]
    frequency = clues[clues["detector_id"].eq("purchase_frequency_drop")]

    assert list(clues.columns) == DAILY_DETECTOR_CLUE_COLUMNS
    assert not frequency.empty
    assert frequency["detector_family"].eq("frequency").all()
    assert frequency["root_cause_label"].eq("采购频次衰减").all()
