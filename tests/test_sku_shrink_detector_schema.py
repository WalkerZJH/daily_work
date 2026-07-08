from __future__ import annotations

from tests.test_daily_detector_contract_utils import build_detector_fixture

from risk_algorithm_core.daily_detector_runner import build_daily_detector_tables


def test_sku_shrink_detector_schema() -> None:
    tables = build_daily_detector_tables(**build_detector_fixture())
    catalog = tables["detector_catalog"].set_index("detector_id")
    clues = tables["daily_detector_clues"]

    assert catalog.loc["sku_shrink", "status"] in {"interface_only", "missing_fields"}
    assert bool(catalog.loc["sku_shrink", "enabled_by_default"]) is False
    assert not clues["detector_id"].eq("sku_shrink").any()
    assert "竞品替代已确认" not in clues.to_csv(index=False)
