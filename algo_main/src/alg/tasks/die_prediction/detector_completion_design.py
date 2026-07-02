"""Detector completion feasibility and design audit.

This module is read-only. It compares the leadership detector design against
the current M4 detector outputs and report schemas, then writes a feasibility
package. It does not implement detectors or modify M4 outputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


OUTPUT_DIR = Path("reports/alive_prediction_detector_completion_design_v1")
INTERFACE_ONLY_DETECTORS = {
    "low_price_purchase_warning",
    "order_price_spread_warning",
    "rejection_response_warning",
    "delayed_response_warning",
    "low_delivery_rate_warning",
}
DELIVERY_DETECTORS = {
    "rejection_response_warning",
    "delayed_response_warning",
    "low_delivery_rate_warning",
}


FIELD_CANDIDATES = [
    "purchase_time",
    "order_count_last_1m_asof_cutoff",
    "order_count_last_3m_asof_cutoff",
    "order_count_last_6m_asof_cutoff",
    "order_count_last_12m_asof_cutoff",
    "frequency_decay_3m_vs_12m",
    "frequency_decay_6m_vs_12m",
    "purchase_quantity_sum_last_1m_asof_cutoff",
    "purchase_quantity_sum_last_3m_asof_cutoff",
    "purchase_quantity_sum_last_6m_asof_cutoff",
    "purchase_quantity_sum_last_12m_asof_cutoff",
    "purchase_amount_sum_last_3m_asof_cutoff",
    "purchase_amount_sum_last_6m_asof_cutoff",
    "purchase_amount_sum_last_12m_asof_cutoff",
    "median_purchase_interval_days_asof_cutoff",
    "purchase_interval_mad_days_asof_cutoff",
    "days_since_last_purchase_asof_cutoff",
    "months_since_last_purchase_asof_cutoff",
    "overdue_ratio",
    "demand_shape_label",
    "history_sufficiency_flag",
    "drug_code",
    "drug_group",
    "drug_category_code",
    "product_line_code",
    "specification",
    "dosage_form",
    "approval_number",
    "purchase_price",
    "purchase_amount",
    "purchase_quantity",
]


@dataclass
class DetectorSpec:
    detector_id: str
    detector_name: str
    leader_design_category: str
    required_fields: list[str]
    demand_shape_route_rule: str
    p_value_possible: str
    fdr_ready: str


DETECTOR_SPECS = [
    DetectorSpec(
        "D001",
        "purchase_interval_overdue_warning",
        "purchase_interval/IPI",
        [
            "median_purchase_interval_days_asof_cutoff",
            "purchase_interval_mad_days_asof_cutoff",
            "days_since_last_purchase_asof_cutoff",
            "months_since_last_purchase_asof_cutoff",
            "overdue_ratio",
            "demand_shape_label",
            "history_sufficiency_flag",
        ],
        "smooth/erratic can use interval evidence; intermittent/lumpy should prefer long horizon or observation.",
        "partial: robust z-test possible if MAD/current gap available; current reports expose overdue_ratio but not MAD.",
        "partial: can support FDR after p_value is added.",
    ),
    DetectorSpec(
        "D002",
        "purchase_frequency_decay_rate_test",
        "purchase_frequency_decay",
        [
            "order_count_last_3m_asof_cutoff",
            "order_count_last_6m_asof_cutoff",
            "order_count_last_12m_asof_cutoff",
            "frequency_decay_3m_vs_12m",
            "frequency_decay_6m_vs_12m",
            "demand_shape_label",
            "history_sufficiency_flag",
        ],
        "avoid strong short-window interpretation for intermittent/lumpy; use as supporting evidence.",
        "yes: Poisson or negative-binomial rate test can produce p_value if counts are available.",
        "yes after p_value and test family metadata are emitted.",
    ),
    DetectorSpec(
        "D003",
        "purchase_quantity_trend_warning",
        "quantity_trend_decay",
        [
            "purchase_quantity_sum_last_1m_asof_cutoff",
            "purchase_quantity_sum_last_3m_asof_cutoff",
            "purchase_quantity_sum_last_6m_asof_cutoff",
            "purchase_quantity_sum_last_12m_asof_cutoff",
            "purchase_quantity",
            "demand_shape_label",
            "history_sufficiency_flag",
        ],
        "trend tests should be disabled or downweighted for intermittent/lumpy demand.",
        "partial: MK/Theil-Sen/CUSUM need ordered window history, not only aggregate columns.",
        "partial only after reliable trend p_value is available.",
    ),
    DetectorSpec(
        "D004",
        "purchase_amount_trend_warning",
        "amount_trend_decay",
        [
            "purchase_amount_sum_last_3m_asof_cutoff",
            "purchase_amount_sum_last_6m_asof_cutoff",
            "purchase_amount_sum_last_12m_asof_cutoff",
            "purchase_amount",
            "demand_shape_label",
            "history_sufficiency_flag",
        ],
        "amount trend should remain weaker than quantity trend unless numeric comparability is confirmed.",
        "partial: possible only as relative trend if amount is monotonic and comparable.",
        "not ready until numeric reliability is confirmed.",
    ),
    DetectorSpec(
        "D005",
        "sku_narrowing_warning",
        "sku_narrowing/product_line",
        ["drug_code", "drug_group", "product_line_code", "specification", "dosage_form", "approval_number"],
        "not applicable at drug_code entity grain without product-line or portfolio grouping.",
        "partial after product-line mapping; count/proportion tests may produce p_value.",
        "not ready until grouping is designed.",
    ),
    DetectorSpec(
        "D006",
        "wallet_share_decline_warning",
        "wallet_share/product_line",
        ["drug_code", "drug_group", "drug_category_code", "product_line_code", "purchase_amount", "purchase_quantity"],
        "requires product-line or portfolio denominator; do not infer wallet share at single drug_code grain.",
        "partial after denominator and peer scope are defined.",
        "not ready until product-line mapping and denominator are reliable.",
    ),
    DetectorSpec(
        "D007",
        "low_price_purchase_warning",
        "price_warning",
        ["purchase_price", "specification", "dosage_form", "approval_number"],
        "price detector independent of demand shape, but should not influence probability.",
        "yes only if comparable unit price is reliable.",
        "not ready while interface-only.",
    ),
    DetectorSpec(
        "D008",
        "order_price_spread_warning",
        "price_warning",
        ["purchase_price", "specification", "dosage_form", "approval_number"],
        "price detector independent of demand shape, but should not influence probability.",
        "yes only if comparable unit price is reliable.",
        "not ready while interface-only.",
    ),
    DetectorSpec(
        "D009",
        "rejection_response_warning",
        "delivery_response",
        ["purchase_time"],
        "skipped by user decision in this stage.",
        "not evaluated in this stage.",
        "not ready; skipped.",
    ),
    DetectorSpec(
        "D010",
        "delayed_response_warning",
        "delivery_response",
        ["purchase_time"],
        "skipped by user decision in this stage.",
        "not evaluated in this stage.",
        "not ready; skipped.",
    ),
    DetectorSpec(
        "D011",
        "low_delivery_rate_warning",
        "delivery_response",
        ["purchase_quantity"],
        "skipped by user decision in this stage.",
        "not evaluated in this stage.",
        "not ready; skipped.",
    ),
    DetectorSpec(
        "D012",
        "terminal_loss_warning",
        "terminal_dynamic",
        ["overdue_ratio", "demand_shape_label", "history_sufficiency_flag"],
        "observation_only guardrail for low-confidence demand shapes.",
        "not required; it is interval state evidence rather than a statistical test.",
        "not applicable in current implementation.",
    ),
    DetectorSpec(
        "D013",
        "new_terminal_detection",
        "terminal_dynamic",
        ["purchase_time", "drug_group"],
        "one-shot/new terminal fact; not recurring churn.",
        "not required; factual detector.",
        "not applicable in current implementation.",
    ),
]


def load_csv_if_exists(path: Path, nrows: int | None = None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, nrows=nrows)


def read_text_if_exists(path: Path, max_chars: int | None = None) -> str:
    if not path.exists():
        return f"MISSING: {path.as_posix()}"
    text = path.read_text(encoding="utf-8", errors="replace")
    return text if max_chars is None else text[:max_chars]


def collect_report_schema(project_root: Path) -> dict[str, set[str]]:
    """Collect columns from current reports only, without reading parquet."""
    paths = {
        "detector_family_summary": project_root / "reports/alive_prediction_detectors_v1/detector_family_summary.csv",
        "detector_evidence_results": project_root / "reports/alive_prediction_detectors_v1/detector_evidence_results.csv",
        "survival_refinement_results": project_root / "reports/alive_prediction_survival_lite_v1/survival_refinement_results.csv",
        "candidate_pool_by_horizon": project_root
        / "reports/alive_prediction_candidate_pool_v1/recurring_business_priority_candidates_by_horizon.csv",
        "candidate_pool": project_root / "reports/alive_prediction_candidate_pool_v1/recurring_business_priority_candidates.csv",
    }
    schema: dict[str, set[str]] = {}
    for name, path in paths.items():
        df = load_csv_if_exists(path, nrows=1)
        schema[name] = set(df.columns)
    evidence_path = project_root / "reports/alive_prediction_detectors_v1/detector_evidence_results.csv"
    if evidence_path.exists():
        try:
            evidence_fields = pd.read_csv(evidence_path, usecols=["evidence_fields"])["evidence_fields"]
            parsed_fields: set[str] = set()
            for value in evidence_fields.dropna().astype(str):
                if value.lower() == "none":
                    continue
                parsed_fields.update(field.strip() for field in value.split(";") if field.strip())
            schema["detector_evidence_fields"] = parsed_fields
        except Exception:
            schema["detector_evidence_fields"] = set()
    return schema


def field_availability_rows(schema: dict[str, set[str]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for field in FIELD_CANDIDATES:
        present_in = [name for name, cols in schema.items() if field in cols]
        rows.append(
            {
                "field": field,
                "available": bool(present_in),
                "available_in_reports": ";".join(present_in),
                "availability_note": "available_in_current_reports" if present_in else "missing_from_current_reports",
            }
        )
    return pd.DataFrame(rows)


def _field_availability(required_fields: list[str], available: set[str]) -> str:
    present = [field for field in required_fields if field in available]
    if len(present) == len(required_fields):
        return "all_required_fields_available"
    if present:
        return "partial_fields_available:" + ",".join(present)
    return "missing_required_fields"


def _current_status(detector_name: str, family_summary: pd.DataFrame) -> str:
    if detector_name in DELIVERY_DETECTORS:
        return "skipped_by_user_decision"
    if family_summary.empty or "detector_name" not in family_summary.columns:
        if detector_name in INTERFACE_ONLY_DETECTORS:
            return "interface_only"
        return "not_implemented"
    rows = family_summary.loc[family_summary["detector_name"].astype(str) == detector_name]
    if rows.empty:
        return "not_implemented"
    return str(rows["detector_status"].iloc[0]) if "detector_status" in rows.columns else "implemented"


def _data_reliability(detector_name: str, required_fields: list[str], available: set[str]) -> str:
    if detector_name in DELIVERY_DETECTORS:
        return "not_assessed_user_skipped_delivery"
    if "price" in detector_name:
        return "unreliable_or_unconfirmed_comparable_price"
    if "amount" in detector_name:
        return "numeric_sensitive_amount_relative_only"
    if "quantity" in detector_name:
        return "relative_quantity_trend_with_caveat"
    if detector_name in {"sku_narrowing_warning", "wallet_share_decline_warning"}:
        return "requires_product_line_or_portfolio_mapping"
    if "purchase_interval" in detector_name:
        if "overdue_ratio" in available:
            return "m3_interval_fields_available_mad_missing"
        return "interval_fields_incomplete"
    return "usable_as_current_evidence"


def _entity_grain_feasibility(detector_name: str, available: set[str], primary_grain: str = "drug_code") -> str:
    if detector_name in {"sku_narrowing_warning", "wallet_share_decline_warning"}:
        if primary_grain == "drug_code" and "product_line_code" not in available:
            return "requires_product_line_mapping"
        return "feasible_after_grouping_design"
    if detector_name in {"low_price_purchase_warning", "order_price_spread_warning"}:
        return "requires_comparable_unit_and_spec_mapping"
    return "feasible_at_current_entity_grain"


def _priority_and_action(detector_name: str, status: str, available: set[str]) -> tuple[str, str, str]:
    if detector_name in DELIVERY_DETECTORS:
        return "skip_current_stage", "skip_current_stage", "user explicitly decided not to supplement delivery detectors"
    if detector_name in {"terminal_loss_warning", "new_terminal_detection"}:
        return "current", "already_implemented", ""
    if detector_name == "purchase_interval_overdue_warning":
        if "overdue_ratio" in available and (
            "median_purchase_interval_days_asof_cutoff" in available or "expected_interval_months" in available
        ):
            return "implement_now", "implement_as_m4_evidence_using_m3_interval_fields", "MAD missing; p_value can be partial unless interval MAD is added"
        return "design_first", "add_or_expose_interval_fields_before_implementation", "missing interval as-of fields"
    if detector_name == "purchase_frequency_decay_rate_test":
        if {"order_count_last_3m_asof_cutoff", "order_count_last_12m_asof_cutoff"} & available or {
            "frequency_decay_3m_vs_12m",
            "frequency_decay_6m_vs_12m",
        } & available:
            return "implement_now", "enhance_existing_frequency_detector_with_rate_test", ""
        return "design_first", "expose order count windows first", "missing order count / decay fields"
    if detector_name == "purchase_quantity_trend_warning":
        return "design_first", "guarded_design_before_implementation", "quantity numeric reliability and trend history need confirmation"
    if detector_name == "purchase_amount_trend_warning":
        return "interface_only", "keep_relative_amount_trend_interface_only", "amount is sensitive/relative and should not imply real monetary trend"
    if detector_name in {"sku_narrowing_warning", "wallet_share_decline_warning"}:
        return "design_first", "requires_product_line_mapping", "current primary entity grain is drug_code; product line is missing"
    if detector_name in {"low_price_purchase_warning", "order_price_spread_warning"}:
        return "interface_only", "keep_interface_only_until_price_reliability_confirmed", "purchase_price comparability is unconfirmed"
    return "design_first", "review_required", "unclassified detector"


def build_detector_gap_matrix(project_root: Path, schema: dict[str, set[str]] | None = None) -> pd.DataFrame:
    schema = schema or collect_report_schema(project_root)
    available = set().union(*schema.values()) if schema else set()
    family_summary = load_csv_if_exists(project_root / "reports/alive_prediction_detectors_v1/detector_family_summary.csv")
    rows: list[dict[str, Any]] = []
    for spec in DETECTOR_SPECS:
        status = _current_status(spec.detector_name, family_summary)
        priority, action, blocking = _priority_and_action(spec.detector_name, status, available)
        rows.append(
            {
                "detector_id": spec.detector_id,
                "detector_name": spec.detector_name,
                "leader_design_category": spec.leader_design_category,
                "current_status": status,
                "required_fields": ";".join(spec.required_fields),
                "field_availability": _field_availability(spec.required_fields, available),
                "data_reliability": _data_reliability(spec.detector_name, spec.required_fields, available),
                "entity_grain_feasibility": _entity_grain_feasibility(spec.detector_name, available),
                "demand_shape_route_rule": spec.demand_shape_route_rule,
                "p_value_possible": spec.p_value_possible,
                "fdr_ready": spec.fdr_ready,
                "implementation_priority": priority,
                "recommended_action": action,
                "blocking_reason": blocking,
            }
        )
    return pd.DataFrame(rows)


def _list_by_priority(matrix: pd.DataFrame, priority: str) -> list[str]:
    if matrix.empty:
        return []
    return matrix.loc[matrix["implementation_priority"] == priority, "detector_name"].astype(str).tolist()


def build_summary_md(matrix: pd.DataFrame) -> str:
    implemented = matrix.loc[matrix["current_status"].astype(str) == "implemented", "detector_name"].tolist()
    if not implemented:
        implemented = [
            name
            for name in ["terminal_loss_warning", "purchase_frequency_fluctuation_warning", "purchase_quantity_fluctuation_warning", "new_terminal_detection"]
            if name in matrix["detector_name"].values
        ]
    implement_now = _list_by_priority(matrix, "implement_now")
    design_first = _list_by_priority(matrix, "design_first")
    interface_only = _list_by_priority(matrix, "interface_only")
    skipped = _list_by_priority(matrix, "skip_current_stage")
    p_value = matrix.loc[matrix["p_value_possible"].astype(str).str.contains("yes|partial", case=False), "detector_name"].tolist()
    fdr = matrix.loc[matrix["fdr_ready"].astype(str).str.contains("yes|partial", case=False), "detector_name"].tolist()
    missing = matrix.loc[matrix["current_status"].isin(["not_implemented", "skipped_by_user_decision"]), "detector_name"].tolist()
    return f"""# Detector Completion Summary

## Current M4 Implemented Detectors

- terminal_loss_warning
- purchase_frequency_fluctuation_warning
- purchase_quantity_fluctuation_warning
- new_terminal_detection

## Remaining Gaps Against Leadership Design

- purchase_interval_overdue_warning / IPI
- purchase_frequency_decay_rate_test enhancement
- purchase_quantity_trend_warning
- purchase_amount_trend_warning
- sku_narrowing_warning
- wallet_share_decline_warning
- price detectors remain interface-only
- delivery detectors are skipped by user decision

## Feasibility Buckets

- implement_now: {implement_now}
- design_first: {design_first}
- interface_only: {interface_only}
- skip_current_stage: {skipped}

## p-value / FDR Readiness

- Detectors that can potentially emit p-value: {p_value}
- Detectors that can support future FDR after p-value output: {fdr}

## Recommendation

Implement next only after design approval, and prioritize IPI plus frequency
rate-test enhancement. Quantity trend should be guarded by numeric reliability
checks. SKU narrowing and wallet share need product-line or portfolio mapping.
Price remains interface-only until comparable price is confirmed. Delivery
detectors should remain skipped in this stage per user decision.

## L2/L3

L2/L3 should remain deferred. This audit only prepares M4 completion design and
does not implement new detectors, FDR, deconfounding, or fusion upgrades.
"""


def build_numeric_usability_md(matrix: pd.DataFrame) -> str:
    return """# Detector Numeric Usability Audit

## Quantity

`purchase_quantity` and derived quantity windows can support relative trend or
fluctuation evidence only with caveats. Prior cleaning notes flagged sensitive
numeric fields as potentially independently desensitized. Because the current
project already uses quantity-like features for relative evidence, quantity
trend can be designed as `relative_quantity_trend_with_caveat`, not as a strong
real-unit business conclusion.

## Amount

Amount fields require stricter caution than quantity. If amount is desensitized
or not comparable, `purchase_amount_trend_warning` must stay interface-only or
relative-only. Amount must not be used to infer price.

## Price

`purchase_price` cannot be used for low-price or price-spread conclusions unless
comparable unit price, specification/unit mapping, and reliability are
confirmed. Price detectors remain interface-only in the current stage.

## Trend Tests

Mann-Kendall, Theil-Sen, and CUSUM require ordered window history, not only
aggregate 3m/6m/12m fields. They should be disabled or downweighted for
intermittent/lumpy demand shapes.
"""


def build_entity_grain_md(matrix: pd.DataFrame) -> str:
    sku = matrix.loc[matrix["detector_name"] == "sku_narrowing_warning"].iloc[0]
    wallet = matrix.loc[matrix["detector_name"] == "wallet_share_decline_warning"].iloc[0]
    return f"""# Detector Entity Grain Feasibility

Current stage uses `manufacturer_code x hospital_code x drug_code` semantics
through `drug_group_source = drug_code`. At this grain, an entity is already a
single drug code, so entity-internal active SKU count is not a valid SKU
narrowing detector.

## SKU Narrowing

- Feasibility: {sku['entity_grain_feasibility']}
- Required action: product-line / portfolio grouping is required before this can
  be a formal detector.
- A manufacturer x hospital x drug_category proxy may be explored, but it is not
  the formal SKU narrowing detector and must be labeled as a proxy.

## Wallet Share

- Feasibility: {wallet['entity_grain_feasibility']}
- Required action: define denominator across product line, category, or
  manufacturer portfolio before calculating share decline.
"""


def build_recommendation_md(matrix: pd.DataFrame) -> str:
    return f"""# Detector Completion Recommendation

## implement_now

{_markdown_list(_list_by_priority(matrix, "implement_now"))}

## design_first

{_markdown_list(_list_by_priority(matrix, "design_first"))}

## interface_only

{_markdown_list(_list_by_priority(matrix, "interface_only"))}

## skip_current_stage

{_markdown_list(_list_by_priority(matrix, "skip_current_stage"))}

## Recommendation

Next implementation should be limited to M4 evidence enhancements: IPI detector
and frequency rate-test enhancement. Quantity trend should be designed with
numeric caveats before implementation. SKU narrowing and wallet share require
product-line mapping. Price remains interface-only. Delivery remains skipped.
Do not enter L2/L3 in the next step.
"""


def build_next_prompt_md(matrix: pd.DataFrame) -> str:
    implement_now = _list_by_priority(matrix, "implement_now")
    return f"""# Next Implementation Prompt: M4 Detector Completion v2

Current audit supports implementing only the following detector enhancements:

{_markdown_list(implement_now)}

Task constraints for the next implementation:

1. Implement `purchase_interval_overdue_warning` as M4 evidence only. Reuse M3
   interval fields where available. Do not replace M3 survival-lite and do not
   change `churn_probability_H` or `relative_business_priority_score_H`.
2. Implement `purchase_frequency_decay_rate_test` as an enhancement to the
   existing frequency detector. Prefer Poisson or negative-binomial rate test if
   count windows are available. Emit `p_value` and leave FDR for a later stage.
3. Design `purchase_quantity_trend_warning` with numeric reliability guardrails.
   If quantity reliability is not confirmed, emit relative-trend evidence only
   and avoid strong causality.
4. Keep SKU narrowing / wallet share as design-first unless `product_line_code`
   or a validated portfolio mapping exists.
5. Keep price detectors interface-only unless comparable price reliability is
   confirmed.
6. Keep delivery detectors skipped in this stage by user decision.
7. Do not implement L2/L3, FDR, detector fusion, line cards, LLM, M6 cache, or
   auto dispatch.
"""


def _markdown_list(items: list[str]) -> str:
    if not items:
        return "- none"
    return "\n".join(f"- {item}" for item in items)


def write_detector_completion_audit(project_root: Path, output_dir: Path | None = None) -> dict[str, Any]:
    output = output_dir or project_root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)

    schema = collect_report_schema(project_root)
    fields = field_availability_rows(schema)
    matrix = build_detector_gap_matrix(project_root, schema)

    fields.to_csv(output / "detector_field_availability_audit.csv", index=False)
    matrix.to_csv(output / "detector_gap_matrix.csv", index=False)
    (output / "detector_completion_summary.md").write_text(build_summary_md(matrix), encoding="utf-8")
    (output / "detector_numeric_usability_audit.md").write_text(build_numeric_usability_md(matrix), encoding="utf-8")
    (output / "detector_entity_grain_feasibility.md").write_text(build_entity_grain_md(matrix), encoding="utf-8")
    (output / "detector_completion_recommendation.md").write_text(build_recommendation_md(matrix), encoding="utf-8")
    (output / "detector_next_implementation_prompt.md").write_text(build_next_prompt_md(matrix), encoding="utf-8")

    return {
        "output_dir": output,
        "matrix_rows": len(matrix),
        "implement_now": _list_by_priority(matrix, "implement_now"),
        "design_first": _list_by_priority(matrix, "design_first"),
        "interface_only": _list_by_priority(matrix, "interface_only"),
        "skip_current_stage": _list_by_priority(matrix, "skip_current_stage"),
    }


__all__ = [
    "DETECTOR_SPECS",
    "FIELD_CANDIDATES",
    "build_detector_gap_matrix",
    "build_next_prompt_md",
    "collect_report_schema",
    "field_availability_rows",
    "write_detector_completion_audit",
]
