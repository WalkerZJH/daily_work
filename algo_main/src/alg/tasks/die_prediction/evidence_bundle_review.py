"""End-to-end sample review helpers for M1-M7 structured evidence bundles.

The review layer is read-only. It audits bundle completeness, claim boundaries,
and actionability before a later LLM/MCP line-card prototype is allowed to
consume the structured material.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


STATUS_SAMPLE_LIMITS = {
    "priority_review": 20,
    "manual_review": 20,
    "low_confidence_watch": 10,
    "observation_only": 10,
    "one_shot_attention": 20,
}
TYPE_SAMPLE_LIMITS = {"demand_shape_observation": 10}
PRIORITY_SAMPLE_LIMITS = {"P1": 10, "P2": 10}
STRENGTH_SAMPLE_LIMITS = {"insufficient": 10}
FORBIDDEN_TEXTS = [
    "医院已经确定流失",
    "医院一定不会再采购",
    "医院主动弃用",
    "竞品替代",
    "政策落标",
    "配送商责任",
    "价格异常导致流失",
    "低风险对象一定安全",
    "高风险对象一定流失",
    "auto dispatch allowed",
    "LLM may change risk score",
    "价格 detector 已确认异常",
    "配送 detector 已确认异常",
]
INTERFACE_ONLY_DETECTORS = {
    "low_price_purchase_warning",
    "order_price_spread_warning",
    "rejection_response_warning",
    "delayed_response_warning",
    "low_delivery_rate_warning",
}


def load_csv_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def parse_json_list(value: Any) -> list[Any]:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return []
    if isinstance(value, list):
        return value
    text = str(value).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return [text]
    return parsed if isinstance(parsed, list) else [parsed]


def normalize_bool(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series.fillna(False)
    return series.fillna(False).astype(str).str.lower().isin(["true", "1", "yes", "y"])


def _score_for_sort(df: pd.DataFrame) -> pd.Series:
    ctype = df.get("candidate_type", pd.Series("", index=df.index)).fillna("").astype(str)
    business = pd.to_numeric(df.get("relative_business_priority_score_H", pd.Series(np.nan, index=df.index)), errors="coerce")
    churn = pd.to_numeric(df.get("churn_probability_H", pd.Series(np.nan, index=df.index)), errors="coerce")
    repeat = pd.to_numeric(df.get("repeat_probability_H", pd.Series(np.nan, index=df.index)), errors="coerce")
    return np.where(ctype.eq("one_shot_attention"), repeat.fillna(0), business.fillna(0) + churn.fillna(0))


def sorted_candidates(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    status_order = {
        "priority_review": 0,
        "manual_review": 1,
        "low_confidence_watch": 2,
        "observation_only": 3,
        "one_shot_attention": 4,
        "not_actionable": 5,
    }
    work = df.copy()
    work["_priority_order"] = work.get("review_priority", pd.Series("", index=work.index)).map(priority_order).fillna(99)
    work["_status_order"] = work.get("final_candidate_status", pd.Series("", index=work.index)).map(status_order).fillna(99)
    work["_sort_score"] = _score_for_sort(work)
    return work.sort_values(
        ["_priority_order", "_status_order", "_sort_score", "candidate_id"],
        ascending=[True, True, False, True],
    ).drop(columns=["_priority_order", "_status_order", "_sort_score"])


def stratified_sample(bundle: pd.DataFrame) -> pd.DataFrame:
    """Build a deterministic review sample across status/type/priority strata."""
    if bundle is None or bundle.empty:
        return pd.DataFrame(columns=bundle.columns if bundle is not None else [])
    samples = []
    for status, limit in STATUS_SAMPLE_LIMITS.items():
        part = bundle[bundle["final_candidate_status"].eq(status)]
        samples.append(sorted_candidates(part).head(limit))
    for candidate_type, limit in TYPE_SAMPLE_LIMITS.items():
        part = bundle[bundle["candidate_type"].eq(candidate_type)]
        samples.append(sorted_candidates(part).head(limit))
    for priority, limit in PRIORITY_SAMPLE_LIMITS.items():
        part = bundle[bundle["review_priority"].eq(priority)]
        samples.append(sorted_candidates(part).head(limit))
    for strength, limit in STRENGTH_SAMPLE_LIMITS.items():
        part = bundle[bundle["evidence_strength"].eq(strength)]
        samples.append(sorted_candidates(part).head(limit))
    out = pd.concat([s for s in samples if s is not None and not s.empty], ignore_index=True)
    if out.empty:
        return out
    key = "bundle_id" if "bundle_id" in out.columns else "candidate_id"
    return out.drop_duplicates(key).reset_index(drop=True)


def claim_consistency_audit(bundle: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if bundle is None or bundle.empty:
        return pd.DataFrame(columns=["candidate_id", "candidate_type", "claim_check_pass", "violation_type", "violation_detail", "recommended_fix"])
    for _, row in bundle.iterrows():
        candidate_id = row.get("candidate_id")
        candidate_type = row.get("candidate_type")
        allowed = [str(x) for x in parse_json_list(row.get("allowed_claims"))]
        forbidden = [str(x) for x in parse_json_list(row.get("forbidden_claims"))]
        detector_list = parse_json_list(row.get("detector_evidence_list"))
        violations: list[tuple[str, str, str]] = []
        if not allowed:
            violations.append(("allowed_claims_empty", "", "Regenerate allowed_claims for this bundle."))
        if not forbidden:
            violations.append(("forbidden_claims_empty", "", "Regenerate forbidden_claims for this bundle."))
        allowed_text = " | ".join(allowed)
        forbidden_text = " | ".join(forbidden)
        for forbidden_phrase in FORBIDDEN_TEXTS:
            if forbidden_phrase in allowed_text:
                violations.append(
                    ("allowed_contains_forbidden_phrase", forbidden_phrase, "Remove forbidden causal or certainty claim from allowed_claims.")
                )
        if candidate_type == "one_shot_attention":
            churn_value = row.get("churn_probability_H")
            if pd.notna(churn_value):
                violations.append(("one_shot_churn_probability_field_non_null", str(churn_value), "Clear churn_probability_H for one-shot rows."))
            positive_churn_claim = [
                claim
                for claim in allowed
                if "churn_probability" in claim
                and "不是" not in claim
                and "not" not in claim.lower()
                and "recurring" in claim.lower()
            ]
            if positive_churn_claim:
                violations.append(("one_shot_churn_probability_claim", " | ".join(positive_churn_claim), "Only allow repeat_probability_H wording for one-shot."))
        if candidate_type == "recurring_business_priority":
            repeat_value = row.get("repeat_probability_interpretation", "")
            repeat_interp = "" if pd.isna(repeat_value) else str(repeat_value)
            if repeat_interp.strip():
                violations.append(("recurring_repeat_probability_interpretation", repeat_interp, "Remove one-shot repeat probability interpretation from recurring rows."))
        if any("价格 detector 已确认异常" in claim or "配送 detector 已确认异常" in claim for claim in allowed):
            violations.append(("interface_only_detector_allowed_as_fact", "", "Keep price/delivery detector limitations in forbidden or limitations only."))
        for evidence in detector_list:
            if isinstance(evidence, dict) and evidence.get("detector_name") in INTERFACE_ONLY_DETECTORS:
                violations.append(("interface_only_detector_in_evidence_list", evidence.get("detector_name"), "Remove interface-only detector from effective evidence list."))
        if bool(row.get("auto_dispatch_allowed")):
            violations.append(("auto_dispatch_allowed_true", "auto_dispatch_allowed=true", "Set auto_dispatch_allowed to false."))
        if bool(row.get("evidence_timeline_available")):
            violations.append(("evidence_timeline_available_true", "evidence_timeline_available=true", "M6 is not implemented; set timeline availability to false."))
        if "LLM may change risk score" in allowed_text:
            violations.append(("llm_score_change_allowed", "LLM may change risk score", "Forbid LLM from changing scores/status."))
        if not violations:
            rows.append(
                {
                    "candidate_id": candidate_id,
                    "candidate_type": candidate_type,
                    "claim_check_pass": True,
                    "violation_type": "",
                    "violation_detail": "",
                    "recommended_fix": "",
                }
            )
        else:
            for violation_type, detail, fix in violations:
                rows.append(
                    {
                        "candidate_id": candidate_id,
                        "candidate_type": candidate_type,
                        "claim_check_pass": False,
                        "violation_type": violation_type,
                        "violation_detail": detail,
                        "recommended_fix": fix,
                    }
                )
    return pd.DataFrame(rows)


def _non_empty(row: pd.Series, field: str) -> bool:
    value = row.get(field)
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return False
    return str(value).strip() not in {"", "[]", "nan", "None"}


def actionability_audit(bundle: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if bundle is None or bundle.empty:
        return pd.DataFrame(columns=["candidate_id", "candidate_type", "actionable_flag", "missing_critical_fields", "actionability_note"])
    for _, row in bundle.iterrows():
        candidate_type = row.get("candidate_type")
        if candidate_type == "recurring_business_priority":
            required = [
                "final_candidate_status",
                "review_priority",
                "churn_probability_H",
                "relative_business_priority_score_H",
                "survival_state",
                "recommended_action_candidates",
                "forbidden_claims",
            ]
            has_evidence = _non_empty(row, "detector_evidence_list") or _non_empty(row, "survival_summary")
            missing = [field for field in required if not _non_empty(row, field)]
            if not has_evidence:
                missing.append("detector_evidence_list_or_survival_summary")
        elif candidate_type == "one_shot_attention":
            required = [
                "repeat_probability_interpretation",
                "recommended_action_candidates",
                "forbidden_claims",
            ]
            missing = [field for field in required if not _non_empty(row, field)]
            if not _non_empty(row, "repeat_probability_H") and not _non_empty(row, "business_priority_reference"):
                missing.append("repeat_probability_H_or_selected_attention_score")
            if "not_recurring_churn_probability" not in str(row.get("repeat_probability_interpretation", "")):
                missing.append("one_shot_non_recurring_churn_note")
        elif candidate_type == "demand_shape_observation":
            required = [
                "demand_shape_label",
                "guardrail_summary",
                "recommended_action_candidates",
                "forbidden_claims",
            ]
            missing = [field for field in required if not _non_empty(row, field)]
            if str(row.get("final_candidate_status")) != "observation_only":
                missing.append("observation_only_status")
        else:
            missing = ["unknown_candidate_type"]
        rows.append(
            {
                "candidate_id": row.get("candidate_id"),
                "candidate_type": candidate_type,
                "actionable_flag": len(missing) == 0,
                "missing_critical_fields": ";".join(missing),
                "actionability_note": "minimum_structured_material_available" if len(missing) == 0 else "missing_critical_fields",
            }
        )
    return pd.DataFrame(rows)


def field_completeness_by_status(bundle: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "candidate_type",
        "final_candidate_status",
        "review_priority",
        "evidence_strength",
        "row_count",
        "churn_probability_H_non_null_rate",
        "repeat_probability_H_non_null_rate",
        "relative_business_priority_score_H_non_null_rate",
        "survival_summary_non_null_rate",
        "detector_evidence_list_non_null_rate",
        "allowed_claims_non_null_rate",
        "forbidden_claims_non_null_rate",
        "recommended_action_candidates_non_null_rate",
        "data_quality_note_non_null_rate",
        "auto_dispatch_false_rate",
        "evidence_timeline_false_rate",
    ]
    if bundle is None or bundle.empty:
        return pd.DataFrame(columns=cols)
    rows = []
    for keys, group in bundle.groupby(["candidate_type", "final_candidate_status", "review_priority", "evidence_strength"], dropna=False):
        rows.append(
            {
                "candidate_type": keys[0],
                "final_candidate_status": keys[1],
                "review_priority": keys[2],
                "evidence_strength": keys[3],
                "row_count": len(group),
                "churn_probability_H_non_null_rate": float(group["churn_probability_H"].notna().mean()),
                "repeat_probability_H_non_null_rate": float(group["repeat_probability_H"].notna().mean()),
                "relative_business_priority_score_H_non_null_rate": float(group["relative_business_priority_score_H"].notna().mean()),
                "survival_summary_non_null_rate": float(group["survival_summary"].fillna("").astype(str).ne("").mean()),
                "detector_evidence_list_non_null_rate": float(group["detector_evidence_list"].fillna("[]").astype(str).ne("[]").mean()),
                "allowed_claims_non_null_rate": float(group["allowed_claims"].fillna("").astype(str).ne("").mean()),
                "forbidden_claims_non_null_rate": float(group["forbidden_claims"].fillna("").astype(str).ne("").mean()),
                "recommended_action_candidates_non_null_rate": float(group["recommended_action_candidates"].fillna("").astype(str).ne("").mean()),
                "data_quality_note_non_null_rate": float(group["data_quality_note"].fillna("").astype(str).ne("").mean()),
                "auto_dispatch_false_rate": float((~normalize_bool(group["auto_dispatch_allowed"])).mean()),
                "evidence_timeline_false_rate": float((~normalize_bool(group["evidence_timeline_available"])).mean()),
            }
        )
    return pd.DataFrame(rows, columns=cols)


def build_sample_review_markdown(sample: pd.DataFrame) -> str:
    lines = [
        "# Evidence Bundle Sample Review",
        "",
        "This is a structured sample review, not a final line card and not LLM-generated copy.",
        "",
    ]
    questions = [
        "该对象为什么进入当前状态？",
        "是否有足够证据支持当前状态？",
        "是否存在不应生成的因果结论？",
        "如果交给 LLM，哪些事实可以说？",
        "如果交给 LLM，哪些话不能说？",
        "是否需要人工复核？",
        "是否可以进入线索卡生成候选？",
    ]
    for i, (_, row) in enumerate(sample.iterrows(), start=1):
        detector_summary = parse_json_list(row.get("detector_evidence_list"))[:3]
        allowed = parse_json_list(row.get("allowed_claims"))[:5]
        forbidden = parse_json_list(row.get("forbidden_claims"))[:5]
        actions = parse_json_list(row.get("recommended_action_candidates"))[:5]
        lines += [
            f"## Sample {i}",
            "",
            f"- candidate_id: `{row.get('candidate_id')}`",
            f"- candidate_type: `{row.get('candidate_type')}`",
            f"- entity_key: `{row.get('manufacturer_code')}|{row.get('hospital_code')}|{row.get('drug_group')}|{row.get('drug_group_source')}`",
            f"- cutoff_month / horizon: `{row.get('cutoff_month')}` / `{row.get('horizon')}`",
            f"- final_candidate_status: `{row.get('final_candidate_status')}`",
            f"- review_priority: `{row.get('review_priority')}`",
            f"- evidence_strength: `{row.get('evidence_strength')}`",
            f"- probability reference: churn=`{row.get('churn_probability_H')}`, repeat=`{row.get('repeat_probability_H')}`",
            f"- business priority reference: `{row.get('relative_business_priority_score_H')}`",
            f"- survival summary: `{row.get('survival_summary')}`",
            f"- demand-shape guardrail summary: `{row.get('guardrail_summary')}`",
            f"- top detector evidence: `{json.dumps(detector_summary, ensure_ascii=False)}`",
            f"- allowed_claims summary: `{json.dumps(allowed, ensure_ascii=False)}`",
            f"- forbidden_claims summary: `{json.dumps(forbidden, ensure_ascii=False)}`",
            f"- recommended_action_candidates summary: `{json.dumps(actions, ensure_ascii=False)}`",
            f"- data_quality_note: `{row.get('data_quality_note')}`",
            "- reviewer_check_questions:",
        ]
        lines += [f"  - {q}" for q in questions]
        lines.append("")
    return "\n".join(lines)


def llm_readiness_report(bundle: pd.DataFrame, claim_audit: pd.DataFrame) -> str:
    allowed_rate = float(bundle["allowed_claims"].fillna("").astype(str).ne("").mean()) if not bundle.empty else 0.0
    forbidden_rate = float(bundle["forbidden_claims"].fillna("").astype(str).ne("").mean()) if not bundle.empty else 0.0
    action_rate = float(bundle["recommended_action_candidates"].fillna("").astype(str).ne("").mean()) if not bundle.empty else 0.0
    violations = int((~claim_audit["claim_check_pass"]).sum()) if not claim_audit.empty else 0
    auto_false = bool((~normalize_bool(bundle["auto_dispatch_allowed"])).all()) if not bundle.empty else True
    one_shot_pollution = int(
        claim_audit["violation_type"].fillna("").astype(str).str.contains("one_shot_churn", regex=False).sum()
    ) if not claim_audit.empty else 0
    proceed = (
        "conditional"
        if allowed_rate == 1.0 and forbidden_rate == 1.0 and action_rate == 1.0 and violations == 0 and auto_false
        else "no"
    )
    lines = [
        "# Evidence Bundle LLM Readiness Report",
        "",
        f"proceed_to_llm_line_card = {proceed}",
        "manual_review_required_before_llm = yes",
        "m6_cache_implemented = false",
        "",
        f"- allowed_claims coverage: {allowed_rate:.4f}",
        f"- forbidden_claims coverage: {forbidden_rate:.4f}",
        f"- recommended_action_candidates coverage: {action_rate:.4f}",
        f"- claim consistency violations: {violations}",
        f"- one-shot churn semantic pollution violations: {one_shot_pollution}",
        f"- auto_dispatch_allowed all false: {auto_false}",
        "",
        "condition: LLM may only transform allowed_claims and recommended_action_candidates into readable text. LLM must not change score, probability, status, detector evidence, or priority.",
    ]
    return "\n".join(lines)


def review_summary(
    bundle: pd.DataFrame,
    sample: pd.DataFrame,
    claim_audit: pd.DataFrame,
    action_audit: pd.DataFrame,
    completeness: pd.DataFrame,
) -> str:
    status_counts = sample["final_candidate_status"].value_counts().to_dict() if not sample.empty else {}
    type_counts = sample["candidate_type"].value_counts().to_dict() if not sample.empty else {}
    violation_count = int((~claim_audit["claim_check_pass"]).sum()) if not claim_audit.empty else 0
    action_rate = float(action_audit["actionable_flag"].mean()) if not action_audit.empty else 0.0
    one_shot_pollution = int(
        claim_audit["violation_type"].fillna("").astype(str).str.contains("one_shot_churn", regex=False).sum()
    ) if not claim_audit.empty else 0
    interface_misuse = int(
        claim_audit["violation_type"].fillna("").astype(str).str.contains("interface_only", regex=False).sum()
    ) if not claim_audit.empty else 0
    p0_count = int(bundle["review_priority"].fillna("").eq("P0").sum()) if not bundle.empty else 0
    strong_count = int(bundle["evidence_strength"].fillna("").eq("strong").sum()) if not bundle.empty else 0
    main_gaps = []
    if not completeness.empty:
        low_cols = []
        rate_cols = [c for c in completeness.columns if c.endswith("_rate")]
        for col in rate_cols:
            if completeness[col].min() < 0.99 and col not in {"data_quality_note_non_null_rate", "has_data_quality_note_rate"}:
                low_cols.append(col)
        main_gaps = low_cols[:8]
    return "\n".join(
        [
            "# Evidence Bundle Review Summary",
            "",
            f"- total bundle rows: {len(bundle)}",
            f"- stratified sample rows: {len(sample)}",
            f"- sample by final_candidate_status: {status_counts}",
            f"- sample by candidate_type: {type_counts}",
            f"- claim consistency violations: {violation_count}",
            f"- actionability pass rate: {action_rate:.4f}",
            f"- field completeness main gaps: {', '.join(main_gaps) if main_gaps else 'none blocking'}",
            f"- one-shot recurring churn semantic pollution: {one_shot_pollution}",
            f"- price/delivery interface-only misuse violations: {interface_misuse}",
            f"- P0 count: {p0_count}; strong evidence count: {strong_count}",
            "- P0=0 / strong=0 should be explicitly shown in later product material as a conservative v1 limitation.",
            f"- recommend entering LLM line-card prototype: {'conditional' if violation_count == 0 else 'no'}",
            "- manual sample review is recommended before LLM/MCP rendering.",
            "- M1-M7 outputs were read only and not modified.",
            "- LLM was not called.",
        ]
    )
