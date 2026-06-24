from __future__ import annotations

from app.detectors.registry import DETECTOR_CATEGORIES, DETECTOR_META


def test_all_detectors_have_allowed_category() -> None:
    allowed = set(DETECTOR_CATEGORIES)

    assert DETECTOR_META
    assert all(meta.category in allowed for meta in DETECTOR_META.values())


def test_business_categories_are_represented_in_catalog() -> None:
    categories = {meta.category for meta in DETECTOR_META.values()}

    assert {
        "price_warning",
        "delivery_response",
        "terminal_change",
        "sales_fluctuation",
    }.issubset(categories)

