"""Deterministic business-copy renderer for frontend-safe risk cards."""

from __future__ import annotations

from typing import Any

import pandas as pd


FORBIDDEN_CLAIMS = [
    "医院已经确定流失",
    "医院一定不会再采购",
    "医院主动弃用",
    "竞品替代已发生",
    "政策落标已发生",
    "配送商责任已确认",
    "价格异常导致流失",
    "低风险对象一定安全",
    "高风险对象一定流失",
]

INTERNAL_TERMS = ["FDR", "MK", "Theil-Sen", "CUSUM", "SHAP", "AUC", "ECE", "XGBoost", "LightGBM", "CatBoost"]


class BusinessCopyRenderer:
    """Template renderer that converts model evidence to safe business language."""

    def render_for_row(self, row: pd.Series | dict[str, Any]) -> dict[str, Any]:
        data = dict(row)
        candidate_type = str(data.get("candidate_type", ""))
        status = str(data.get("final_candidate_status", ""))
        detector_hits = int(float(data.get("detector_hit_count", 0) or 0))
        survival_state = str(data.get("survival_state", ""))

        if candidate_type == "one_shot":
            title = "新进终端关注"
            summary = "该对象属于新近采购关系，仅建议关注，不展示 recurring 流失概率。"
            action = "纳入新进终端关注清单，等待后续采购记录确认。"
            caveat = "one-shot 对象不等同于 recurring churn。"
        elif candidate_type == "demand_shape_observation" or status in {"observation_only", "low_confidence_watch", "not_actionable"}:
            title = "观察对象"
            summary = "当前历史记录或采购形态不足以支持强预警，建议继续观察。"
            action = "纳入观察清单，等待更多采购信号确认。"
            caveat = "观察对象不代表高风险。"
        elif status == "priority_review":
            title = "优先复核线索"
            summary = "该医院-药品关系出现需优先复核的采购节奏信号。"
            action = "建议业务人员优先复核近期采购节奏，并确认是否存在正常延迟或需求变化。"
            caveat = "该结论是风险复核线索，不是最终业务判断。"
        elif status == "manual_review" or detector_hits > 0:
            title = "人工复核线索"
            summary = "近期采购行为出现变化，建议人工确认是否属于正常波动。"
            action = "建议业务人员结合实际采购记录复核。"
            caveat = "证据强度不是概率。"
        else:
            title = "月度复核对象"
            summary = "该对象进入月度工作清单，建议结合业务上下文复核。"
            action = "纳入月度复核清单。"
            caveat = "仅供内部分析师与业务复核使用。"

        evidence = self.render_evidence_text_list(survival_state, data.get("detector_evidence_list", ""))
        one_line = summary
        manager_hint = action
        payload = {
            "risk_card_title": title,
            "risk_card_summary": summary,
            "evidence_text_list": evidence,
            "suggested_action_text": action,
            "caveat_text": caveat,
            "one_line_diagnosis": one_line,
            "manager_action_hint": manager_hint,
        }
        self.assert_safe(payload)
        return payload

    def render_evidence_text_list(self, survival_state: str, detector_evidence_list: Any) -> list[str]:
        texts: list[str] = []
        if "overdue" in survival_state or "interval" in survival_state:
            texts.append("距离上次采购时间或采购间隔偏离历史常规节奏。")
        raw = str(detector_evidence_list or "")
        if "purchase_frequency_fluctuation_warning" in raw:
            texts.append("近期采购频次低于过往水平。")
        if "purchase_interval_overdue_warning" in raw:
            texts.append("当前采购节奏需要业务人员复核。")
        if "terminal_loss_warning" in raw:
            texts.append("近期未观察到采购记录，需确认是否仍在正常采购周期内。")
        if not texts:
            texts.append("当前仅形成月度复核线索，需结合业务上下文判断。")
        return texts

    def detector_display_text(self, detector_name: str) -> str:
        return {
            "terminal_loss_warning": "近期未观察到采购记录，需确认是否仍在正常采购周期内。",
            "purchase_interval_overdue_warning": "采购间隔偏离历史常规节奏，建议人工复核。",
            "purchase_frequency_fluctuation_warning": "近期采购频次低于过往水平，建议继续跟踪。",
            "purchase_quantity_fluctuation_warning": "近期采购数量变化较大，需结合业务背景复核。",
            "new_terminal_detection": "新进终端事实记录，仅作为关注对象。",
        }.get(str(detector_name), "证据信号暂不对业务侧展示。")

    def assert_safe(self, payload: dict[str, Any]) -> None:
        text = str(payload)
        bad = [term for term in FORBIDDEN_CLAIMS + INTERNAL_TERMS if term in text]
        if bad:
            raise ValueError(f"unsafe business copy terms: {bad}")


def contains_forbidden_claims(text: str) -> bool:
    return any(term in text for term in FORBIDDEN_CLAIMS + INTERNAL_TERMS)
