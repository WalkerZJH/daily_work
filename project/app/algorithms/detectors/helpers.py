from __future__ import annotations

from typing import Any

import pandas as pd

from app.schemas.algorithm import EvidenceRef


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def order_refs(orders: pd.DataFrame, limit: int = 5) -> list[EvidenceRef]:
    refs: list[EvidenceRef] = []
    if orders.empty or "order_id" not in orders.columns:
        return refs
    for _, row in orders.head(limit).iterrows():
        event_time = None
        if "order_time" in row and pd.notna(row["order_time"]):
            event_time = pd.Timestamp(row["order_time"]).to_pydatetime()
        fields: dict[str, Any] = {}
        for field in ["drug_code", "spec", "purchase_qty", "product_line_code"]:
            if field in row and pd.notna(row[field]):
                value = row[field]
                fields[field] = value.item() if hasattr(value, "item") else value
        order_id = str(row["order_id"])
        refs.append(
            EvidenceRef(
                ref_type="order",
                ref_id=order_id,
                order_id=order_id,
                event_time=event_time,
                fields=fields,
            )
        )
    return refs


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default
