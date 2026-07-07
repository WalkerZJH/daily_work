"""Build frontend page payloads from MVC result-batch tables."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json

import pandas as pd

from .business_copy_renderer import contains_forbidden_claims
from .transformers import json_clean


class PagePayloadBuilder:
    def build_all(self, tables: dict[str, pd.DataFrame], manifest: dict[str, Any]) -> dict[str, Any]:
        entities = tables["risk_entities"]
        cards = tables["risk_cards"]
        evidence = tables["risk_card_evidence"]
        report_month = manifest["report_month"]
        top = self._top_entities(entities, len(entities))
        payloads = {
            "index_payload": self.index_payload(report_month, top, entities, evidence),
            "clues_payload": self.clues_payload(top, entities),
            "watchlist_payload": self.watchlist_payload(entities),
            "dashboard_payload": self.dashboard_payload(report_month, entities),
            "backtest_payload": self.backtest_payload(),
            "verify_payload": self.verify_payload(),
            "distributor_payload": self.distributor_payload(),
            "order_detail_sample_payload": self.order_detail_payload(),
            "monthly_report_payload": self.monthly_report_payload(tables["daily_reports"], entities, cards),
            "clue_detail_samples": self.clue_detail_samples(top.head(20), cards, evidence),
        }
        self.assert_customer_safe(payloads)
        return payloads

    def index_payload(self, report_month: str, top: pd.DataFrame, entities: pd.DataFrame, evidence: pd.DataFrame) -> dict[str, Any]:
        return {
            "page_title": "VP 工作台",
            "report_month": report_month,
            "primary_horizon": "H12",
            "hero": {
                "risk_exposure_display": "相对潜在影响汇总",
                "red_count": int(entities["risk_level"].eq("red").sum()),
                "orange_count": int(entities["risk_level"].eq("orange").sum()),
                "pending_count": int(entities["review_status"].isin(["待处理", "待业务确认"]).sum()),
                "observation_count": int(entities["is_observation"].sum()),
                "one_shot_attention_count": int(entities["is_one_shot"].sum()),
                "caveat": "月度业务复核数据包，精确概率仅在 gate 允许时展示。",
            },
            "kpi_cards": {
                "high_risk_entity_count": int(entities["is_high_risk"].sum()),
                "manual_review_count": int(entities["review_status"].isin(["待处理", "待业务确认"]).sum()),
                "observation_count": int(entities["is_observation"].sum()),
                "potential_value_total_display": "相对潜在影响，未接入真实金额核验",
                "recovery_verified_placeholder": "待接入工单反馈",
                "recovery_rate_placeholder": "待接入工单反馈",
            },
            "top_clues": [self.entity_card(row, evidence) for _, row in top.head(8).iterrows()],
            "links": {"clues_url": "clues.html", "watchlist_url": "watchlist.html", "dashboard_url": "dashboard.html", "verify_url": "verify.html"},
        }

    def clues_payload(self, top: pd.DataFrame, entities: pd.DataFrame) -> dict[str, Any]:
        cols = [
            "risk_entity_id",
            "hospital_display_name",
            "product_line_display_name",
            "risk_level",
            "risk_color",
            "risk_score_display",
            "palive_display",
            "palive_display_mode",
            "value_at_risk_display",
            "root_cause_label",
            "region_display_name",
            "review_status",
            "suggested_action_short",
            "user_visible_caveat",
        ]
        return {
            "page_title": "全部风险线索",
            "subtitle": "月度风险线索列表，供业务复核使用。",
            "filters": {
                "risk_level_options": sorted(entities["risk_level"].dropna().unique().tolist()),
                "product_line_options": sorted(entities["product_line_display_name"].dropna().head(200).unique().tolist()),
                "root_cause_options": sorted(entities["root_cause_label"].dropna().unique().tolist()),
                "region_options": ["未配置地区"],
                "review_status_options": ["待处理", "跟进中", "已标记观察", "待业务确认", "不可行动"],
            },
            "table_columns": ["医院", "产品线", "等级", "风险分", "P(alive)", "挽回价值", "根因", "地区", "状态", "操作"],
            "items": self.records(top[cols]),
            "pagination": {"page": 1, "page_size": len(top), "total_items": int(len(entities))},
            "summary_counts": {
                "high_risk": int(entities["is_high_risk"].sum()),
                "observation": int(entities["is_observation"].sum()),
                "one_shot_attention": int(entities["is_one_shot"].sum()),
            },
        }

    def watchlist_payload(self, entities: pd.DataFrame) -> dict[str, Any]:
        watch = entities[entities["final_candidate_status"].isin(["observation_only", "low_confidence_watch", "not_actionable"])].head(500)
        items = []
        for _, row in watch.iterrows():
            items.append(
                {
                    "risk_entity_id": row["risk_entity_id"],
                    "hospital_display_name": row["hospital_display_name"],
                    "product_line_display_name": row["product_line_display_name"],
                    "risk_score_display": row["risk_score_display"],
                    "palive_display": row["palive_display"],
                    "trigger_signal": row["root_cause_label"],
                    "first_seen_date": None,
                    "observed_days": None,
                    "potential_value_display": row["value_at_risk_display"],
                    "trend_status": "继续观察",
                    "action": "观察，不作为强预警",
                }
            )
        return {
            "page_title": "观察清单",
            "subtitle": "观察对象不是强预警，只建议继续跟踪。",
            "kpi_cards": {"observation_count": len(watch), "average_palive": "不展示", "potential_value_display": "相对潜在影响"},
            "explanation_banner": "观察对象不是强预警，只是建议继续跟踪；历史不足对象不展示精确概率。",
            "items": items,
        }

    def dashboard_payload(self, report_month: str, entities: pd.DataFrame) -> dict[str, Any]:
        by_product = entities.groupby("product_line_display_name").size().sort_values(ascending=False).head(20).reset_index(name="risk_entity_count")
        return {
            "page_title": "管理驾驶舱 · 本月统计",
            "report_month": report_month,
            "kpi_cards": {
                "monthly_risk_exposure": "相对潜在影响汇总",
                "monthly_recovered_amount": "待接入工单反馈",
                "verification_rate": "待接入工单反馈",
                "recovery_roi": "待接入工单反馈",
                "inspection_coverage_units": int(len(entities)),
            },
            "risk_exposure_trend": [{"month": report_month, "high_risk_count": int(entities["is_high_risk"].sum()), "observation_count": int(entities["is_observation"].sum())}],
            "recovery_rate_trend_placeholder": "待接入工单反馈",
            "recovery_funnel_placeholder": "待接入工单反馈",
            "risk_by_region": [{"region_display_name": "未配置地区", "risk_entity_count": int(len(entities))}],
            "risk_by_product_line": self.records(by_product),
            "caveat": "未接入真实工单反馈，不展示已确认回款、兑现统计或 ROI。",
        }

    def backtest_payload(self) -> dict[str, Any]:
        return {
            "proof_case_report_allowed": False,
            "title": "历史命中案例",
            "explanation": "当前暂未形成客户确认的历史命中案例。后续可由业务人员回填复核结果，用于生成历史命中案例。",
            "required_feedback_fields": ["risk_entity_id", "review_result", "followup_date", "purchase_recovered_flag", "comment"],
            "placeholder_cases": [],
        }

    def verify_payload(self) -> dict[str, Any]:
        return {
            "verification_enabled": False,
            "pending_verification_count": 0,
            "explanation": "当前尚未接入真实业务处理反馈，暂不计算业务兑现情况。后续业务人员回填后，可按订单数据核验是否恢复采购。",
            "feedback_template_fields": ["risk_entity_id", "handler", "action_taken", "feedback_date", "next_purchase_observed"],
        }

    def distributor_payload(self) -> dict[str, Any]:
        return {
            "delivery_detector_enabled": False,
            "alerts": [],
            "explanation": "当前配送相关证据未达到正式预警条件，暂不生成配送侧结论。",
            "data_quality_note": "配送与履约类 detector 多数仍为预留或待验证。",
        }

    def order_detail_payload(self) -> dict[str, Any]:
        return {
            "order_level_trace_available": False,
            "schema": ["order_id", "candidate_id", "hospital_display_name", "drug_display_name", "purchase_date", "purchase_quantity_display", "purchase_amount_display", "delivery_rate_display", "evidence_role", "caveat"],
            "items": [],
            "caveat": "当前批次未提供可安全展示的订单级明细。",
        }

    def monthly_report_payload(self, daily_reports: pd.DataFrame, entities: pd.DataFrame, cards: pd.DataFrame) -> dict[str, Any]:
        report = daily_reports.iloc[0]
        return {
            "report_type": "monthly",
            "report_month": report["report_month"],
            "daily_report_id": report["daily_report_id"],
            "title": report["title"],
            "summary": report["summary_text"],
            "linked_counts": {"risk_entities": int(len(entities)), "risk_cards": int(len(cards)), "proof_cases": 0},
        }

    def clue_detail_samples(self, entities: pd.DataFrame, cards: pd.DataFrame, evidence: pd.DataFrame) -> dict[str, dict[str, Any]]:
        samples: dict[str, dict[str, Any]] = {}
        for _, row in entities.iterrows():
            entity_cards = cards[cards["risk_entity_id"].eq(row["risk_entity_id"])].head(10)
            entity_evidence = evidence[evidence["risk_entity_id"].eq(row["risk_entity_id"])].head(20)
            samples[f"{row['risk_entity_id']}.json"] = {
                "risk_entity": json_clean(row.to_dict()),
                "hero_metrics": {"risk_score_display": row["risk_score_display"], "palive_display": row["palive_display"], "value_at_risk_display": row["value_at_risk_display"]},
                "diagnosis_quote": row["main_reason_summary"],
                "risk_tags": [row["risk_level"], row["root_cause_label"]],
                "palive_or_risk_trend": [],
                "risk_cards": self.records(entity_cards),
                "evidence_chain": self.records(entity_evidence[["evidence_type", "evidence_level", "evidence_text", "visibility_level"]]) if not entity_evidence.empty else [],
                "guardrail_notes": ["当前结果仅供月度业务复核。", "仍需业务人员结合实际情况复核。"],
                "recommended_actions": [row["suggested_action_short"]],
                "traceable_orders": [],
                "disposition_panel": {"manual_review_required": True, "auto_dispatch_allowed": False},
                "forbidden_claims": ["不得作确定性结论", "不得作绝对采购判断", "不得作配送侧归因结论"],
                "user_visible_caveat": row["user_visible_caveat"],
            }
        return samples

    def entity_card(self, row: pd.Series, evidence: pd.DataFrame) -> dict[str, Any]:
        ev = evidence[evidence["risk_entity_id"].eq(row["risk_entity_id"])].head(2)
        return {
            "risk_entity_id": row["risk_entity_id"],
            "hospital_display_name": row["hospital_display_name"],
            "product_line_display_name": row["product_line_display_name"],
            "risk_level": row["risk_level"],
            "risk_color": row["risk_color"],
            "main_reason_summary": row["main_reason_summary"],
            "root_cause_label": row["root_cause_label"],
            "risk_score_display": row["risk_score_display"],
            "palive_display": row["palive_display"],
            "value_at_risk_display": row["value_at_risk_display"],
            "suggested_action_short": row["suggested_action_short"],
            "evidence_preview": ev["evidence_text"].tolist() if not ev.empty else ["建议结合近期采购记录复核。"],
            "user_visible_caveat": row["user_visible_caveat"],
        }

    def assert_customer_safe(self, payloads: dict[str, Any]) -> None:
        for key, payload in payloads.items():
            text = json.dumps(payload, ensure_ascii=False)
            if contains_forbidden_claims(text):
                raise ValueError(f"unsafe customer payload text in {key}")

    def write_payloads(self, payload_root: Path, payloads: dict[str, Any]) -> None:
        payload_root.mkdir(parents=True, exist_ok=True)
        sample_dir = payload_root / "clue_detail_samples"
        sample_dir.mkdir(parents=True, exist_ok=True)
        for name, payload in payloads.items():
            if name == "clue_detail_samples":
                for filename, sample in payload.items():
                    self.write_json(sample_dir / filename, sample)
            else:
                self.write_json(payload_root / f"{name}.json", payload)

    @staticmethod
    def write_json(path: Path, payload: Any) -> None:
        path.write_text(json.dumps(json_clean(payload), ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _top_entities(entities: pd.DataFrame, n: int) -> pd.DataFrame:
        work = entities.copy()
        work["rank_level"] = work["risk_level"].map({"red": 5, "orange": 4, "yellow": 3, "observation": 2, "attention": 2, "insufficient": 1}).fillna(0)
        work["rank_score"] = pd.to_numeric(work["risk_probability_value"], errors="coerce").fillna(0)
        return work.sort_values(["is_high_risk", "rank_level", "rank_score"], ascending=[False, False, False]).head(n)

    @staticmethod
    def records(df: pd.DataFrame) -> list[dict[str, Any]]:
        return [json_clean(row) for row in df.to_dict("records")]
