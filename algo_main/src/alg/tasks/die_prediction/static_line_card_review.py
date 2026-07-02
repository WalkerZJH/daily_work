"""Static line-card style review renderer for structured evidence bundles.

This prototype renders fixed-template Markdown/HTML samples for manual review.
It does not call an LLM, generate final line cards, change scores, or modify
M1-M7 outputs.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


STATUS_LIMITS = {
    "priority_review": 10,
    "manual_review": 10,
    "one_shot_attention": 10,
    "observation_only": 10,
    "low_confidence_watch": 5,
}
FORBIDDEN_KEY_TERMS = [
    "医院已经流失",
    "医院已经确定流失",
    "确定不采购",
    "医院一定不会再采购",
    "竞品替代",
    "政策落标",
    "价格 detector 已确认异常",
    "配送 detector 已确认异常",
]
INTERFACE_ONLY_DETECTOR_NAMES = {
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


def normalize_bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def choose_card_samples(sample_or_bundle: pd.DataFrame) -> pd.DataFrame:
    """Choose display samples from review sample or full bundle."""
    if sample_or_bundle is None or sample_or_bundle.empty:
        return pd.DataFrame(columns=sample_or_bundle.columns if sample_or_bundle is not None else [])
    work = sample_or_bundle.copy()
    business = pd.to_numeric(work.get("relative_business_priority_score_H", pd.Series(np.nan, index=work.index)), errors="coerce")
    churn = pd.to_numeric(work.get("churn_probability_H", pd.Series(np.nan, index=work.index)), errors="coerce")
    repeat = pd.to_numeric(work.get("repeat_probability_H", pd.Series(np.nan, index=work.index)), errors="coerce")
    ctype = work.get("candidate_type", pd.Series("", index=work.index)).fillna("").astype(str)
    work["_sort_score"] = np.where(ctype.eq("one_shot_attention"), repeat.fillna(0), business.fillna(0) + churn.fillna(0))
    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    work["_priority_order"] = work.get("review_priority", pd.Series("", index=work.index)).map(priority_order).fillna(99)
    rows = []
    for status, limit in STATUS_LIMITS.items():
        part = work[work["final_candidate_status"].eq(status)].copy()
        if part.empty:
            continue
        part = part.sort_values(["_priority_order", "_sort_score", "candidate_id"], ascending=[True, False, True]).head(limit)
        rows.append(part)
    if not rows:
        return pd.DataFrame(columns=sample_or_bundle.columns)
    out = pd.concat(rows, ignore_index=True).drop_duplicates("bundle_id" if "bundle_id" in work.columns else "candidate_id")
    out = out.drop(columns=[c for c in ["_sort_score", "_priority_order"] if c in out.columns]).reset_index(drop=True)
    out["card_id"] = [f"static_card_{i:03d}" for i in range(1, len(out) + 1)]
    return out


def _fmt(value: Any) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "not_applicable"
    text = str(value)
    return text if text else "not_applicable"


def _bullet_list(values: list[Any], limit: int | None = None) -> list[str]:
    selected = values[:limit] if limit is not None else values
    return [f"- {_fmt(v)}" for v in selected] if selected else ["- not_available"]


def detector_lines(row: pd.Series) -> list[str]:
    evidence = parse_json_list(row.get("detector_evidence_list"))[:3]
    if not evidence:
        return ["当前没有可用的强 detector 证据，仅作为观察或人工复核材料。"]
    lines: list[str] = []
    for item in evidence:
        if not isinstance(item, dict):
            continue
        if item.get("detector_name") in INTERFACE_ONLY_DETECTOR_NAMES:
            continue
        lines.extend(
            [
                "- detector_family: " + _fmt(item.get("detector_family")),
                "- detector_name: " + _fmt(item.get("detector_name")),
                "- severity: " + _fmt(item.get("severity")),
                "- confidence: " + _fmt(item.get("confidence")),
                "- reason_code: " + _fmt(item.get("reason_code")),
                "- business_interpretation: " + _fmt(item.get("business_interpretation")),
                "",
            ]
        )
    return lines or ["当前没有可用的强 detector 证据，仅作为观察或人工复核材料。"]


def render_card_markdown(row: pd.Series) -> str:
    status = _fmt(row.get("final_candidate_status"))
    candidate_type = _fmt(row.get("candidate_type"))
    is_one_shot = candidate_type == "one_shot_attention"
    allowed = parse_json_list(row.get("allowed_claims"))[:6]
    forbidden = [
        "不得说医院已经确定流失。",
        "不得说医院一定不会再采购。",
        "不得说竞品替代。",
        "不得说政策落标。",
        "one-shot 不得说 churn_probability。",
    ]
    existing_forbidden = [str(x) for x in parse_json_list(row.get("forbidden_claims"))]
    for item in existing_forbidden[:5]:
        if item not in forbidden:
            forbidden.append(item)
    actions = parse_json_list(row.get("recommended_action_candidates"))
    lines = [
        f"## [{status}] 医院-药品风险线索",
        "",
        f"<!-- card_id: {_fmt(row.get('card_id'))}; template_rendered_not_llm -->",
        "",
        "### 1. 基本信息",
        "",
        f"- candidate_id: {_fmt(row.get('candidate_id'))}",
        f"- candidate_type: {candidate_type}",
        f"- manufacturer_code: {_fmt(row.get('manufacturer_code'))}",
        f"- hospital_code: {_fmt(row.get('hospital_code'))}",
        f"- drug_group: {_fmt(row.get('drug_group'))}",
        f"- cutoff_month: {_fmt(row.get('cutoff_month'))}",
        f"- horizon: {_fmt(row.get('horizon'))}",
        "",
        "### 2. 当前处理状态",
        "",
        f"- final_candidate_status: {status}",
        f"- review_priority: {_fmt(row.get('review_priority'))}",
        f"- evidence_strength: {_fmt(row.get('evidence_strength'))}",
        f"- human_review_required: {_fmt(row.get('human_review_required'))}",
        "- auto_dispatch_allowed: false",
        "",
        "### 3. 分数与语义",
        "",
    ]
    if is_one_shot:
        lines.extend(
            [
                f"- repeat_probability_H: {_fmt(row.get('repeat_probability_H'))}",
                f"- repeat_probability_interpretation: {_fmt(row.get('repeat_probability_interpretation'))}",
                "- selected_attention_score: not_available_in_structured_bundle_v1",
                "- selected_attention_policy: not_available_in_structured_bundle_v1",
                "- 注意：该分数不是 recurring churn probability。",
            ]
        )
    else:
        lines.extend(
            [
                f"- churn_probability_H: {_fmt(row.get('churn_probability_H'))}",
                f"- probability_interpretation: {_fmt(row.get('churn_probability_interpretation'))}",
                f"- relative_value_at_risk_H: {_fmt(row.get('relative_value_at_risk_H'))}",
                f"- relative_business_priority_score_H: {_fmt(row.get('relative_business_priority_score_H'))}",
                f"- business_priority_interpretation: {_fmt(row.get('business_priority_interpretation'))}",
                "- repeat_probability_H: not_applicable",
            ]
        )
    lines.extend(["", "### 4. 采购节奏 / Survival 信息", ""])
    if is_one_shot:
        lines.append("该对象为 one-shot 专项关注对象，不适用 recurring survival-lite 解释。")
    else:
        lines.extend(
            [
                f"- survival_state: {_fmt(row.get('survival_state'))}",
                f"- survival_confidence: {_fmt(row.get('survival_confidence'))}",
                f"- survival_summary: {_fmt(row.get('survival_summary'))}",
                f"- demand_shape_label: {_fmt(row.get('demand_shape_label'))}",
                f"- demand_shape_route: {_fmt(row.get('demand_shape_route'))}",
                f"- guardrail_summary: {_fmt(row.get('guardrail_summary'))}",
            ]
        )
    lines.extend(["", "### 5. Detector 证据", ""])
    lines.extend(detector_lines(row))
    lines.extend(["", "### 6. 允许表达的事实", ""])
    lines.extend(_bullet_list([str(x) for x in allowed], limit=6))
    lines.extend(["", "### 7. 禁止表达的结论", ""])
    lines.extend(_bullet_list(forbidden, limit=8))
    lines.extend(["", "### 8. 建议动作候选", ""])
    lines.extend(_bullet_list([str(x) for x in actions]))
    lines.extend(
        [
            "",
            "注意：这不是自动派单，仅供人工复核参考。",
            "",
            "### 9. 人工复核问题",
            "",
            "1. 该对象为什么进入当前状态？",
            "2. 当前证据是否足够支持人工跟进？",
            "3. 是否存在低频采购导致的误报风险？",
            "4. 是否需要业务人员补充现场信息？",
            "5. 该卡片是否适合后续交给 LLM 改写为自然语言线索卡？",
            "",
        ]
    )
    return "\n".join(lines)


def render_cards_markdown(samples: pd.DataFrame) -> str:
    lines = [
        "# Alive Prediction Static Line Card Samples v1",
        "",
        "本文件由固定模板渲染，不是 LLM 文案，不是正式线索卡，不允许自动派单。",
        "",
    ]
    for _, row in samples.iterrows():
        lines.append(render_card_markdown(row))
    return "\n".join(lines)


def render_cards_html(samples: pd.DataFrame) -> str:
    cards = []
    for _, row in samples.iterrows():
        md = render_card_markdown(row)
        cards.append(f"<article class='card'><pre>{html.escape(md)}</pre></article>")
    return "\n".join(
        [
            "<!doctype html>",
            "<html><head><meta charset='utf-8'><title>Alive Prediction Static Line Cards v1</title>",
            "<style>body{font-family:Arial,sans-serif;margin:24px;background:#f7f7f7}.card{background:white;border:1px solid #ddd;border-radius:6px;padding:16px;margin:16px 0}pre{white-space:pre-wrap;font-family:Consolas,monospace;font-size:13px}</style>",
            "</head><body>",
            "<h1>Alive Prediction Static Line Card Samples v1</h1>",
            "<p>Fixed-template static review output. No LLM was called.</p>",
            *cards,
            "</body></html>",
        ]
    )


def sample_index(samples: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "card_id",
        "bundle_id",
        "candidate_id",
        "candidate_type",
        "final_candidate_status",
        "review_priority",
        "evidence_strength",
        "manufacturer_code",
        "hospital_code",
        "drug_group",
        "cutoff_month",
        "horizon",
    ]
    for col in cols:
        if col not in samples.columns:
            samples[col] = np.nan
    return samples[cols].copy()


def _section_without_forbidden(md: str) -> str:
    marker_start = "### 7. 禁止表达的结论"
    marker_end = "### 8. 建议动作候选"
    if marker_start not in md or marker_end not in md:
        return md
    before, rest = md.split(marker_start, 1)
    _, after = rest.split(marker_end, 1)
    return before + marker_end + after


def claim_boundary_audit(samples: pd.DataFrame, card_markdowns: dict[str, str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in samples.iterrows():
        card_id = row.get("card_id")
        text = card_markdowns.get(card_id, "")
        outside_forbidden = _section_without_forbidden(text)
        violations: list[tuple[str, str, str]] = []
        for term in FORBIDDEN_KEY_TERMS:
            if term in outside_forbidden:
                violations.append(("forbidden_phrase_outside_forbidden_section", term, "Move forbidden wording into forbidden section only."))
        if row.get("candidate_type") == "one_shot_attention":
            section3 = text.split("### 4. 采购节奏 / Survival 信息", 1)[0]
            if "churn_probability_H:" in section3 or "churn_probability:" in section3:
                violations.append(("one_shot_churn_probability_displayed", "churn_probability", "Remove recurring churn probability from one-shot card."))
            if "不是 recurring churn probability" not in text:
                violations.append(("one_shot_non_recurring_note_missing", "", "Add one-shot non-recurring-churn note."))
        detector_text = "\n".join(text.split("### 5. Detector 证据", 1)[1:]).split("### 6. 允许表达的事实", 1)[0]
        if any(name in detector_text for name in INTERFACE_ONLY_DETECTOR_NAMES):
            violations.append(("interface_only_detector_rendered_as_hit", "", "Do not render price/delivery interface-only detectors as evidence."))
        if "auto_dispatch_allowed: true" in text.lower():
            violations.append(("auto_dispatch_allowed_true", "", "Render auto_dispatch_allowed as false."))
        if "auto_dispatch_allowed: false" not in text:
            violations.append(("auto_dispatch_false_missing", "", "Render auto_dispatch_allowed false."))
        if not violations:
            rows.append(
                {
                    "card_id": card_id,
                    "candidate_id": row.get("candidate_id"),
                    "candidate_type": row.get("candidate_type"),
                    "claim_boundary_pass": True,
                    "violation_type": "",
                    "violation_detail": "",
                    "recommended_fix": "",
                }
            )
        else:
            for violation_type, detail, fix in violations:
                rows.append(
                    {
                        "card_id": card_id,
                        "candidate_id": row.get("candidate_id"),
                        "candidate_type": row.get("candidate_type"),
                        "claim_boundary_pass": False,
                        "violation_type": violation_type,
                        "violation_detail": detail,
                        "recommended_fix": fix,
                    }
                )
    return pd.DataFrame(rows)


def field_completeness(samples: pd.DataFrame, card_markdowns: dict[str, str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in samples.iterrows():
        text = card_markdowns.get(row.get("card_id"), "")
        ctype = row.get("candidate_type")
        has_core_identity = all(_fmt(row.get(c)) != "not_applicable" for c in ["candidate_id", "manufacturer_code", "hospital_code", "drug_group"])
        has_status = all(_fmt(row.get(c)) != "not_applicable" for c in ["final_candidate_status", "review_priority", "evidence_strength"])
        if ctype == "one_shot_attention":
            has_score = _fmt(row.get("repeat_probability_H")) != "not_applicable" and "不是 recurring churn probability" in text
            has_survival = "不适用 recurring survival-lite" in text
        else:
            has_score = _fmt(row.get("churn_probability_H")) != "not_applicable" and _fmt(row.get("relative_business_priority_score_H")) != "not_applicable"
            has_survival = _fmt(row.get("survival_summary")) != "not_applicable" or "not_applicable" in text
        has_detector = "### 5. Detector 证据" in text and ("detector_name:" in text or "当前没有可用的强 detector 证据" in text)
        has_allowed = "### 6. 允许表达的事实" in text
        has_forbidden = "### 7. 禁止表达的结论" in text
        has_actions = "### 8. 建议动作候选" in text
        has_questions = "### 9. 人工复核问题" in text
        complete = all([has_core_identity, has_status, has_score, has_survival, has_detector, has_allowed, has_forbidden, has_actions, has_questions])
        rows.append(
            {
                "card_id": row.get("card_id"),
                "candidate_id": row.get("candidate_id"),
                "candidate_type": ctype,
                "final_candidate_status": row.get("final_candidate_status"),
                "review_priority": row.get("review_priority"),
                "has_core_identity": has_core_identity,
                "has_status": has_status,
                "has_score_semantics": has_score,
                "has_survival_or_not_applicable": has_survival,
                "has_detector_or_explanation": has_detector,
                "has_allowed_claims": has_allowed,
                "has_forbidden_claims": has_forbidden,
                "has_recommended_actions": has_actions,
                "has_manual_review_questions": has_questions,
                "card_complete": complete,
            }
        )
    return pd.DataFrame(rows)


def manual_review_checklist_text() -> str:
    return "\n".join(
        [
            "# Static Line Card Manual Review Checklist",
            "",
            "1. 这张卡能否解释“为什么出现”；",
            "2. 这张卡是否区分概率、业务优先级、证据；",
            "3. 这张卡是否避免无依据因果；",
            "4. one-shot 是否避免被理解为流失；",
            "5. low_confidence / observation 是否没有被强预警；",
            "6. 当前 P0=0 / strong=0 是否会影响首页展示；",
            "7. VP 每日屏是否需要只展示 priority_review + top manual_review；",
            "8. 是否需要先人工确认 20-50 条样例再进入 LLM。",
        ]
    )


def llm_readiness_note(boundary: pd.DataFrame, completeness: pd.DataFrame) -> str:
    pass_rate = float(boundary["claim_boundary_pass"].mean()) if not boundary.empty else 0.0
    complete_rate = float(completeness["card_complete"].mean()) if not completeness.empty else 0.0
    violations = int((~boundary["claim_boundary_pass"]).sum()) if not boundary.empty else 0
    proceed = "conditional" if pass_rate == 1.0 and complete_rate == 1.0 and violations == 0 else "no"
    return "\n".join(
        [
            "# Static Line Card LLM Readiness Note",
            "",
            f"proceed_to_llm_line_card = {proceed}",
            "manual_review_required_before_llm = yes",
            "",
            f"- claim_boundary_pass rate: {pass_rate:.4f}",
            f"- card_complete rate: {complete_rate:.4f}",
            f"- claim boundary violations: {violations}",
            "- condition: LLM 只能基于 allowed_claims、recommended_action_candidates 和 structured evidence 字段改写表达，不得改变 score、status、probability、priority、detector evidence。",
        ]
    )


def summary_text(samples: pd.DataFrame, completeness: pd.DataFrame, boundary: pd.DataFrame) -> str:
    status_counts = samples["final_candidate_status"].value_counts().to_dict() if not samples.empty else {}
    type_counts = samples["candidate_type"].value_counts().to_dict() if not samples.empty else {}
    complete_rate = float(completeness["card_complete"].mean()) if not completeness.empty else 0.0
    boundary_rate = float(boundary["claim_boundary_pass"].mean()) if not boundary.empty else 0.0
    one_shot_pollution = int(boundary["violation_type"].fillna("").astype(str).str.contains("one_shot", regex=False).sum()) if not boundary.empty else 0
    interface_misuse = int(boundary["violation_type"].fillna("").astype(str).str.contains("interface_only", regex=False).sum()) if not boundary.empty else 0
    auto_false = int(boundary["violation_type"].fillna("").eq("auto_dispatch_allowed_true").sum()) == 0
    proceed = "conditional" if complete_rate == 1.0 and boundary_rate == 1.0 else "no"
    return "\n".join(
        [
            "# Static Line Card Review Summary",
            "",
            "- Markdown samples generated: true",
            "- HTML samples generated: true",
            f"- sample rows: {len(samples)}",
            f"- samples by final_candidate_status: {status_counts}",
            f"- samples by candidate_type: {type_counts}",
            f"- card_complete rate: {complete_rate:.4f}",
            f"- claim_boundary_pass rate: {boundary_rate:.4f}",
            f"- one-shot churn semantic pollution violations: {one_shot_pollution}",
            f"- price/delivery interface-only misuse violations: {interface_misuse}",
            f"- auto_dispatch_allowed all false in cards: {auto_false}",
            "- P0=0 / strong=0 is explained as a conservative v1 limitation and should remain visible in later product material.",
            f"- proceed_to_llm_line_card: {proceed}",
            "- manual review still required before LLM.",
            "- LLM was not called.",
            "- Final line cards were not generated.",
        ]
    )
