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
    "配送商导致流失",
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
            summary = "该医院-药品关系属于新进终端关注对象，建议判断是否有机会促进第二次采购。"
            action = "纳入新进终端关注清单，不展示 recurring churn probability。"
            caveat = "one-shot 对象不等同于 recurring churn。"
        elif candidate_type == "demand_shape_observation" or status in {"observation_only", "low_confidence_watch", "not_actionable"}:
            title = "观察对象"
            summary = "当前历史记录或采购形态不足以支持强预警，建议继续观察。"
            action = "纳入观察清单，等待更多采购信号确认。"
            caveat = "观察对象不代表高风险。"
        elif status == "priority_review":
            title = "优先复核线索"
            summary = "该医院-药品关系进入重点风险复核清单，近期采购状态相对历史节奏出现异常。"
            action = "建议业务人员优先复核采购计划、院内需求和近期订单状态。"
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
        payload = {
            "risk_card_title": title,
            "risk_card_summary": summary,
            "evidence_text_list": evidence,
            "suggested_action_text": action,
            "caveat_text": caveat,
            "one_line_diagnosis": summary,
            "manager_action_hint": action,
        }
        self.assert_safe(payload)
        return payload

    def render_evidence_text_list(self, survival_state: str, detector_evidence_list: Any) -> list[str]:
        texts: list[str] = []
        if "overdue" in survival_state or "interval" in survival_state:
            texts.append("距离上次采购时间或采购间隔偏离历史常规节奏。")
        raw = str(detector_evidence_list or "")
        if "purchase_frequency_fluctuation_warning" in raw:
            texts.append("近期采购频次低于历史水平。")
        if "purchase_interval_overdue_warning" in raw:
            texts.append("当前采购节奏需要业务人员复核。")
        if "terminal_loss_warning" in raw:
            texts.append("近期未观察到采购记录，需要确认是否仍在正常采购周期内。")
        if not texts:
            texts.append("当前仅形成月度复核线索，需结合业务上下文判断。")
        return texts

    def detector_display_text(self, detector_name: str) -> str:
        return self.render_detector_evidence(detector_name)["evidence_text"]

    def render_detector_evidence(self, detector_name: str, *, gate_status: str = "enabled") -> dict[str, str]:
        """Render one detector as frontend-safe business copy."""
        if gate_status in {"disabled", "internal_only"}:
            disabled = self.render_disabled_detector_note(detector_name)
            payload = {
                "card_title": "证据未启用",
                "card_summary": disabled["disabled_reason_text"],
                "evidence_text": disabled["disabled_reason_text"],
                "suggested_action": "当前不作为业务风险证据展示。",
                "caveat_text": disabled["disabled_reason_text"],
                "visibility_level": "internal_only",
            }
            self.assert_safe(payload)
            return payload

        mapping = {
            "terminal_loss_warning": {
                "card_title": "重点风险复核",
                "card_summary": "该医院-药品关系进入重点风险复核清单，近期采购状态相对历史节奏出现异常。",
                "evidence_text": "近期采购状态相对历史节奏出现异常，建议业务人员优先复核采购计划和实际需求。",
                "suggested_action": "优先复核采购计划、院内需求和近期订单状态。",
            },
            "purchase_interval_overdue_warning": {
                "card_title": "采购节奏超期",
                "card_summary": "距离上次采购时间已超过其历史常规采购节奏。",
                "evidence_text": "距离上次采购时间已超过其历史常规采购节奏，建议确认是否为正常采购延迟。",
                "suggested_action": "确认是否存在正常采购延迟、短期库存或需求变化。",
            },
            "purchase_frequency_fluctuation_warning": {
                "card_title": "采购频次下降",
                "card_summary": "近期采购频次低于历史水平。",
                "evidence_text": "近期采购频次低于历史水平，建议复核是否存在需求变化或采购计划调整。",
                "suggested_action": "复核近期采购计划、院内需求和下次采购预期。",
            },
            "purchase_quantity_fluctuation_warning": {
                "card_title": "采购数量变化",
                "card_summary": "近期采购数量较历史水平下降。",
                "evidence_text": "近期采购数量较历史水平下降，仅作为辅助证据，需要业务复核。",
                "suggested_action": "结合采购频次和业务背景人工确认。",
            },
            "new_terminal_detection": {
                "card_title": "新进终端关注",
                "card_summary": "该医院-药品关系属于新进终端关注对象。",
                "evidence_text": "该医院-药品关系属于新进终端关注对象，建议判断是否有机会促进第二次采购。",
                "suggested_action": "判断是否需要促进第二次采购，不解释为 recurring 流失。",
            },
            "low_delivery_rate_warning": {
                "card_title": "履约数量辅助观察",
                "card_summary": "履约数量侧信号仅作辅助观察。",
                "evidence_text": "当前仅可作为履约数量侧辅助观察，不足以判断配送责任。",
                "suggested_action": "仅在业务复核时参考，不作为归因结论。",
            },
        }
        payload = mapping.get(
            str(detector_name),
            {
                "card_title": "业务证据信号",
                "card_summary": "当前证据仅作为业务复核辅助。",
                "evidence_text": "当前证据仅作为业务复核辅助，不形成确定性结论。",
                "suggested_action": "结合业务上下文人工复核。",
            },
        )
        payload = {
            **payload,
            "caveat_text": "该证据用于人工复核，不是概率，也不是最终业务结论。",
            "visibility_level": "business_visible" if gate_status == "enabled" else "manager_visible",
        }
        self.assert_safe(payload)
        return payload

    def render_disabled_detector_note(self, detector_name: str) -> dict[str, str]:
        notes = {
            "low_price_purchase_warning": "当前价格证据未启用，原因是价格口径或可比价映射不足。",
            "order_price_spread_warning": "当前价格证据未启用，原因是价格口径或可比价映射不足。",
            "delayed_response_warning": "当前配送时效证据未启用，原因是配送/到货时间字段缺失率较高或回填不稳定。",
            "rejection_response_warning": "当前响应类证据未启用，原因是响应字段可靠性不足。",
            "low_delivery_rate_warning": "当前履约数量侧证据默认不启用强结论，需人工复核数据口径。",
            "purchase_amount_trend_warning": "当前金额趋势证据仅保留内部接口，原因是金额字段为脱敏或相对口径。",
            "sku_narrowing_warning": "当前 SKU 收窄证据未启用，原因是产品线或组合映射不足。",
            "wallet_share_decline_warning": "当前份额变化证据未启用，原因是产品线映射和完整上下文不足。",
        }
        text = notes.get(str(detector_name), "当前 detector 未达到业务展示条件。")
        payload = {"detector_name": str(detector_name), "disabled_reason_text": text}
        self.assert_safe(payload)
        return payload

    def assert_safe(self, payload: dict[str, Any]) -> None:
        text = str(payload)
        bad = [term for term in FORBIDDEN_CLAIMS + INTERNAL_TERMS if term in text]
        if bad:
            raise ValueError(f"unsafe business copy terms: {bad}")


def contains_forbidden_claims(text: str) -> bool:
    return any(term in text for term in FORBIDDEN_CLAIMS + INTERNAL_TERMS)

