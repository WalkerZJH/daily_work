from __future__ import annotations

from tests.formal_raw_to_batch_test_utils import REPORT_DIR, read_report_csv


def test_raw_source_inventory_finds_order_fact_or_reports_blocker() -> None:
    blocker = REPORT_DIR / "current_v2_raw_input_blocker.md"
    if blocker.exists():
        assert "No valid order fact/raw source" in blocker.read_text(encoding="utf-8")
        return

    inventory = read_report_csv("raw_source_inventory.csv")
    assert not inventory.empty
    raw_candidates = inventory[inventory["can_be_raw_orders"].astype(bool)]
    assert not raw_candidates.empty
    assert raw_candidates["path"].astype(str).str.contains("fact_purchase_event|combined_raw_orders|model_base").any()
