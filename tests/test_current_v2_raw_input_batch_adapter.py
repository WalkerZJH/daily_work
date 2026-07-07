from __future__ import annotations

import json

import pandas as pd

from tests.formal_raw_to_batch_test_utils import require_raw_batch


def test_current_v2_raw_input_batch_has_required_orders_contract() -> None:
    raw_batch = require_raw_batch()
    manifest = json.loads((raw_batch / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["raw_batch_id"] == "current_v2_raw_input_batch"
    assert manifest["compatible_with_v2_exploration"] is True

    orders = pd.read_parquet(raw_batch / "orders.parquet")
    required = {"order_date", "manufacturer_code", "hospital_code", "drug_code", "order_quantity", "order_amount"}
    assert required.issubset(orders.columns)
    assert len(orders) > 0
