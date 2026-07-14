from __future__ import annotations

from risk_algorithm_core.detector_catalog import build_detector_capability_matrix


def test_detector_capability_matrix_matches_design() -> None:
    matrix = build_detector_capability_matrix()
    by_id = matrix.set_index("detector_id")

    assert by_id.loc["purchase_interval_ipi", "status"] == "implemented"
    assert by_id.loc["purchase_quantity_trend", "status"] == "implemented"
    assert by_id.loc["purchase_frequency_drop", "status"] == "implemented"
    assert by_id.loc["sku_shrink", "status"] == "blocked_by_missing_domain_concept"
    assert by_id.loc["fulfillment_gap", "status"] == "blocked_by_data"
    assert by_id.loc["price_competition", "status"] == "not_implemented"
    assert by_id.loc["peer_contrast", "status"] == "reserved"

    assert bool(by_id.loc["purchase_interval_ipi", "can_enter_v1_daily_detector"])
    assert not bool(by_id.loc["price_competition", "can_enter_v1_daily_detector"])
    assert by_id.loc["sku_shrink", "missing_fields"] == "product_line_domain_concept"
