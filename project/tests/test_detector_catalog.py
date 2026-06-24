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
