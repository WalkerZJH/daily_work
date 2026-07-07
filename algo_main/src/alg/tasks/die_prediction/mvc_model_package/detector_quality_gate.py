"""Business readiness and data-quality gates for detector evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


DETECTOR_COLUMNS = [
    "detector_family",
    "detector_name",
    "business_requirement",
    "implementation_status",
    "rule_type",
    "required_fields",
    "available_fields",
    "missing_fields",
    "missing_rate_if_available",
    "data_quality_gate_status",
    "frontend_display_status",
    "enabled_for_frontend_worklist",
    "enabled_for_monthly_report",
    "enabled_for_dashboard",
    "enabled_for_distributor_page",
    "confidence_policy",
    "caveat",
    "forbidden_claims",
    "next_action",
]

GATE_COLUMNS = [
    "detector_name",
    "gate_status",
    "required_fields_available",
    "missing_rate_ok",
    "numeric_reliability_ok",
    "mapping_available",
    "semantic_caveat",
    "enable_frontend_display",
    "enable_customer_copy",
    "enable_internal_only",
    "reason_code",
]


@dataclass(frozen=True, slots=True)
class DetectorSpec:
    detector_family: str
    detector_name: str
    business_requirement: str
    implementation_status: str
    rule_type: str
    required_fields: tuple[str, ...]
    data_quality_gate_status: str
    frontend_display_status: str
    enabled_for_frontend_worklist: bool
    enabled_for_monthly_report: bool
    enabled_for_dashboard: bool
    enabled_for_distributor_page: bool
    confidence_policy: str
    caveat: str
    forbidden_claims: str
    next_action: str


DETECTOR_SPECS = [
    DetectorSpec("terminal", "terminal_loss_warning", "identify relationships needing priority review when recent purchases disappear", "enabled_rule_v1", "rule", ("months_since_last_purchase_asof_cutoff", "churn_probability_H"), "pass", "business_visible", True, True, True, False, "evidence_not_probability", "Only supports review prioritization; not a definitive churn conclusion.", "definitive churn claim", "show as priority review evidence"),
    DetectorSpec("interval", "purchase_interval_overdue_warning", "flag purchase rhythm materially overdue relative to own history", "enabled_rule_v1", "rule", ("months_since_last_purchase_asof_cutoff", "overdue_ratio", "expected_interval_months"), "pass", "business_visible", True, True, True, False, "evidence_not_probability", "Interval score is evidence/ranking support, not probability.", "definitive churn claim", "show as interval evidence"),
    DetectorSpec("frequency", "purchase_frequency_fluctuation_warning", "flag recent purchase frequency lower than historical baseline", "enabled_rule_v1", "rule", ("order_count_last_3m_asof_cutoff", "order_count_last_12m_asof_cutoff"), "pass", "business_visible", True, True, True, False, "evidence_not_probability", "Frequency drop needs business review for normal demand cycles.", "causal claim", "show as frequency evidence"),
    DetectorSpec("quantity", "purchase_quantity_fluctuation_warning", "flag recent purchase quantity decline if quantity fields are reliable", "weak_enabled_review_required", "rule", ("quantity_last_3m_asof_cutoff", "quantity_last_12m_asof_cutoff"), "weak_pass", "manager_visible", True, True, False, False, "weak_evidence_review_required", "Quantity is auxiliary evidence and needs manual review.", "causal claim", "show only when fields pass reliability guardrail"),
    DetectorSpec("new_terminal", "new_terminal_detection", "identify new terminal purchase fact", "enabled_rule_v1", "fact", ("first_purchase_time", "purchase_count_asof_cutoff"), "pass", "business_visible", True, True, False, False, "fact_not_churn_probability", "New terminal fact is separate from recurring churn.", "recurring churn claim", "show as one-shot/new terminal attention"),
    DetectorSpec("price", "low_price_purchase_warning", "evaluate low-price purchase signal", "interface_only", "interface", ("purchase_price", "comparable_price_group"), "blocked_semantics", "disabled", False, False, False, False, "not_enabled", "Price comparability is not validated.", "price caused churn", "keep interface only until comparable-price mapping exists"),
    DetectorSpec("price", "order_price_spread_warning", "evaluate order price spread signal", "interface_only", "interface", ("purchase_price", "comparable_price_group"), "blocked_semantics", "disabled", False, False, False, False, "not_enabled", "Price comparability is not validated.", "price caused churn", "keep interface only until comparable-price mapping exists"),
    DetectorSpec("response", "rejection_response_warning", "evaluate rejection/response behavior", "deferred_missing_data", "interface", ("response_status", "response_time"), "blocked_missing_data", "disabled", False, False, False, False, "not_enabled", "Response fields are not reliable enough for business claims.", "distributor responsibility", "defer until response fields are validated"),
    DetectorSpec("delivery", "delayed_response_warning", "evaluate delivery or arrival delay", "deferred_missing_data", "interface", ("delivery_time", "arrival_time"), "blocked_missing_data", "disabled", False, False, False, False, "not_enabled", "delivery_time / arrival_time missingness is too high for response-time analysis.", "distributor responsibility", "do not enable in current stage"),
    DetectorSpec("delivery", "low_delivery_rate_warning", "evaluate fulfillment quantity ratio as auxiliary observation", "weak_enabled_review_required", "rule", ("delivered_quantity", "ordered_quantity"), "weak_pass_default_disabled", "disabled", False, False, False, False, "weak_evidence_review_required", "Can only be auxiliary fulfillment observation; not distributor responsibility.", "distributor responsibility", "keep disabled by default until quantity/status reliability is approved"),
    DetectorSpec("amount", "purchase_amount_trend_warning", "evaluate purchase amount trend", "internal_only", "interface", ("purchase_amount",), "blocked_semantics", "internal_only", False, False, False, False, "internal_only", "Amount fields are desensitized/relative and should not support real value claims.", "amount caused churn", "keep internal only"),
    DetectorSpec("portfolio", "sku_narrowing_warning", "evaluate SKU or portfolio narrowing", "deferred_missing_mapping", "interface", ("product_line_code", "portfolio_mapping"), "blocked_mapping", "disabled", False, False, False, False, "not_enabled", "Portfolio/product-line mapping is not stable enough.", "competitor replacement", "defer until portfolio mapping exists"),
    DetectorSpec("portfolio", "wallet_share_decline_warning", "evaluate wallet-share decline", "deferred_missing_mapping", "interface", ("product_line_code", "portfolio_mapping", "manufacturer_choice_set"), "blocked_mapping", "disabled", False, False, False, False, "not_enabled", "Choice-set context is partial and cannot be interpreted as complete wallet share.", "market share or competitor replacement claim", "defer until product-line and full context mapping exists"),
]


def build_detector_business_readiness_matrix(
    available_fields: Iterable[str] | None = None,
    missing_rates: dict[str, float] | None = None,
) -> pd.DataFrame:
    available = set(available_fields or [])
    rates = missing_rates or {}
    rows = []
    for spec in DETECTOR_SPECS:
        required = list(spec.required_fields)
        present = [field for field in required if field in available]
        missing = [field for field in required if field not in available]
        rows.append(
            {
                "detector_family": spec.detector_family,
                "detector_name": spec.detector_name,
                "business_requirement": spec.business_requirement,
                "implementation_status": spec.implementation_status,
                "rule_type": spec.rule_type,
                "required_fields": "|".join(required),
                "available_fields": "|".join(present),
                "missing_fields": "|".join(missing),
                "missing_rate_if_available": "|".join(f"{field}:{rates.get(field, 'not_measured')}" for field in required),
                "data_quality_gate_status": spec.data_quality_gate_status,
                "frontend_display_status": spec.frontend_display_status,
                "enabled_for_frontend_worklist": spec.enabled_for_frontend_worklist,
                "enabled_for_monthly_report": spec.enabled_for_monthly_report,
                "enabled_for_dashboard": spec.enabled_for_dashboard,
                "enabled_for_distributor_page": spec.enabled_for_distributor_page,
                "confidence_policy": spec.confidence_policy,
                "caveat": spec.caveat,
                "forbidden_claims": spec.forbidden_claims,
                "next_action": spec.next_action,
            }
        )
    return pd.DataFrame(rows, columns=DETECTOR_COLUMNS)


def build_detector_quality_gate(readiness: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in readiness.iterrows():
        status = str(row["implementation_status"])
        enabled = bool(row["enabled_for_frontend_worklist"])
        internal_only = status == "internal_only"
        rows.append(
            {
                "detector_name": row["detector_name"],
                "gate_status": _gate_status(status),
                "required_fields_available": _fields_available(row),
                "missing_rate_ok": status not in {"deferred_missing_data"},
                "numeric_reliability_ok": status not in {"interface_only"} or "price" not in str(row["detector_family"]),
                "mapping_available": status != "deferred_missing_mapping",
                "semantic_caveat": row["caveat"],
                "enable_frontend_display": enabled,
                "enable_customer_copy": enabled and status in {"enabled_rule_v1", "weak_enabled_review_required"},
                "enable_internal_only": internal_only,
                "reason_code": row["data_quality_gate_status"],
            }
        )
    return pd.DataFrame(rows, columns=GATE_COLUMNS)


def _gate_status(status: str) -> str:
    if status == "enabled_rule_v1":
        return "enabled"
    if status == "weak_enabled_review_required":
        return "weak_enabled_review_required"
    if status == "internal_only":
        return "internal_only"
    return "disabled"


def _fields_available(row: pd.Series) -> bool:
    status = str(row["implementation_status"])
    if status in {"enabled_rule_v1", "weak_enabled_review_required", "internal_only"}:
        return True
    return False

