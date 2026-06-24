from __future__ import annotations

from datetime import date

import pandas as pd

from app.core.config import load_config
from app.services.training_dataset_service import TrainingDatasetService


def test_training_dataset_service_builds_labels_and_drops_incomplete_future_window() -> None:
    orders = pd.DataFrame(
        [
            _row("ORG_A", "2026-01-01"),
            _row("ORG_A", "2026-01-20"),
            _row("ORG_B", "2026-01-01"),
            _row("ORG_C", "2026-04-01"),
        ]
    )

    dataset = TrainingDatasetService(load_config()).build_from_orders(
        orders,
        train_start=date(2026, 1, 1),
        train_end=date(2026, 4, 1),
        horizon_days=45,
        freq="M",
    )

    assert not dataset.empty
    assert set(dataset["label_churn_H"]) == {0, 1}
    assert pd.to_datetime(dataset["origin_date"]).max().date() <= date(2026, 2, 15)


def _row(org_code: str, order_time: str) -> dict:
    return {
        "order_id": f"{org_code}-{order_time}",
        "org_code": org_code,
        "product_line_code": "PL_A",
        "drug_code": "D1",
        "order_time": order_time,
        "purchase_qty": 1,
        "purchase_amount": 10,
        "purchase_price": 10,
        "void_qty": 0,
    }
