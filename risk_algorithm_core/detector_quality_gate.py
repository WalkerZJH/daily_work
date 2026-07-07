"""Runtime detector quality gates."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd


@dataclass(frozen=True, slots=True)
class DetectorGateDecision:
    detector_name: str
    gate_status: str
    required_fields_available: bool
    missing_rate_ok: bool
    numeric_reliability_ok: bool
    mapping_available: bool
    semantic_caveat: str
    enable_frontend_display: bool
    enable_customer_copy: bool
    enable_internal_only: bool
    reason_code: str


class DetectorQualityGate:
    def __init__(self, config: dict | None = None):
        self.config = config or {}

    def evaluate(self, features: pd.DataFrame, raw_tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
        decisions = [
            self._decision("terminal_loss_warning", "enabled_rule_v1", True, True, True, True, "", True, True, False, "enabled"),
            self._decision("purchase_interval_overdue_warning", "enabled_rule_v1", True, True, True, True, "", True, True, False, "enabled"),
            self._decision("purchase_frequency_fluctuation_warning", "enabled_rule_v1", True, True, True, True, "", True, True, False, "enabled"),
            self._quantity_decision(features),
            self._decision("new_terminal_detection", "enabled_rule_v1", True, True, True, True, "new_terminal_fact_not_recurring_churn", True, True, False, "enabled"),
            self._delivery_time_decision(raw_tables),
            self._decision("rejection_response_warning", "deferred_missing_data", False, False, False, False, "stable rejection response fields unavailable", False, False, True, "missing_rejection_mapping"),
            self._low_delivery_rate_decision(raw_tables),
            self._price_decision(raw_tables, "low_price_purchase_warning"),
            self._price_decision(raw_tables, "order_price_spread_warning"),
            self._decision("sku_narrowing_warning", "deferred_missing_mapping", False, False, False, False, "product line or portfolio mapping unavailable", False, False, True, "missing_portfolio_mapping"),
            self._decision("wallet_share_decline_warning", "deferred_missing_mapping", False, False, False, False, "complete platform share context unavailable", False, False, True, "missing_wallet_share_context"),
            self._decision("purchase_amount_trend_warning", "internal_only", True, True, False, True, "amount may be relative or de-identified", False, False, True, "amount_semantics_not_customer_safe"),
        ]
        return pd.DataFrame([asdict(d) for d in decisions])

    def _quantity_decision(self, features: pd.DataFrame) -> DetectorGateDecision:
        ok = "purchase_quantity_recent" in features and features["purchase_quantity_recent"].notna().mean() > 0.8
        status = "weak_enabled_review_required" if ok else "deferred_missing_data"
        return self._decision("purchase_quantity_fluctuation_warning", status, ok, ok, ok, True, "quantity evidence is auxiliary and review-required", ok, ok, not ok, "quantity_reliable" if ok else "quantity_missing")

    def _delivery_time_decision(self, raw_tables: dict[str, pd.DataFrame]) -> DetectorGateDecision:
        events = raw_tables.get("delivery_events", pd.DataFrame())
        available = not events.empty and {"delivery_date", "arrival_date"}.issubset(events.columns)
        missing_ok = bool(available and events[["delivery_date", "arrival_date"]].notna().mean().min() >= 0.5)
        return self._decision("delayed_response_warning", "enabled_rule_v1" if missing_ok else "deferred_missing_data", available, missing_ok, missing_ok, True, "delivery time evidence disabled when delivery or arrival time is missing", False, False, True, "delivery_time_missing")

    def _low_delivery_rate_decision(self, raw_tables: dict[str, pd.DataFrame]) -> DetectorGateDecision:
        enabled = bool(self.config.get("enable_low_delivery_rate_if_quality_passed", False))
        status = "weak_enabled_review_required" if enabled else "interface_only"
        return self._decision("low_delivery_rate_warning", status, enabled, enabled, enabled, True, "weak fulfillment-side evidence only; no distributor responsibility claim", enabled, enabled, not enabled, "weak_optional_detector")

    def _price_decision(self, raw_tables: dict[str, pd.DataFrame], name: str) -> DetectorGateDecision:
        price = raw_tables.get("price_reference", pd.DataFrame())
        ok = not price.empty and "reference_price" in price
        status = "weak_enabled_review_required" if ok and self.config.get("enable_price_detectors") else "interface_only"
        return self._decision(name, status, ok, ok, ok, ok, "price comparability is not validated for customer-facing claims", False, False, True, "price_reference_not_enabled")

    @staticmethod
    def _decision(
        detector_name: str,
        gate_status: str,
        required_fields_available: bool,
        missing_rate_ok: bool,
        numeric_reliability_ok: bool,
        mapping_available: bool,
        semantic_caveat: str,
        enable_frontend_display: bool,
        enable_customer_copy: bool,
        enable_internal_only: bool,
        reason_code: str,
    ) -> DetectorGateDecision:
        return DetectorGateDecision(
            detector_name,
            gate_status,
            required_fields_available,
            missing_rate_ok,
            numeric_reliability_ok,
            mapping_available,
            semantic_caveat,
            enable_frontend_display,
            enable_customer_copy,
            enable_internal_only,
            reason_code,
        )
