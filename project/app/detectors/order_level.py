from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

import pandas as pd

from app.schemas.algorithm import DetectorEvidence


def run_order_level_detectors(
    orders: pd.DataFrame,
    *,
    as_of_date: date,
    enabled_detectors: list[str],
    recent_days: int,
    low_price_config: dict[str, Any] | None = None,
    spread_ratio_threshold: float = 1.8,
    low_delivery_rate_threshold: float = 0.8,
) -> dict[str, list[DetectorEvidence]]:
    grouped: dict[str, list[DetectorEvidence]] = {}
    if orders.empty:
        return grouped
    scoped = orders.copy()
    scoped["order_time"] = pd.to_datetime(scoped["order_time"], errors="coerce")
    scoped = scoped[scoped["order_time"].notna()]
    scoped = scoped[scoped["order_time"].dt.date <= as_of_date]
    recent_start = pd.Timestamp(as_of_date) - pd.Timedelta(days=recent_days)
    recent = scoped[scoped["order_time"] >= recent_start]

    def add(org_code: str, product_line_code: str, evidence: DetectorEvidence) -> None:
        grouped.setdefault(f"{org_code}|product_line|{product_line_code}", []).append(evidence)

    if "low_price" in enabled_detectors:
        for evidence in _low_price(recent, low_price_config or {}):
            add(
                str(evidence.related_entities.get("org_code", "")),
                str(evidence.related_entities.get("product_line_code", "")),
                evidence,
            )

    if "price_spread" in enabled_detectors:
        for evidence in _price_spread(recent, spread_ratio_threshold):
            add(
                str(evidence.related_entities.get("org_code", "")),
                str(evidence.related_entities.get("product_line_code", "")),
                evidence,
            )

    if "delivery_refusal" in enabled_detectors:
        for evidence in _delivery_refusal(recent):
            add(
                str(evidence.related_entities.get("org_code", "")),
                str(evidence.related_entities.get("product_line_code", "")),
                evidence,
            )

    if "low_delivery_rate" in enabled_detectors:
        for evidence in _low_delivery_rate(recent, low_delivery_rate_threshold):
            add(
                str(evidence.related_entities.get("org_code", "")),
                str(evidence.related_entities.get("product_line_code", "")),
                evidence,
            )

    return grouped


def _low_price(orders: pd.DataFrame, config: dict[str, Any]) -> list[DetectorEvidence]:
    warning_price = config.get("warning_price")
    overrides: dict[str, Any] = config.get("overrides") or {}
    output: list[DetectorEvidence] = []
    if warning_price is None and not overrides:
        return [
            DetectorEvidence(
                detector_id="low_price",
                category="price_warning",
                family="price_threshold",
                hit=False,
                severity=0,
                confidence=0,
                reason_code="LOW_PRICE_THRESHOLD_NOT_CONFIGURED",
                warnings=["LOW_PRICE_THRESHOLD_NOT_CONFIGURED"],
            )
        ]
    for _, row in orders.iterrows():
        product_line_code = str(row.get("product_line_code") or "")
        drug_code = str(row.get("drug_code") or "")
        threshold = overrides.get(product_line_code, overrides.get(drug_code, warning_price))
        price = _float(row.get("comparable_unit_price"))
        if threshold is None or price is None or price >= float(threshold):
            continue
        severity = min(100.0, (float(threshold) - price) / max(float(threshold), 0.01) * 100)
        output.append(
            DetectorEvidence(
                detector_id="low_price",
                category="price_warning",
                family="price_threshold",
                hit=True,
                severity=max(35.0, severity),
                confidence=0.85,
                reason_code="LOW_PRICE_BELOW_WARNING_PRICE",
                evidence_items=[
                    {
                        "order_id": str(row.get("order_id")),
                        "comparable_unit_price": price,
                        "warning_price": float(threshold),
                    }
                ],
                related_entities=_related_entities(row),
                sample_order_ids=[str(row.get("order_id"))],
                statistics={"comparable_unit_price": price, "warning_price": float(threshold)},
            )
        )
    return output


def _price_spread(orders: pd.DataFrame, threshold: float) -> list[DetectorEvidence]:
    output: list[DetectorEvidence] = []
    if orders.empty:
        return output
    group_cols = ["org_code", "product_line_code"]
    for (org_code, product_line_code), group in orders.groupby(group_cols, dropna=True):
        prices = pd.to_numeric(group["comparable_unit_price"], errors="coerce").dropna()
        if prices.empty:
            continue
        min_price = float(prices.min())
        max_price = float(prices.max())
        if min_price <= 0:
            output.append(
                DetectorEvidence(
                    detector_id="price_spread",
                    category="price_warning",
                    family="price_spread",
                    hit=False,
                    severity=0,
                    confidence=0,
                    reason_code="PRICE_SPREAD_MIN_PRICE_NOT_POSITIVE",
                    related_entities={
                        "org_code": str(org_code),
                        "product_line_code": str(product_line_code),
                    },
                    warnings=["PRICE_SPREAD_MIN_PRICE_NOT_POSITIVE"],
                )
            )
            continue
        spread_ratio = max_price / min_price
        if spread_ratio < threshold:
            continue
        samples = group.sort_values("comparable_unit_price")["order_id"].astype(str).head(5).tolist()
        output.append(
            DetectorEvidence(
                detector_id="price_spread",
                category="price_warning",
                family="price_spread",
                hit=True,
                severity=min(100.0, max(45.0, (spread_ratio / threshold - 1) * 80 + 45)),
                confidence=0.8,
                reason_code="PRICE_SPREAD_RATIO_EXCEEDED",
                evidence_items=[
                    {
                        "max_price": max_price,
                        "min_price": min_price,
                        "spread_ratio": spread_ratio,
                        "sample_order_ids": samples,
                    }
                ],
                related_entities=_related_entities(group.iloc[0]),
                sample_order_ids=samples,
                statistics={
                    "max_price": max_price,
                    "min_price": min_price,
                    "spread_ratio": spread_ratio,
                    "spread_ratio_threshold": threshold,
                },
            )
        )
    return output


def _delivery_refusal(orders: pd.DataFrame) -> list[DetectorEvidence]:
    if "order_status" not in orders.columns:
        return []
    pattern = "拒绝|退货|无法配送|缺货|驳回"
    hit_orders = orders[orders["order_status"].fillna("").astype(str).str.contains(pattern, regex=True)]
    output: list[DetectorEvidence] = []
    for (org_code, product_line_code), group in hit_orders.groupby(["org_code", "product_line_code"]):
        statuses = Counter(group["order_status"].fillna("").astype(str))
        samples = group["order_id"].astype(str).head(10).tolist()
        output.append(
            DetectorEvidence(
                detector_id="delivery_refusal",
                category="delivery_response",
                family="delivery_status",
                hit=True,
                severity=80,
                confidence=0.75,
                reason_code="DELIVERY_STATUS_REFUSAL_KEYWORD",
                evidence_items=[{"matched_statuses": dict(statuses), "sample_order_ids": samples}],
                related_entities=_related_entities(group.iloc[0]),
                sample_order_ids=samples,
                statistics={"matched_order_count": int(len(group)), "matched_statuses": dict(statuses)},
            )
        )
    return output


def _low_delivery_rate(orders: pd.DataFrame, threshold: float) -> list[DetectorEvidence]:
    output: list[DetectorEvidence] = []
    if "delivery_qty" not in orders.columns or "purchase_qty" not in orders.columns:
        return output
    for (org_code, product_line_code), group in orders.groupby(["org_code", "product_line_code"]):
        purchase_qty = pd.to_numeric(group["purchase_qty"], errors="coerce").sum()
        delivery_qty = pd.to_numeric(group["delivery_qty"], errors="coerce").sum()
        if purchase_qty <= 0:
            continue
        delivery_rate = float(delivery_qty / purchase_qty)
        if delivery_rate >= threshold:
            continue
        output.append(
            DetectorEvidence(
                detector_id="low_delivery_rate",
                category="delivery_response",
                family="delivery_fulfillment",
                hit=True,
                severity=min(100.0, max(35.0, (threshold - delivery_rate) / threshold * 100)),
                confidence=0.7,
                reason_code="DELIVERY_RATE_BELOW_THRESHOLD",
                evidence_items=[
                    {
                        "purchase_qty": float(purchase_qty),
                        "delivery_qty": float(delivery_qty),
                        "delivery_rate": delivery_rate,
                    }
                ],
                related_entities=_related_entities(group.iloc[0]),
                sample_order_ids=group["order_id"].astype(str).head(10).tolist(),
                statistics={"delivery_rate": delivery_rate, "threshold": threshold},
            )
        )
    return output


def _related_entities(row: pd.Series) -> dict[str, Any]:
    keys = [
        "org_code",
        "org_name",
        "product_line_code",
        "product_line_name",
        "drug_code",
        "province",
        "city",
        "county",
        "distributor_code",
        "distributor_name",
        "manufacturer_code",
        "manufacturer_name",
    ]
    return {key: row.get(key) for key in keys if pd.notna(row.get(key))}


def _float(value: Any) -> float | None:
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
