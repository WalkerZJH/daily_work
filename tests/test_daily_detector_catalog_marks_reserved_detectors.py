from __future__ import annotations

from pathlib import Path

from risk_algorithm_core.detector_catalog import build_detector_catalog
from risk_algorithm_core.detector_config import load_daily_detector_config


def test_daily_detector_catalog_marks_reserved_detectors() -> None:
    config = load_daily_detector_config(Path("configs/risk_algorithm_core/daily_detector_rules.yaml"))
    catalog = build_detector_catalog(config)
    by_id = catalog.set_index("detector_id")

    assert by_id.loc["price_competition", "status"] == "not_implemented"
    assert by_id.loc["peer_contrast", "status"] == "reserved"
    assert by_id.loc["price_competition", "enabled_by_default"] is False
    assert by_id.loc["peer_contrast", "enabled_by_default"] is False
    assert by_id.loc["fulfillment_gap", "status"] == "blocked_by_data"
    assert by_id.loc["sku_shrink", "status"] == "blocked_by_missing_domain_concept"
    assert by_id.loc["purchase_quantity_trend", "method"] == "simplified_ratio_v1"
    assert by_id.loc["purchase_interval_ipi", "output_schema_version"] == "daily_detector_clue_v1"
