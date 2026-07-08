from __future__ import annotations

from risk_algorithm_core.detector_catalog import build_detector_capability_matrix


def test_detector_capability_matrix_matches_design() -> None:
    matrix = build_detector_capability_matrix()
    by_id = matrix.set_index("detector_id")

    assert by_id.loc["purchase_interval_ipi", "status"] == "implemented"
    assert by_id.loc["purchase_quantity_trend", "status"] == "implemented"
    assert by_id.loc["purchase_frequency_drop", "status"] == "implemented"
    assert by_id.loc["sku_shrink", "status"] in {"interface_only", "missing_fields"}
    assert by_id.loc["fulfillment_gap", "status"] == "experimental"
    assert by_id.loc["price_competition", "status"] == "reserved"
    assert by_id.loc["peer_contrast", "status"] == "reserved"

    assert bool(by_id.loc["purchase_interval_ipi", "can_enter_v1_daily_detector"])
    assert not bool(by_id.loc["price_competition", "can_enter_v1_daily_detector"])
    assert "product_line" in by_id.loc["sku_shrink", "missing_fields"]
