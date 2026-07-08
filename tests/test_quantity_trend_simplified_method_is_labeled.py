from __future__ import annotations

from tests.test_daily_detector_contract_utils import build_detector_fixture

from risk_algorithm_core.daily_detector_runner import build_daily_detector_tables


def test_quantity_trend_simplified_method_is_labeled() -> None:
    tables = build_daily_detector_tables(**build_detector_fixture())
    catalog = tables["detector_catalog"].set_index("detector_id")
    clues = tables["daily_detector_clues"]
    quantity = clues[clues["detector_id"].eq("purchase_quantity_trend")]

    assert catalog.loc["purchase_quantity_trend", "method"] == "simplified_ratio_v1"
    assert not quantity.empty
    assert quantity["evidence_payload"].astype(str).str.contains("simplified_ratio_v1").all()
