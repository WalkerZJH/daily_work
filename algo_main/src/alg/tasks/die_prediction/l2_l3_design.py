"""L2/L3 algorithm alignment design for alive prediction.

This module generates design documents only. It does not implement L2/L3,
apply FDR, modify M1-M7 outputs, train models, call LLMs, or generate line
cards.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


OUTPUT_DIR = Path("reports/alive_prediction_l2_l3_design_v1")


def load_csv_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def read_text_if_exists(path: Path, max_chars: int | None = None) -> str:
    if not path.exists():
        return f"MISSING: {path.as_posix()}"
    text = path.read_text(encoding="utf-8", errors="replace")
    return text if max_chars is None else text[:max_chars]


def fdr_group_key(cutoff_month: str, horizon: str | int, detector_name: str) -> str:
    return f"{cutoff_month}|H{str(horizon).replace('H', '')}|{detector_name}"


def build_detector_eligibility_matrix(project_root: Path | None = None) -> pd.DataFrame:
    """Build static L3 eligibility design matrix."""
    rows = [
        {
            "detector_name": "terminal_loss_warning",
            "detector_family": "terminal_dynamic",
            "source_version": "v1",
            "detector_type": "survival_state_evidence",
            "has_p_value": False,
            "fdr_eligible": False,
            "corroboration_eligible": "true",
            "effective_signal_family": "terminal_dynamic",
            "can_upgrade_status": True,
            "can_suppress_status": False,
            "notes": "state evidence; can support recurring review but does not produce p_value",
        },
        {
            "detector_name": "purchase_frequency_fluctuation_warning",
            "detector_family": "sales_fluctuation",
            "source_version": "v1",
            "detector_type": "rule_evidence",
            "has_p_value": False,
            "fdr_eligible": False,
            "corroboration_eligible": "weak",
            "effective_signal_family": "sales_frequency",
            "can_upgrade_status": False,
            "can_suppress_status": False,
            "notes": "legacy frequency rule; weak corroboration only after D002 exists",
        },
        {
            "detector_name": "purchase_quantity_fluctuation_warning",
            "detector_family": "sales_fluctuation",
            "source_version": "v1",
            "detector_type": "rule_evidence",
            "has_p_value": False,
            "fdr_eligible": False,
            "corroboration_eligible": "weak",
            "effective_signal_family": "sales_quantity",
            "can_upgrade_status": False,
            "can_suppress_status": False,
            "notes": "high_hit_rate_caveat; cannot alone support strong evidence",
        },
        {
            "detector_name": "new_terminal_detection",
            "detector_family": "terminal_dynamic",
            "source_version": "v1",
            "detector_type": "factual_one_shot_evidence",
            "has_p_value": False,
            "fdr_eligible": False,
            "corroboration_eligible": "false_for_recurring",
            "effective_signal_family": "one_shot_new_terminal",
            "can_upgrade_status": False,
            "can_suppress_status": False,
            "notes": "one-shot/new terminal fact; not recurring churn corroboration",
        },
        {
            "detector_name": "purchase_interval_overdue_warning",
            "detector_family": "terminal_dynamic",
            "source_version": "v2",
            "detector_type": "interval_state_evidence",
            "has_p_value": False,
            "fdr_eligible": False,
            "corroboration_eligible": "true",
            "effective_signal_family": "terminal_dynamic",
            "can_upgrade_status": True,
            "can_suppress_status": False,
            "notes": "D001 has no p_value while MAD missing; corroboration only",
        },
        {
            "detector_name": "purchase_frequency_decay_rate_test",
            "detector_family": "sales_fluctuation",
            "source_version": "v2",
            "detector_type": "statistical_test",
            "has_p_value": True,
            "fdr_eligible": True,
            "corroboration_eligible": "true",
            "effective_signal_family": "sales_frequency",
            "can_upgrade_status": True,
            "can_suppress_status": False,
            "notes": "D002 is current v1 FDR statistical detector",
        },
        {
            "detector_name": "low_price_purchase_warning",
            "detector_family": "price_warning",
            "source_version": "v1",
            "detector_type": "interface_only",
            "has_p_value": False,
            "fdr_eligible": False,
            "corroboration_eligible": "false",
            "effective_signal_family": "price_warning_interface_only",
            "can_upgrade_status": False,
            "can_suppress_status": False,
            "notes": "interface_only_not_effective_evidence",
        },
        {
            "detector_name": "order_price_spread_warning",
            "detector_family": "price_warning",
            "source_version": "v1",
            "detector_type": "interface_only",
            "has_p_value": False,
            "fdr_eligible": False,
            "corroboration_eligible": "false",
            "effective_signal_family": "price_warning_interface_only",
            "can_upgrade_status": False,
            "can_suppress_status": False,
            "notes": "interface_only_not_effective_evidence",
        },
        {
            "detector_name": "rejection_response_warning",
            "detector_family": "delivery_response",
            "source_version": "v1",
            "detector_type": "interface_only_skipped",
            "has_p_value": False,
            "fdr_eligible": False,
            "corroboration_eligible": "false",
            "effective_signal_family": "delivery_response_interface_only",
            "can_upgrade_status": False,
            "can_suppress_status": False,
            "notes": "skipped_current_stage_user_decision",
        },
        {
            "detector_name": "delayed_response_warning",
            "detector_family": "delivery_response",
            "source_version": "v1",
            "detector_type": "interface_only_skipped",
            "has_p_value": False,
            "fdr_eligible": False,
            "corroboration_eligible": "false",
            "effective_signal_family": "delivery_response_interface_only",
            "can_upgrade_status": False,
            "can_suppress_status": False,
            "notes": "skipped_current_stage_user_decision",
        },
        {
            "detector_name": "low_delivery_rate_warning",
            "detector_family": "delivery_response",
            "source_version": "v1",
            "detector_type": "interface_only_skipped",
            "has_p_value": False,
            "fdr_eligible": False,
            "corroboration_eligible": "false",
            "effective_signal_family": "delivery_response_interface_only",
            "can_upgrade_status": False,
            "can_suppress_status": False,
            "notes": "skipped_current_stage_user_decision",
        },
    ]
    return pd.DataFrame(rows)


def build_fdr_design_matrix(eligibility: pd.DataFrame | None = None) -> pd.DataFrame:
    eligibility = eligibility if eligibility is not None else build_detector_eligibility_matrix()
    fdr_rows = []
    for _, row in eligibility.iterrows():
        if bool(row["fdr_eligible"]):
            fdr_rows.append(
                {
                    "detector_name": row["detector_name"],
                    "fdr_scope": "cutoff_month x horizon x detector_name",
                    "fdr_group_key_template": "{cutoff_month}|{horizon}|{detector_name}",
                    "q": 0.10,
                    "apply_by_cutoff": True,
                    "apply_by_horizon": True,
                    "mix_across_detector_families": False,
                    "required_input_fields": "candidate_id;cutoff_month;horizon;detector_name;p_value",
                    "output_fields": "fdr_group_key;raw_p_value;bh_threshold;fdr_pass_flag;fdr_q_value;fdr_applied",
                    "fdr_status_if_missing": "not_applicable_no_p_value",
                    "notes": "first L3 implementation should run only for D002",
                }
            )
        else:
            fdr_rows.append(
                {
                    "detector_name": row["detector_name"],
                    "fdr_scope": "not_applicable",
                    "fdr_group_key_template": "",
                    "q": "",
                    "apply_by_cutoff": False,
                    "apply_by_horizon": False,
                    "mix_across_detector_families": False,
                    "required_input_fields": "",
                    "output_fields": "fdr_status",
                    "fdr_status_if_missing": "not_applicable_no_p_value",
                    "notes": "excluded from FDR; can only support corroboration if eligible",
                }
            )
    return pd.DataFrame(fdr_rows)


def effective_signal_families(evidence: pd.DataFrame, eligibility: pd.DataFrame | None = None, fdr_applied: bool = False) -> set[str]:
    if evidence.empty:
        return set()
    eligibility = eligibility if eligibility is not None else build_detector_eligibility_matrix()
    meta = eligibility.set_index("detector_name").to_dict("index")
    families: set[str] = set()
    for _, row in evidence.iterrows():
        name = str(row.get("detector_name", ""))
        info = meta.get(name)
        if not info:
            continue
        if str(info["corroboration_eligible"]).lower() in {"false", "false_for_recurring"}:
            continue
        if not _truthy(row.get("hit_flag", False)):
            continue
        if str(row.get("data_quality_status", "")).lower() == "not_evaluable":
            continue
        if bool(info["fdr_eligible"]) and fdr_applied and not _truthy(row.get("fdr_pass_flag", False)):
            continue
        families.add(str(info["effective_signal_family"]))
    return families


def corroboration_level(evidence: pd.DataFrame, l2_guardrail: str = "none", fdr_applied: bool = False) -> str:
    if l2_guardrail in {"peer_suppressed", "policy_caveat", "systemic_delivery_caveat", "suppressed_by_l2"}:
        return "suppressed_by_l2"
    families = effective_signal_families(evidence, fdr_applied=fdr_applied)
    if not families:
        return "none"
    has_stat = False
    if not evidence.empty and "detector_name" in evidence.columns:
        stat_hits = evidence["detector_name"].astype(str).eq("purchase_frequency_decay_rate_test") & evidence.get(
            "hit_flag", pd.Series(False, index=evidence.index)
        ).map(_truthy)
        has_stat = bool(stat_hits.any())
    if len(families) >= 2:
        return "multi_signal"
    if has_stat and not fdr_applied:
        return "provisional_fdr_ready"
    return "single_signal"


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def build_risk_register() -> pd.DataFrame:
    rows = [
        ("L2L3_R001", "FDR", "Only D002 currently supports p_value.", "medium", "high", "Limit FDR v1 to D002.", "D002-only FDR scope.", True, "Confirm D002 as the only v1 FDR detector."),
        ("L2L3_R002", "D001", "D001 lacks MAD and p_value.", "medium", "high", "Use as interval corroboration only.", "Exclude D001 from FDR.", False, "Add interval MAD later if FDR is needed."),
        ("L2L3_R003", "quantity", "Quantity detector hit rate is high.", "medium", "medium", "Treat quantity as weak evidence.", "Do not allow quantity-only strong upgrade.", True, "Confirm whether quantity can participate in multi-signal."),
        ("L2L3_R004", "peer", "Peer cohort may be too small.", "medium", "medium", "Use cohort fallback and not_evaluable flag.", "Define cohort_min_size.", True, "Choose min cohort size."),
        ("L2L3_R005", "policy", "Policy/procurement data missing.", "high", "medium", "Interface-only caveat.", "Do not confirm policy loss.", True, "Confirm availability of bid/procurement fields."),
        ("L2L3_R006", "delivery", "Delivery detectors are skipped.", "medium", "high", "skipped_current_stage.", "No strong delivery mask.", False, "Revisit only if user reopens delivery scope."),
        ("L2L3_R007", "product_line", "Product-line mapping is missing.", "medium", "high", "Keep SKU/wallet out of L3.", "No SKU/wallet corroboration.", True, "Provide product_line mapping."),
        ("L2L3_R008", "status", "Aligned status may become too complex.", "medium", "medium", "Write aligned output as sidecar.", "Do not overwrite M5.", False, "Run side-by-side review."),
        ("L2L3_R009", "P0", "P0/strong evidence policy is undecided.", "medium", "medium", "Keep auto dispatch false.", "P0 only after L2/L3 evidence passes.", True, "Confirm whether P0 may appear."),
        ("L2L3_R010", "semantics", "L2/L3 could be mistaken for probability calibration.", "high", "medium", "Explicit semantics audit.", "Never change probability/business priority.", False, "Keep M5/M7 score fields unchanged."),
    ]
    return pd.DataFrame(
        rows,
        columns=[
            "risk_id",
            "risk_area",
            "risk_description",
            "severity",
            "likelihood",
            "current_mitigation",
            "design_decision",
            "requires_user_decision",
            "recommended_action",
        ],
    )


def build_design_markdowns(project_root: Path, eligibility: pd.DataFrame, fdr_matrix: pd.DataFrame) -> dict[str, str]:
    current = read_current_status(project_root)
    fdr_detectors = eligibility.loc[eligibility["fdr_eligible"], "detector_name"].tolist()
    corroboration_only = eligibility.loc[
        (~eligibility["fdr_eligible"]) & eligibility["corroboration_eligible"].isin(["true", "weak"]),
        "detector_name",
    ].tolist()
    interface_only = eligibility.loc[eligibility["detector_type"].astype(str).str.contains("interface"), "detector_name"].tolist()
    return {
        "l2_l3_design_summary.md": _summary_md(current, fdr_detectors, corroboration_only, interface_only),
        "l2_guardrail_policy.md": _l2_guardrail_policy_md(),
        "l2_peer_specificity_design.md": _l2_peer_specificity_md(),
        "l2_policy_seasonality_delivery_design.md": _l2_policy_seasonality_delivery_md(),
        "l3_fdr_scope_design.md": _l3_fdr_scope_md(fdr_detectors),
        "l3_signal_family_corroboration_design.md": _l3_corroboration_md(),
        "aligned_status_decision_policy.md": _aligned_status_policy_md(),
        "l2_l3_integration_contract.md": _integration_contract_md(),
        "l2_l3_open_questions.md": _open_questions_md(),
        "l2_l3_implementation_sequence.md": _implementation_sequence_md(),
        "l2_l3_implementation_prompt_draft.md": _implementation_prompt_md(),
    }


def read_current_status(project_root: Path) -> dict[str, Any]:
    pvalue = load_csv_if_exists(project_root / "reports/alive_prediction_detectors_v2/detector_v2_p_value_readiness_report.csv")
    stage = read_text_if_exists(project_root / "reports/alive_prediction_stage_end_audit_v1/stage_end_freeze_decision.md", 2000)
    d002_rows = 0
    d002_p = 0
    d001_p = 0
    if not pvalue.empty:
        d002 = pvalue.loc[pvalue["detector_name"] == "purchase_frequency_decay_rate_test"]
        d001 = pvalue.loc[pvalue["detector_name"] == "purchase_interval_overdue_warning"]
        if not d002.empty:
            d002_rows = int(pd.to_numeric(d002["evaluated_row_count"], errors="coerce").fillna(0).iloc[0])
            d002_p = int(pd.to_numeric(d002["p_value_available_count"], errors="coerce").fillna(0).iloc[0])
        if not d001.empty:
            d001_p = int(pd.to_numeric(d001["p_value_available_count"], errors="coerce").fillna(0).iloc[0])
    return {"d002_rows": d002_rows, "d002_p": d002_p, "d001_p": d001_p, "stage_freeze_text": stage}


def _summary_md(current: dict[str, Any], fdr_detectors: list[str], corroboration_only: list[str], interface_only: list[str]) -> str:
    return f"""# L2/L3 Design Summary

## Why Not Implement Directly

L2/L3 should not be implemented as a single engineering jump because L2
requires demand-side decisions on peer suppression, policy caveats, and P0
criteria, while L3 currently has only one statistically testable detector.
Implementing all at once would risk contaminating probability semantics and
making detector evidence look like a new score.

## Current FDR Inputs

- D002 evaluated rows: {current['d002_rows']}
- D002 p_value available: {current['d002_p']}
- D001 p_value available: {current['d001_p']}
- FDR v1 eligible detectors: {fdr_detectors}

## Detector Roles

- FDR detectors: {fdr_detectors}
- Corroboration-only detectors: {corroboration_only}
- Interface/explanation-only detectors: {interface_only}

## Recommended FDR Scope

FDR v1 should run only on `purchase_frequency_decay_rate_test`, grouped by
`cutoff_month x horizon x detector_name`, with BH q=0.10.

## L2 v1 Guardrails

Start with peer specificity as the first evaluable guardrail. Policy,
seasonality, and systemic delivery should remain caveat/interface designs until
fields and user decisions are confirmed.

## Aligned Status

Aligned status should be emitted as sidecar outputs and must not overwrite M5 or
M7. It may adjust review labels and caveats, but must not change probability,
business priority, detector evidence, or auto-dispatch.

## Implementation Recommendation

Proceed conditionally with Phase 1 only: D002 FDR, signal family aggregation,
corroboration_level, and aligned_candidate_status_decision_v1 as sidecar output.
User decisions are still needed for peer suppression vs caveat, cohort size,
quantity weak-signal participation, and whether P0 can appear.
"""


def _l2_guardrail_policy_md() -> str:
    return """# L2 Guardrail Policy

L2 is false-positive guardrail design, not probability recalculation.

L2 responsibilities:

1. Detect likely false churn signals.
2. Decide whether a strong alert should be suppressed or caveated.
3. Mark manual-review requirements.
4. Provide guardrail fields for M5/M7.

L2 must not:

1. Change `churn_probability_H`.
2. Change `relative_business_priority_score_H`.
3. Produce a new risk probability.
4. Delete candidates.
5. Enable auto dispatch.

Recommended L2 result fields:

- `peer_specificity_flag`
- `false_positive_guardrail`
- `policy_mask_status`
- `seasonality_status`
- `systemic_delivery_status`
- `l2_guardrail_reason`
- `l2_manual_review_required`
"""


def _l2_peer_specificity_md() -> str:
    return """# L2 Peer Specificity Design

## Goal

Separate entity-specific decline from cohort-wide decline.

## Cohort Fallback

1. `manufacturer_code x province_code x hospital_level_code x drug_category_code`
2. `manufacturer_code x province_code x drug_category_code`
3. `manufacturer_code x hospital_level_code x drug_category_code`
4. `manufacturer_code x drug_category_code`
5. global fallback

## Parameters

- `cohort_min_size`: user decision required; initial design placeholder 30.
- Recent/base decline metrics: reuse D002 rate ratio or order-count windows.
- Demand-shape adjustment: intermittent/lumpy lower peer specificity weight.

## Outputs

`peer_specificity_flag`:

- `specific_decline`
- `cohort_wide_decline`
- `no_specific_decline`
- `not_evaluable`

`false_positive_guardrail`:

- `none`
- `peer_suppressed`
- `peer_caveat`
- `not_evaluable`

## Open Design Choice

`cohort_wide_decline` should probably start as `peer_caveat`, not hard
suppression, until backtest proves it reduces false positives without hiding
recoverable accounts.
"""


def _l2_policy_seasonality_delivery_md() -> str:
    return """# L2 Policy / Seasonality / Delivery Design

## Policy / Procurement Caveat

Output:

- `policy_mask_status = policy_mask_applied | policy_caveat | not_evaluable`

Rules:

- Do not infer procurement loss from medical-insurance category alone.
- If bid/win/loss fields are absent, default to `not_evaluable`.
- Do not claim policy loss is confirmed.
- Use caveat/manual review only.

## Seasonality Caveat

Output:

- `seasonality_status = seasonal_caveat | no_seasonal_evidence | not_evaluable`

Design:

- Require same-month history or peer same-period data.
- Avoid STL when history is short.
- Prefer caveat for short-window alerts rather than hard suppression.

## Systemic Delivery Caveat

User decided delivery detectors are not supplemented in this stage.

Output:

- `systemic_delivery_status = skipped_current_stage`

Rules:

- Do not confirm distributor responsibility.
- Do not use delivery as strong de-fake mask.
- Keep fields for future integration only.
"""


def _l3_fdr_scope_md(fdr_detectors: list[str]) -> str:
    return f"""# L3 FDR Scope Design

## FDR Applies To

FDR v1 applies only to: {fdr_detectors}

## Scope

`cutoff_month x horizon x detector_name`

Reasoning:

1. Different cutoffs are different inspection days.
2. Different horizons have different business meaning.
3. Detector p-values have different statistical assumptions.
4. Current v1 has only D002 as p-value-ready.

## Parameter

- Benjamini-Hochberg q = 0.10

## Non-FDR Detectors

- D001 has no p-value while MAD is missing: `fdr_status = not_applicable_no_p_value`.
- Rule/state detectors are corroboration only.
- Quantity detector is not in FDR.
- Interface-only detectors are excluded.

## Future Output Fields

- `fdr_group_key`
- `raw_p_value`
- `bh_threshold`
- `fdr_pass_flag`
- `fdr_q_value`
- `fdr_applied`
"""


def _l3_corroboration_md() -> str:
    return """# L3 Signal Family Corroboration Design

## Signal Families

1. `terminal_dynamic`
2. `sales_frequency`
3. `sales_quantity`
4. `one_shot_new_terminal`
5. `price_warning_interface_only`
6. `delivery_response_interface_only`

## Effective Signal Rules

Only count a signal family when:

1. `hit_flag = true`.
2. `data_quality_status != not_evaluable`.
3. detector is not interface-only.
4. if statistical and FDR applied, `fdr_pass_flag = true`.
5. if statistical and FDR ready but not yet applied, mark provisional.
6. quantity detector is weak and cannot alone support strong evidence.

## corroboration_level

- `none`
- `single_signal`
- `multi_signal`
- `multi_signal_with_peer_specificity`
- `suppressed_by_l2`
- `provisional_fdr_ready`
"""


def _aligned_status_policy_md() -> str:
    return """# Aligned Status Decision Policy

This is future design only. It must not overwrite M5 outputs.

## Inputs

- M5 `candidate_status_decision`
- L2 guardrail results
- L3 corroboration results
- M4/M4v2 detector evidence

## Rules

1. If L2 guardrail is `peer_suppressed`, `policy_caveat`, or `systemic_delivery_caveat`, downgrade `priority_review` to `manual_review` or `observation_only`, and cap review priority at P2.
2. Recurring candidates may become P0/strong only when terminal dynamic evidence, sales-frequency statistical evidence passing FDR, and peer-specific decline align.
3. Terminal dynamic alone can keep `priority_review`, but should not become strong.
4. Quantity-only evidence must never create `priority_review`.
5. One-shot remains `one_shot_attention`.
6. Demand-shape observation remains `observation_only`.
7. `auto_dispatch_allowed` remains false.
"""


def _integration_contract_md() -> str:
    return """# L2/L3 Integration Contract

## Inputs

- `candidate_status_decision.csv`
- `detector_evidence_results.csv`
- `detector_evidence_results_v2.csv`
- `survival_refinement_results.csv`
- `structured_evidence_bundle.csv`

## Outputs

- `l2_guardrail_results.csv`
- `l3_fdr_results.csv`
- `l3_corroboration_results.csv`
- `aligned_candidate_status_decision.csv`
- `aligned_structured_evidence_bundle.csv`

## Contract

1. Do not overwrite original M5/M7 outputs.
2. Aligned outputs are sidecar versioned artifacts.
3. Side-by-side comparison is required.
4. Do not change probability or business-priority scores.
5. Do not enable auto dispatch.
"""


def _open_questions_md() -> str:
    questions = [
        "cohort_wide_decline 是压制还是 caveat？",
        "同侪 cohort 最小样本数取多少？",
        "FDR scope 是否按 cutoff x horizon x detector？",
        "D002 是否足够作为 v1 唯一 FDR detector？",
        "D001 无 p-value 是否只做 corroboration？",
        "quantity detector 是否允许参与 multi_signal？",
        "P0 是否允许出现，还是本阶段继续 P0=0？",
        "policy/集采字段是否可获得？",
        "product_line 映射何时提供？",
        "是否允许 L2/L3 调整 review_priority，但不改 business priority？",
    ]
    return "# L2/L3 Open Questions\n\n" + "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions)) + "\n"


def _implementation_sequence_md() -> str:
    return """# L2/L3 Implementation Sequence

## Phase 1

- L3 FDR for D002 only.
- Signal family aggregation.
- `corroboration_level`.

## Phase 2

- L2 peer specificity proxy.
- `aligned_candidate_status_decision`.

## Phase 3

- Policy/seasonality interfaces.
- Aligned evidence bundle.

## Phase 4

- Backtest whether L2/L3 reduces false positives.

Do not implement all L2/L3 at once.
"""


def _implementation_prompt_md() -> str:
    return """# L2/L3 Implementation Prompt Draft

Implement alive prediction L2/L3 v1 sidecar outputs only.

Scope:

1. D002 FDR by `cutoff_month x horizon x detector_name`.
2. Signal family aggregation.
3. `corroboration_level`.
4. `aligned_candidate_status_decision_v1`.

Do not:

1. Implement policy/seasonality/delivery strong masks.
2. Modify original M5/M7 outputs.
3. Change `churn_probability_H`.
4. Change `relative_business_priority_score_H`.
5. Enable auto dispatch.
6. Call LLM.
7. Generate line cards.
8. Implement M6 cache.
"""


def write_l2_l3_design(project_root: Path, output_dir: Path | None = None) -> dict[str, Any]:
    output = output_dir or project_root / OUTPUT_DIR
    output.mkdir(parents=True, exist_ok=True)

    eligibility = build_detector_eligibility_matrix(project_root)
    fdr_matrix = build_fdr_design_matrix(eligibility)
    risks = build_risk_register()
    docs = build_design_markdowns(project_root, eligibility, fdr_matrix)

    eligibility.to_csv(output / "l3_detector_eligibility_matrix.csv", index=False)
    fdr_matrix.to_csv(output / "l3_fdr_design_matrix.csv", index=False)
    risks.to_csv(output / "l2_l3_risk_register.csv", index=False)
    for filename, text in docs.items():
        (output / filename).write_text(text, encoding="utf-8")

    return {
        "output_dir": output,
        "fdr_eligible": eligibility.loc[eligibility["fdr_eligible"], "detector_name"].tolist(),
        "corroboration_only": eligibility.loc[
            (~eligibility["fdr_eligible"]) & eligibility["corroboration_eligible"].isin(["true", "weak"]),
            "detector_name",
        ].tolist(),
        "interface_only": eligibility.loc[eligibility["detector_type"].astype(str).str.contains("interface"), "detector_name"].tolist(),
        "risk_count": len(risks),
    }


__all__ = [
    "build_detector_eligibility_matrix",
    "build_fdr_design_matrix",
    "build_risk_register",
    "corroboration_level",
    "effective_signal_families",
    "fdr_group_key",
    "load_csv_if_exists",
    "read_text_if_exists",
    "write_l2_l3_design",
]
