from __future__ import annotations

from app.detectors.registry import DETECTOR_CATEGORIES, build_default_detector_registry


def test_detector_catalog_contains_business_categories_and_new_price_detectors() -> None:
    catalog = {meta.detector_id: meta for meta in build_default_detector_registry().catalog()}
    categories = {meta.category for meta in catalog.values()}

    assert {"price_warning", "delivery_response", "terminal_change", "sales_fluctuation"}.issubset(
        set(DETECTOR_CATEGORIES)
    )
    assert {"price_warning", "delivery_response", "terminal_change"}.issubset(categories)
    assert catalog["inactive_terminal"].category == "terminal_change"
    assert catalog["new_terminal"].category == "terminal_change"
    assert catalog["ip_interval"].category == "terminal_change"
    assert catalog["frequency_drop"].category == "terminal_change"
    assert "low_price" in catalog
    assert "price_spread" in catalog


def test_requirement_detectors_are_registered_with_metadata() -> None:
    catalog = {meta.detector_id: meta for meta in build_default_detector_registry().catalog()}
    required = {
        "low_price_warning",
        "price_spread_warning",
        "delivery_rejection_warning",
        "delivery_delay_warning",
        "low_delivery_rate_warning",
        "terminal_lost_warning",
        "new_terminal_warning",
        "purchase_quantity_fluctuation_warning",
        "purchase_frequency_fluctuation_warning",
    }

    assert required.issubset(catalog)
    for detector_id in required:
        meta = catalog[detector_id]
        assert meta.name_zh
        assert meta.category in DETECTOR_CATEGORIES
        assert meta.status
        assert meta.required_fields


def test_requirement_outside_internal_detectors_are_reserved_or_interface_only() -> None:
    catalog = {meta.detector_id: meta for meta in build_default_detector_registry().catalog()}

    assert catalog["substitution_risk"].status == "reserved"
    assert catalog["cycle_deviation"].status == "reserved"
    assert catalog["sku_shrink"].status == "reserved"
