"""Page payload builder for backend MVC integration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .repositories import RiskResultRepository


class PagePayloadBuilder:
    def __init__(self, repository: RiskResultRepository):
        self.repository = repository

    def build_index_payload(self) -> dict[str, Any]:
        return self._payload_or_build("index_payload", self._build_index_payload)

    def build_clues_payload(self) -> dict[str, Any]:
        return self._payload_or_build("clues_payload", self._build_clues_payload)

    def build_clue_detail_payload(self, risk_entity_id: str) -> dict[str, Any]:
        entity = self.repository.get_risk_entity(risk_entity_id)
        if entity is None:
            raise KeyError(risk_entity_id)
        cards = self.repository.list_risk_cards(risk_entity_id).to_dict("records")
        for card in cards:
            card["evidence"] = self.repository.list_evidence(str(card["risk_card_id"])).to_dict("records")
        return {"risk_entity": entity, "risk_cards": cards, "auto_dispatch_allowed": False}

    def build_watchlist_payload(self) -> dict[str, Any]:
        return self._payload_or_build(
            "watchlist_payload",
            lambda: {"items": self.repository.list_risk_entities(is_observation=True).to_dict("records")},
        )

    def build_dashboard_payload(self) -> dict[str, Any]:
        return self._payload_or_build(
            "dashboard_payload",
            lambda: {"kpi_cards": {"feedback": "pending feedback integration"}},
        )

    def build_backtest_payload(self) -> dict[str, Any]:
        return self._payload_or_build(
            "backtest_payload",
            lambda: {"proof_case_report_allowed": False, "placeholder_cases": []},
        )

    def build_verify_payload(self) -> dict[str, Any]:
        return self._payload_or_build("verify_payload", lambda: {"verification_enabled": False})

    def build_distributor_payload(self) -> dict[str, Any]:
        return self._payload_or_build(
            "distributor_payload",
            lambda: {"delivery_detector_enabled": False, "alerts": []},
        )

    def build_frontend_workbench_payload(self) -> dict[str, Any]:
        return self._payload_or_build(
            "frontend_workbench_payload",
            lambda: build_default_frontend_payloads()["workbench"],
        )

    def build_frontend_risk_entities_payload(self) -> dict[str, Any]:
        return self._payload_or_build(
            "frontend_risk_entities_payload",
            lambda: build_default_frontend_payloads()["risk_entities"],
        )

    def build_frontend_risk_entity_detail_payload(self, risk_entity_id: str) -> dict[str, Any]:
        default_details = build_default_frontend_payloads()["risk_entity_details"]
        return self._payload_or_build(
            f"frontend_risk_entity_detail_{risk_entity_id}_payload",
            lambda: _detail_or_raise(default_details, risk_entity_id),
        )

    def build_frontend_oneshot_payload(self) -> dict[str, Any]:
        return self._payload_or_build(
            "frontend_oneshot_payload",
            lambda: build_default_frontend_payloads()["oneshot_terminals"],
        )

    def build_frontend_monthly_reports_payload(self) -> dict[str, Any]:
        return self._payload_or_build(
            "frontend_monthly_reports_payload",
            lambda: build_default_frontend_payloads()["monthly_reports"],
        )

    def build_frontend_proof_cases_payload(self) -> dict[str, Any]:
        return self._payload_or_build(
            "frontend_proof_cases_payload",
            lambda: build_default_frontend_payloads()["proof_cases"],
        )

    def _payload_or_build(self, page_name: str, builder: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        try:
            return self.repository.get_page_payload(page_name)
        except FileNotFoundError:
            return builder()

    def _build_index_payload(self) -> dict[str, Any]:
        entities = self.repository.list_risk_entities()
        high_risk_count = int(entities["is_high_risk"].sum()) if "is_high_risk" in entities else 0
        return {
            "page_title": "workbench",
            "top_clues": entities.head(8).to_dict("records"),
            "hero": {
                "high_risk_entity_count": high_risk_count,
                "auto_dispatch_allowed": False,
            },
        }

    def _build_clues_payload(self) -> dict[str, Any]:
        entities = self.repository.list_risk_entities()
        return {"items": entities.to_dict("records"), "pagination": {"total_items": len(entities)}}


def build_default_frontend_payloads() -> dict[str, Any]:
    """Return deterministic page payloads used while algorithm batch integration is settling."""

    batch_context = {
        "report_month": "2026-07",
        "score_as_of_date": "2026-07-31",
        "data_watermark_at": "2026-07-07 13:32",
        "score_batch_id": "2026-07-monthly-risk-score",
        "result_batch_id": "2026-07-monthly-risk-result",
        "primary_horizon": "H6",
        "primary_horizon_label": "主视角",
        "score_formula": "risk_probability * average_consumption_in_window",
    }
    entities = sorted(_risk_entities(), key=lambda item: item["business_score"], reverse=True)
    details = {entity["entity_id"]: _risk_entity_detail(entity) for entity in entities}
    workbench_rows = _workbench_rows(entities)
    daily_reports = _daily_reports(batch_context)
    oneshot = _oneshot_payload(batch_context)

    overview_metrics = [
        {"label": "主工作台", "value": str(len(workbench_rows)), "tone": "danger"},
        {"label": "风险卡", "value": "24", "tone": "warning"},
        {"label": "新进终端", "value": str(oneshot["summary"]["oneshot_count"]), "tone": "info"},
        {"label": "高价值待跟进", "value": "21", "tone": "success"},
    ]

    return {
        "workbench": {
            "batch_context": batch_context,
            "overview_metrics": overview_metrics,
            "fill_policy": {
                "manufacturer_code": "M001",
                "workbench_target_count": 20,
                "global_current_month_hospital_drug_count": len(entities),
                "fill_reason": "global 当月医院 × 药品数量不足时，主工作台使用补充算法填充到 20 个。",
            },
            "rows": workbench_rows,
        },
        "risk_entities": {
            "batch_context": batch_context,
            "entities": entities,
            "pagination": {"total_items": len(entities)},
        },
        "risk_entity_details": details,
        "oneshot_terminals": oneshot,
        "monthly_reports": {
            "batch_context": batch_context,
            "overview_metrics": overview_metrics,
            "daily_report_options": daily_reports,
            "monthly_reports": [
                {
                    "monthly_report_id": "monthly_2026_07",
                    "title": "2026-07 MonthlyReport",
                    "report_month": "2026-07",
                    "score_batch_id": batch_context["score_batch_id"],
                    "data_watermark_at": batch_context["data_watermark_at"],
                    "summary": "本月报告沉淀风险排序、detector 证据链、新进终端复购倾向与成功案例。",
                },
                {
                    "monthly_report_id": "monthly_2026_06",
                    "title": "2026-06 MonthlyReport",
                    "report_month": "2026-06",
                    "score_batch_id": "2026-06-monthly-risk-score",
                    "data_watermark_at": "2026-06-30 23:59",
                    "summary": "历史月报用于比较新增、持续、缓解、oneshot 复购倾向与主工作台补齐变化。",
                },
            ],
        },
        "proof_cases": {
            "items": [
                {
                    "proof_case_id": "proof_xiehe_2025",
                    "title": "Proof-case · 北京协和历史命中案例",
                    "visible": "业务可见",
                    "outcome": "历史高风险线索后续发生停购，证据包括采购间隔超期和品规收缩。",
                    "case_summary": "成功案例展示采购间隔超期、品规收缩和后续停购结果，突出产品提前识别价值。",
                },
                {
                    "proof_case_id": "proof_huaxi_2025",
                    "title": "Proof-case · 华西配送侧案例",
                    "visible": "业务可见",
                    "outcome": "系统提前识别配送履约恶化，业务复核后归因为断供侧问题。",
                    "case_summary": "成功案例展示配送履约恶化信号，帮助团队提前定位断供风险。",
                },
            ]
        },
    }


def _risk_entities() -> list[dict[str, Any]]:
    rows = [
        {
            "entity_id": "re_huaxi_c_h6",
            "hospital_name": "四川大学华西医院",
            "drug_name": "C产品线 · 肿瘤",
            "manufacturer_code": "M001",
            "region": "西南",
            "horizon": "H6",
            "risk_probability": 0.74,
            "average_consumption_in_window": 1_950_000,
            "risk_band": "high",
            "risk_color": "red",
            "last_purchase_date": "2026-04-18",
            "days_since_last_purchase": 80,
            "risk_card_count": 5,
            "status": "优先跟进",
            "monthly_status": "persistent",
            "value_level": "高",
            "primary_reason": "连续停购苗头叠加配送履约恶化，需要判断需求流失还是断供问题。",
        },
        {
            "entity_id": "re_xiehe_a_h6",
            "hospital_name": "北京协和医院",
            "drug_name": "A产品线 · 心血管",
            "manufacturer_code": "M001",
            "region": "华北",
            "horizon": "H6",
            "risk_probability": 0.82,
            "average_consumption_in_window": 1_280_000,
            "risk_band": "high",
            "risk_color": "red",
            "last_purchase_date": "2026-05-02",
            "days_since_last_purchase": 66,
            "risk_card_count": 4,
            "status": "优先跟进",
            "monthly_status": "new",
            "value_level": "高",
            "primary_reason": "采购间隔超出历史节奏，近 3 月频次下降，品规从 4 个缩至 1 个。",
        },
        {
            "entity_id": "re_renji_a_h6",
            "hospital_name": "上海仁济医院",
            "drug_name": "A产品线 · 心血管",
            "manufacturer_code": "M002",
            "region": "华东",
            "horizon": "H6",
            "risk_probability": 0.61,
            "average_consumption_in_window": 860_000,
            "risk_band": "medium",
            "risk_color": "orange",
            "last_purchase_date": "2026-05-29",
            "days_since_last_purchase": 39,
            "risk_card_count": 3,
            "status": "跟进中",
            "monthly_status": "worsening",
            "value_level": "中",
            "primary_reason": "采购量和采购频次同步下降，需要确认是否为正常窗口波动。",
        },
    ]
    for row in rows:
        row["business_score"] = round(row["risk_probability"] * row["average_consumption_in_window"])
    return rows


def _risk_entity_detail(entity: dict[str, Any]) -> dict[str, Any]:
    return {
        "entity": entity,
        "horizon_profiles": {
            "H3": _horizon_profile(entity, "H3", "短窗预警", -0.14, 0.48, 0.86),
            "H6": _horizon_profile(entity, "H6", "主视角", 0, 1, 1),
            "H12": _horizon_profile(entity, "H12", "长窗经营影响", 0.08, 1.72, 1.08),
        },
    }


def _horizon_profile(
    entity: dict[str, Any],
    horizon: str,
    label: str,
    probability_delta: float,
    consumption_multiplier: float,
    detector_factor: float,
) -> dict[str, Any]:
    probability = min(0.96, max(0.05, round(entity["risk_probability"] + probability_delta, 2)))
    consumption = round(entity["average_consumption_in_window"] * consumption_multiplier)
    return {
        "horizon": horizon,
        "label": label,
        "risk_probability": probability,
        "average_consumption_in_window": consumption,
        "business_score": round(probability * consumption),
        "reason": f"{horizon} {label}: {entity['primary_reason']}",
        "detector_results": [_detector_result(item, horizon, label, detector_factor) for item in _detector_templates(entity)],
        "xgboost_shap": _shap_highlights(entity, horizon),
        "detector_narrative": (
            f"{horizon} detector 结果自然语言聚合：采购间隔、频次、品规和履约信号共同解释 "
            f"{entity['hospital_name']} × {entity['drug_name']} 的业务评分排序。"
        ),
    }


def _detector_templates(entity: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "detector_id": "gap",
            "detector_name": "采购间隔 detector",
            "score": 0.88 if entity["risk_band"] == "high" else 0.54,
            "signal": "强命中" if entity["risk_band"] == "high" else "关注",
            "status": "采购间隔超期",
            "evidence": f"当前间隔 {entity['days_since_last_purchase']} 天，高于自身历史采购节奏。",
            "action": "确认院内采购计划、竞品替代和配送节奏变化。",
        },
        {
            "detector_id": "frequency",
            "detector_name": "频次下降 detector",
            "score": 0.81 if entity["risk_band"] == "high" else 0.76,
            "signal": "命中",
            "status": "采购频次下降",
            "evidence": "近 90 天采购频次低于 12 个月基线。",
            "action": "复核科室需求和采购计划变化。",
        },
        {
            "detector_id": "sku",
            "detector_name": "品规收缩 detector",
            "score": 0.72 if entity["risk_band"] == "high" else 0.58,
            "signal": "命中" if entity["risk_band"] == "high" else "关注",
            "status": "品规覆盖收缩",
            "evidence": "活跃品规覆盖减少，主力规格需要重点确认。",
            "action": "检查竞品替代、规格替换和院内目录变化。",
        },
        {
            "detector_id": "fulfillment",
            "detector_name": "配送履约 detector",
            "score": 0.83 if entity["entity_id"] == "re_huaxi_c_h6" else 0.46,
            "signal": "命中" if entity["entity_id"] == "re_huaxi_c_h6" else "关注",
            "status": "配送履约波动",
            "evidence": "配送完成率较前期出现波动，结合需求侧信号统一判断。",
            "action": "同步配送侧确认近期履约稳定性。",
        },
    ]


def _detector_result(template: dict[str, Any], horizon: str, label: str, factor: float) -> dict[str, Any]:
    return {
        **template,
        "score": round(min(0.99, template["score"] * factor), 2),
        "evidence": f"{horizon} {label}: {template['evidence']}",
    }


def _shap_highlights(entity: dict[str, Any], horizon: str) -> list[dict[str, Any]]:
    return [
        {
            "feature": f"avg_consumption_{horizon.lower()}",
            "contribution": 0.24 if entity["business_score"] > 1_000_000 else 0.11,
            "explanation": f"{horizon} 预测窗口内平均消费金额放大业务优先级。",
        },
        {
            "feature": "days_since_last_purchase",
            "contribution": 0.18,
            "explanation": "距离末次采购天数抬升风险概率。",
        },
        {
            "feature": "frequency_drop_90d",
            "contribution": 0.15,
            "explanation": "近 90 天采购频次低于自身基线。",
        },
    ]


def _workbench_rows(entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [
        {
            "row_id": entity["entity_id"],
            "entity_id": entity["entity_id"],
            "manufacturer_code": entity["manufacturer_code"],
            "hospital_name": entity["hospital_name"],
            "drug_name": entity["drug_name"],
            "region": entity["region"],
            "risk_probability": entity["risk_probability"],
            "average_consumption_in_window": entity["average_consumption_in_window"],
            "business_score": entity["business_score"],
            "source_type": "global 当月命中",
            "fill_source": "主干风险模型",
            "action": "查看风险卡",
        }
        for entity in entities
    ]
    for index, hospital in enumerate(_fill_hospitals(), start=1):
        probability = round(0.58 - (index - 1) * 0.012, 2)
        consumption = 760_000 - (index - 1) * 18_000
        rows.append(
            {
                "row_id": f"fill_{index:02d}",
                "entity_id": None,
                "manufacturer_code": "M001",
                "hospital_name": hospital,
                "drug_name": _fill_drugs()[(index - 1) % len(_fill_drugs())],
                "region": ["华东", "华中", "华北", "华南", "西南"][(index - 1) % 5],
                "risk_probability": probability,
                "average_consumption_in_window": consumption,
                "business_score": round(probability * consumption),
                "source_type": "补充算法",
                "fill_source": _fill_sources()[(index - 1) % len(_fill_sources())],
                "action": "进入主工作台跟进清单",
            }
        )
    return sorted(rows, key=lambda item: item["business_score"], reverse=True)[:20]


def _fill_hospitals() -> list[str]:
    return [
        "南京鼓楼医院",
        "中南大学湘雅医院",
        "山东大学齐鲁医院",
        "武汉同济医院",
        "广州中山肿瘤医院",
        "重庆医科大学附属第一医院",
        "安徽医科大学第一附属医院",
        "北京朝阳医院",
        "复旦大学附属华山医院",
        "天津医科大学总医院",
        "西安交通大学第一附属医院",
        "大连医科大学附属第一医院",
        "厦门大学附属第一医院",
        "徐州医科大学附属医院",
        "新疆医科大学第一附属医院",
        "海南省人民医院",
        "贵州医科大学附属医院",
    ]


def _fill_drugs() -> list[str]:
    return ["A产品线 · 心血管", "B产品线 · 抗感染", "C产品线 · 肿瘤", "D产品线 · 消化"]


def _fill_sources() -> list[str]:
    return ["oneshot 复购倾向", "detector 补充排序", "历史节奏回补", "高价值终端覆盖"]


def _oneshot_payload(batch_context: dict[str, Any]) -> dict[str, Any]:
    items = [
        _oneshot_item("os_001", "浙江大学医学院附属第一医院", "D产品线 · 消化", "华东", "2026-06-18", 320_000, 19, 0.79, 410_000),
        _oneshot_item("os_002", "郑州大学第一附属医院", "A产品线 · 心血管", "华中", "2026-06-24", 180_000, 13, 0.64, 260_000),
        _oneshot_item("os_003", "苏州大学附属第一医院", "C产品线 · 肿瘤", "华东", "2026-06-05", 510_000, 32, 0.71, 850_000),
        _oneshot_item("os_004", "南方医科大学南方医院", "B产品线 · 抗感染", "华南", "2026-06-21", 220_000, 16, 0.68, 300_000),
        _oneshot_item("os_005", "吉林大学第一医院", "A产品线 · 心血管", "东北", "2026-06-12", 150_000, 25, 0.57, 190_000),
        _oneshot_item("os_006", "昆明医科大学第一附属医院", "D产品线 · 消化", "西南", "2026-06-28", 260_000, 9, 0.73, 360_000),
    ]
    return {
        "report_month": batch_context["report_month"],
        "summary": {
            "oneshot_count": len(items),
            "high_repurchase_propensity_count": sum(1 for item in items if item["repurchase_propensity"] >= 0.7),
            "average_repurchase_propensity": round(sum(item["repurchase_propensity"] for item in items) / len(items), 2),
            "expected_repurchase_amount": sum(item["expected_repurchase_amount"] for item in items),
        },
        "items": sorted(items, key=lambda item: item["repurchase_propensity"], reverse=True),
    }


def _oneshot_item(
    oneshot_id: str,
    hospital_name: str,
    drug_name: str,
    region: str,
    first_purchase_date: str,
    first_purchase_amount: int,
    days_since_first_purchase: int,
    repurchase_propensity: float,
    expected_repurchase_amount: int,
) -> dict[str, Any]:
    priority = "高复购倾向" if repurchase_propensity >= 0.7 else "中高复购倾向"
    return {
        "oneshot_id": oneshot_id,
        "hospital_name": hospital_name,
        "drug_name": drug_name,
        "region": region,
        "first_purchase_date": first_purchase_date,
        "first_purchase_amount": first_purchase_amount,
        "days_since_first_purchase": days_since_first_purchase,
        "repurchase_propensity": repurchase_propensity,
        "expected_repurchase_amount": expected_repurchase_amount,
        "priority": priority,
        "reason": "首采金额、首采后天数和区域同类终端复购表现共同推高复购促进优先级。",
    }


def _daily_reports(batch_context: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "daily_report_id": "daily_2026_07_07",
            "date": "2026-07-07",
            "label": "当前日报",
            "title": "2026-07-07 风险日报",
            "report_month": batch_context["report_month"],
            "score_batch_id": batch_context["score_batch_id"],
            "data_watermark_at": batch_context["data_watermark_at"],
            "high_risk_entities": 9,
            "oneshot_count": 6,
            "detector_alerts": 24,
            "summary": "当前日报聚焦 H6 高风险 entity、oneshot 复购倾向和 detector 证据链。",
        },
        {
            "daily_report_id": "daily_2026_07_06",
            "date": "2026-07-06",
            "label": "上一期",
            "title": "2026-07-06 风险日报",
            "report_month": batch_context["report_month"],
            "score_batch_id": "2026-07-daily-risk-20260706",
            "data_watermark_at": "2026-07-06 18:00",
            "high_risk_entities": 8,
            "oneshot_count": 5,
            "detector_alerts": 19,
            "summary": "上一期日报用于对比新增、持续和缓解的风险实体变化。",
        },
        {
            "daily_report_id": "daily_2026_07_05",
            "date": "2026-07-05",
            "label": "历史日报",
            "title": "2026-07-05 风险日报",
            "report_month": batch_context["report_month"],
            "score_batch_id": "2026-07-daily-risk-20260705",
            "data_watermark_at": "2026-07-05 18:00",
            "high_risk_entities": 7,
            "oneshot_count": 4,
            "detector_alerts": 17,
            "summary": "历史日报展示风险排序、detector 证据和新进终端复购倾向的连续变化。",
        },
    ]


def _detail_or_raise(details: dict[str, Any], risk_entity_id: str) -> dict[str, Any]:
    if risk_entity_id not in details:
        raise KeyError(risk_entity_id)
    return details[risk_entity_id]
