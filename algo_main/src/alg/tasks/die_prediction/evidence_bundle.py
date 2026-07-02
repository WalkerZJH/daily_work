"""M7 structured evidence bundle prototype.

This module turns M5 status decisions plus M4 evidence into structured source
material for a later line-card generator. It does not train, score, rank, run
detectors, call an LLM, or implement M6 cache.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


INTERFACE_ONLY_DETECTORS = {
    "low_price_purchase_warning",
    "order_price_spread_warning",
    "rejection_response_warning",
    "delayed_response_warning",
    "low_delivery_rate_warning",
}
BUNDLE_COLUMNS = [
    "bundle_id",
    "candidate_id",
    "candidate_type",
    "manufacturer_code",
    "hospital_code",
    "drug_group",
    "drug_group_source",
    "cutoff_month",
    "horizon",
    "candidate_source",
    "final_candidate_status",
    "review_priority",
    "evidence_strength",
    "human_review_required",
    "auto_dispatch_allowed",
    "churn_probability_H",
    "churn_probability_interpretation",
    "repeat_probability_H",
    "repeat_probability_interpretation",
    "relative_value_at_risk_H",
    "relative_business_priority_score_H",
    "business_priority_interpretation",
    "survival_state",
    "survival_confidence",
    "survival_summary",
    "demand_shape_label",
    "demand_shape_route",
    "label_confidence_weight",
    "guardrail_summary",
    "detector_evidence_list",
    "detector_hit_count",
    "strong_detector_hit_count",
    "implemented_detector_hit_count",
    "interface_only_detector_count",
    "top_detector_reasons",
    "evidence_timeline_available",
    "evidence_timeline_reference",
    "evidence_persistence_summary",
    "allowed_claims",
    "forbidden_claims",
    "recommended_action_candidates",
    "model_limitations_note",
    "data_quality_note",
]


def load_csv_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def normalize_bool(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series.fillna(False)
    return series.fillna(False).astype(str).str.lower().isin(["true", "1", "yes", "y"])


def _clean_scalar(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value):
            return None
        return float(value)
    if pd.isna(value):
        return None
    return value


def to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _bundle_id(row: pd.Series) -> str:
    payload = "|".join(
        str(row.get(col, ""))
        for col in ["candidate_id", "candidate_type", "cutoff_month", "horizon", "final_candidate_status"]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def build_detector_evidence_list(detectors: pd.DataFrame) -> pd.DataFrame:
    """Aggregate implemented M4 detector hits to a JSON list per candidate."""
    if detectors is None or detectors.empty or "candidate_id" not in detectors.columns:
        return pd.DataFrame(columns=["candidate_id", "detector_evidence_list"])
    work = detectors.copy()
    work["candidate_id"] = work["candidate_id"].fillna("").astype(str)
    work = work[work["candidate_id"].ne("")]
    if work.empty:
        return pd.DataFrame(columns=["candidate_id", "detector_evidence_list"])
    hit = normalize_bool(work.get("hit_flag", pd.Series(False, index=work.index)))
    status = work.get("data_quality_status", pd.Series("", index=work.index)).fillna("").astype(str)
    detector_name = work.get("detector_name", pd.Series("", index=work.index)).fillna("").astype(str)
    valid = hit & status.ne("not_evaluable") & ~detector_name.isin(INTERFACE_ONLY_DETECTORS)
    work = work[valid].copy()
    if work.empty:
        return pd.DataFrame(columns=["candidate_id", "detector_evidence_list"])

    def pack(group: pd.DataFrame) -> str:
        rows = []
        for _, row in group.iterrows():
            rows.append(
                {
                    "detector_family": _clean_scalar(row.get("detector_family")),
                    "detector_name": _clean_scalar(row.get("detector_name")),
                    "severity": _clean_scalar(row.get("severity")),
                    "confidence": _clean_scalar(row.get("confidence")),
                    "reason_code": _clean_scalar(row.get("reason_code")),
                    "business_interpretation": _clean_scalar(row.get("business_interpretation")),
                    "evidence_fields": _clean_scalar(row.get("evidence_fields")),
                    "data_quality_status": _clean_scalar(row.get("data_quality_status")),
                }
            )
        return to_json(rows)

    return work.groupby("candidate_id", dropna=False).apply(pack, include_groups=False).reset_index(name="detector_evidence_list")


def survival_summary(row: pd.Series) -> str:
    parts = [
        f"survival_state={row.get('survival_state', '')}",
        f"overdue_ratio={row.get('overdue_ratio', '')}",
        f"survival_confidence={row.get('survival_confidence', '')}",
        f"history_sufficiency={row.get('history_sufficiency_flag', '')}",
    ]
    return ";".join(parts)


def guardrail_summary(row: pd.Series) -> str:
    shape = str(row.get("demand_shape_label", "") or "").lower()
    route = str(row.get("demand_shape_route", "") or "").lower()
    if shape == "smooth":
        return "standard interpretation allowed"
    if shape == "erratic":
        return "lower confidence; manual review preferred"
    if shape == "intermittent":
        return "long horizon preferred; short horizon caution"
    if shape == "lumpy" or route == "observation_only":
        return "observation only unless strong external evidence"
    return "demand-shape missing; manual review required"


def allowed_claims_for(row: pd.Series) -> list[str]:
    candidate_type = row.get("candidate_type")
    horizon = row.get("horizon")
    status = row.get("final_candidate_status")
    shape = row.get("demand_shape_label")
    claims = ["当前不允许自动派单。"]
    if candidate_type == "recurring_business_priority":
        claims += [
            "该对象进入业务优先级候选池。",
            f"该对象的 {horizon} recurring 流失概率为 {row.get('churn_probability_H')}.",
            "该对象的业务优先级较高。",
            f"该对象当前 survival_state 为 {row.get('survival_state')}.",
            "该对象的 survival_state 仅表示是否超出自身历史采购节奏。",
            "该对象需要人工复核。" if row.get("human_review_required") else "该对象当前不建议自动处置。",
        ]
        reasons = str(row.get("top_detector_reasons", "") or "")
        if "frequency" in reasons:
            claims.append("该对象近期采购频次相对历史水平下降。")
        if "quantity" in reasons:
            claims.append("该对象近期采购量相对历史水平变化。")
        if str(shape) in {"intermittent", "lumpy"}:
            claims.append("该对象属于低频或特殊需求形态，短窗口结果需谨慎。")
    elif candidate_type == "one_shot_attention":
        claims += [
            "该对象是 one-shot high value 关注对象。",
            f"该对象的 repeat_probability_{horizon} 表示首次采购后窗口内发生第二次采购的概率。",
            "该对象的 one-shot 分数不是 recurring churn probability。",
            "该对象建议人工判断是否促进第二次采购。",
        ]
    elif candidate_type == "demand_shape_observation":
        claims += [
            "该对象进入 demand-shape observation。",
            "该对象属于低频或特殊需求形态。",
            "当前只建议观察或人工复核。",
            "不建议仅凭短窗口未采购判断流失。",
        ]
    else:
        claims += [f"该对象状态为 {status}，需要先确认数据质量。"]
    return claims


def forbidden_claims_for(row: pd.Series) -> list[str]:
    claims = [
        "医院已经确定流失。",
        "医院一定不会再采购。",
        "医院主动弃用。",
        "竞品替代。",
        "政策落标。",
        "配送商责任。",
        "价格异常导致流失。",
        "低风险对象一定安全。",
        "高风险对象一定流失。",
        "auto dispatch allowed。",
        "LLM may change risk score。",
        "价格 detector 已确认异常。",
        "配送 detector 已确认异常。",
        "配送商责任已确认。",
    ]
    if row.get("candidate_type") == "one_shot_attention":
        claims += [
            "该 one-shot 的 churn_probability 是 xx。",
            "one_shot_non_repeat_risk_H 是 recurring churn probability。",
            "该 one-shot 已经流失。",
        ]
    return claims


def recommended_actions_for(row: pd.Series) -> list[str]:
    candidate_type = row.get("candidate_type")
    status = row.get("final_candidate_status")
    shape = str(row.get("demand_shape_label", "") or "").lower()
    if candidate_type == "one_shot_attention":
        return [
            "建议业务人员判断是否需要促进第二次采购。",
            "建议复核首次采购是否为试采。",
            "建议结合医院等级、地区和药品类别判断转化机会。",
            "不建议解释为 recurring 流失。",
        ]
    if candidate_type == "demand_shape_observation" or status == "observation_only" or shape in {"intermittent", "lumpy"}:
        return [
            "建议进入观察清单。",
            "建议优先查看更长窗口。",
            "不建议仅因 H3 未采购直接预警。",
            "建议等待更多采购周期或人工确认。",
        ]
    if status in {"priority_review", "manual_review"}:
        return [
            "建议人工核查近期采购频次下降原因。",
            "建议结合医院实际采购计划判断是否正常延迟。",
            "建议业务人员复核是否存在需求变化。",
            "若终端丢失证据为 medium，建议优先人工复核而非自动处置。",
        ]
    return [
        "建议补充数据或等待更多历史。",
        "建议人工确认数据质量。",
        "不建议自动处置。",
    ]


def limitations_note(strong_count: int = 0, p0_count: int = 0) -> str:
    notes = [
        "M6 evidence timeline not implemented",
        "price_warning detector interface-only",
        "delivery_response detector interface-only",
        "auto_dispatch_allowed false",
        "detector evidence is not probability",
        "one-shot repeat probability is not recurring churn probability",
        "LLM not involved in scoring or decision",
    ]
    if strong_count == 0 or p0_count == 0:
        notes.append("Current M5 decision is conservative: no P0 or strong evidence was generated in v1")
    return "; ".join(notes)


def build_structured_evidence_bundle(status: pd.DataFrame, detectors: pd.DataFrame | None = None) -> pd.DataFrame:
    if status is None or status.empty:
        return pd.DataFrame(columns=BUNDLE_COLUMNS)
    base = status.copy()
    detector_lists = build_detector_evidence_list(detectors if detectors is not None else pd.DataFrame())
    if not detector_lists.empty:
        base = base.merge(detector_lists, on="candidate_id", how="left", suffixes=("", "_from_m4"))
        source_col = "detector_evidence_list_from_m4" if "detector_evidence_list_from_m4" in base.columns else "detector_evidence_list"
        base["detector_evidence_list"] = base[source_col].fillna("[]")
        if source_col == "detector_evidence_list_from_m4":
            base = base.drop(columns=["detector_evidence_list_from_m4"])
    else:
        base["detector_evidence_list"] = "[]"

    strong_count = int(base.get("evidence_strength", pd.Series(dtype=str)).fillna("").eq("strong").sum())
    p0_count = int(base.get("review_priority", pd.Series(dtype=str)).fillna("").eq("P0").sum())
    base["candidate_source"] = base["candidate_type"].map(
        {
            "recurring_business_priority": "M1_recurring_business_priority_candidates",
            "one_shot_attention": "M2_one_shot_attention_candidates_enriched",
            "demand_shape_observation": "M1_M2_corrections_demand_shape_display_ready",
        }
    ).fillna("unknown")
    base["survival_summary"] = base.apply(survival_summary, axis=1)
    base["label_confidence_weight"] = np.where(
        base["candidate_type"].eq("recurring_business_priority"),
        np.where(base.get("history_sufficiency_flag", "").astype(str).eq("history_sufficient"), 1.0, 0.5),
        np.nan,
    )
    base["guardrail_summary"] = base.apply(guardrail_summary, axis=1)
    base["allowed_claims"] = base.apply(lambda row: to_json(allowed_claims_for(row)), axis=1)
    base["forbidden_claims"] = base.apply(lambda row: to_json(forbidden_claims_for(row)), axis=1)
    base["recommended_action_candidates"] = base.apply(lambda row: to_json(recommended_actions_for(row)), axis=1)
    base["model_limitations_note"] = limitations_note(strong_count=strong_count, p0_count=p0_count)
    base["auto_dispatch_allowed"] = False
    base["evidence_timeline_available"] = False
    base["evidence_timeline_reference"] = np.nan
    base["evidence_persistence_summary"] = "not_implemented_in_v1"
    base["bundle_id"] = base.apply(_bundle_id, axis=1)
    for col in BUNDLE_COLUMNS:
        if col not in base.columns:
            base[col] = np.nan
    return base[BUNDLE_COLUMNS]


def split_bundles(bundle: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if bundle.empty:
        empty = pd.DataFrame(columns=BUNDLE_COLUMNS)
        return empty, empty, empty
    return (
        bundle[bundle["candidate_type"].eq("recurring_business_priority")].copy(),
        bundle[bundle["candidate_type"].eq("one_shot_attention")].copy(),
        bundle[bundle["candidate_type"].eq("demand_shape_observation")].copy(),
    )


def claims_table(bundle: pd.DataFrame, claim_col: str, output_col: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if bundle.empty:
        return pd.DataFrame(columns=["bundle_id", "candidate_id", "candidate_type", output_col])
    for _, row in bundle.iterrows():
        try:
            values = json.loads(row.get(claim_col, "[]"))
        except json.JSONDecodeError:
            values = []
        for value in values:
            rows.append(
                {
                    "bundle_id": row.get("bundle_id"),
                    "candidate_id": row.get("candidate_id"),
                    "candidate_type": row.get("candidate_type"),
                    output_col: value,
                }
            )
    return pd.DataFrame(rows, columns=["bundle_id", "candidate_id", "candidate_type", output_col])


def completeness_report(bundle: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "candidate_type",
        "row_count",
        "has_probability_rate",
        "has_business_priority_rate",
        "has_survival_rate",
        "has_detector_evidence_rate",
        "has_allowed_claims_rate",
        "has_forbidden_claims_rate",
        "has_recommended_actions_rate",
        "has_data_quality_note_rate",
        "auto_dispatch_false_rate",
    ]
    if bundle.empty:
        return pd.DataFrame(columns=cols)
    rows = []
    for candidate_type, group in bundle.groupby("candidate_type", dropna=False):
        has_probability = group["churn_probability_H"].notna() | group["repeat_probability_H"].notna()
        detector_nonempty = group["detector_evidence_list"].fillna("[]").astype(str).ne("[]")
        rows.append(
            {
                "candidate_type": candidate_type,
                "row_count": len(group),
                "has_probability_rate": float(has_probability.mean()),
                "has_business_priority_rate": float(group["relative_business_priority_score_H"].notna().mean()),
                "has_survival_rate": float(group["survival_state"].fillna("").astype(str).ne("").mean()),
                "has_detector_evidence_rate": float(detector_nonempty.mean()),
                "has_allowed_claims_rate": float(group["allowed_claims"].fillna("").astype(str).ne("").mean()),
                "has_forbidden_claims_rate": float(group["forbidden_claims"].fillna("").astype(str).ne("").mean()),
                "has_recommended_actions_rate": float(
                    group["recommended_action_candidates"].fillna("").astype(str).ne("").mean()
                ),
                "has_data_quality_note_rate": float(group["data_quality_note"].fillna("").astype(str).ne("").mean()),
                "auto_dispatch_false_rate": float((~normalize_bool(group["auto_dispatch_allowed"])).mean()),
            }
        )
    return pd.DataFrame(rows, columns=cols)


def distribution_table(df: pd.DataFrame, column: str) -> pd.DataFrame:
    if df is None or df.empty or column not in df.columns:
        return pd.DataFrame(columns=[column, "row_count", "share"])
    out = df[column].fillna("__MISSING__").astype(str).value_counts().reset_index()
    out.columns = [column, "row_count"]
    out["share"] = out["row_count"] / max(len(df), 1)
    return out


def semantics_audit_text() -> str:
    return "\n".join(
        [
            "# Evidence Bundle Semantics Audit",
            "",
            "- M7 does not train models.",
            "- M7 does not re-rank candidates.",
            "- M7 does not recalculate probability.",
            "- M7 does not run detectors.",
            "- M7 does not implement M6 cache.",
            "- M7 does not call an LLM.",
            "- M7 does not generate final line cards.",
            "- recurring `churn_probability_H` and one-shot `repeat_probability_H` have different semantics.",
            "- `business_priority_score_H` is not probability.",
            "- detector severity/confidence are not probability.",
            "- `allowed_claims` and `forbidden_claims` are generated for later controlled rendering.",
            "- `auto_dispatch_allowed` is false for every row.",
        ]
    )


def data_quality_text(bundle: pd.DataFrame, status: pd.DataFrame, detectors: pd.DataFrame) -> str:
    return "\n".join(
        [
            "# Evidence Bundle Data Quality Report",
            "",
            f"- status decision rows loaded: {len(status)}",
            f"- detector evidence rows loaded: {len(detectors)}",
            f"- structured evidence bundle rows: {len(bundle)}",
            f"- rows with detector evidence list: {int(bundle['detector_evidence_list'].fillna('[]').astype(str).ne('[]').sum()) if not bundle.empty else 0}",
            "",
            "Raw demand_shape_observation_candidates.csv is intentionally not loaded as M7 input.",
        ]
    )


def summary_text(bundle: pd.DataFrame, completeness: pd.DataFrame) -> str:
    status_dist = distribution_table(bundle, "final_candidate_status")
    priority_dist = distribution_table(bundle, "review_priority")
    strength_dist = distribution_table(bundle, "evidence_strength")
    allowed_rate = float(bundle["allowed_claims"].fillna("").astype(str).ne("").mean()) if not bundle.empty else 0.0
    forbidden_rate = float(bundle["forbidden_claims"].fillna("").astype(str).ne("").mean()) if not bundle.empty else 0.0
    action_rate = float(bundle["recommended_action_candidates"].fillna("").astype(str).ne("").mean()) if not bundle.empty else 0.0
    return "\n".join(
        [
            "# Evidence Bundle v1 Summary",
            "",
            f"- structured_evidence_bundle.csv generated: {not bundle.empty}",
            f"- total rows: {len(bundle)}",
            f"- allowed_claims coverage: {allowed_rate:.4f}",
            f"- forbidden_claims coverage: {forbidden_rate:.4f}",
            f"- recommended_action_candidates coverage: {action_rate:.4f}",
            f"- auto_dispatch_allowed all false: {bool((~normalize_bool(bundle['auto_dispatch_allowed'])).all()) if not bundle.empty else True}",
            f"- evidence_timeline_available all false: {bool((~normalize_bool(bundle['evidence_timeline_available'])).all()) if not bundle.empty else True}",
            "- LLM was not called.",
            "- Final line cards were not generated.",
            "- M6 cache was not implemented.",
            "- Current M5 decision is conservative: no P0 or strong evidence was generated in v1. Bundles should be used for manual review material, not automatic dispatch.",
            "- Next stage can conditionally enter LLM/MCP line-card generation after manual sample review.",
            "",
            "## candidate_type",
            distribution_table(bundle, "candidate_type").to_markdown(index=False),
            "",
            "## final_candidate_status",
            status_dist.to_markdown(index=False),
            "",
            "## review_priority",
            priority_dist.to_markdown(index=False),
            "",
            "## evidence_strength",
            strength_dist.to_markdown(index=False),
            "",
            "## completeness",
            completeness.to_markdown(index=False),
        ]
    )


def next_stage_text(bundle: pd.DataFrame) -> str:
    allowed = float(bundle["allowed_claims"].fillna("").astype(str).ne("").mean()) if not bundle.empty else 0.0
    forbidden = float(bundle["forbidden_claims"].fillna("").astype(str).ne("").mean()) if not bundle.empty else 0.0
    auto_false = bool((~normalize_bool(bundle["auto_dispatch_allowed"])).all()) if not bundle.empty else True
    proceed = "conditional" if allowed >= 0.99 and forbidden >= 0.99 and auto_false and not bundle.empty else "no"
    return "\n".join(
        [
            "# Evidence Bundle Next Stage Readiness",
            "",
            f"proceed_to_llm_line_card = {proceed}",
            "manual_review_required_before_llm = yes",
            "m6_cache_implemented = false",
            "",
            "condition: LLM may only consume allowed_claims and recommended_action_candidates. LLM must not change score, status, detector evidence, or probability.",
        ]
    )
