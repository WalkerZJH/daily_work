"""Transform M-closure tables into MVC domain/result-batch tables."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import json
import math

import numpy as np
import pandas as pd

from .business_copy_renderer import BusinessCopyRenderer
from .schemas import (
    DAILY_REPORT_COLUMNS,
    PROOF_CASE_COLUMNS,
    RISK_CARD_COLUMNS,
    RISK_ENTITY_COLUMNS,
    RISK_EVIDENCE_COLUMNS,
    TIMELINE_COLUMNS,
    WORK_ORDER_RESERVED_COLUMNS,
)


def transform_m_closure_to_result_tables(
    inputs: dict[str, pd.DataFrame],
    *,
    selected_candidate_ids: set[str] | None = None,
    max_cards_per_entity: int = 5,
    max_business_visible_evidence_per_card: int = 3,
) -> dict[str, pd.DataFrame]:
    base = build_base_frame(inputs, selected_candidate_ids=selected_candidate_ids)
    risk_entities = build_risk_entities(base)
    risk_cards, evidence = build_cards_and_evidence(
        risk_entities,
        inputs["m4"],
        max_cards_per_entity=max_cards_per_entity,
        max_business_visible_evidence_per_card=max_business_visible_evidence_per_card,
    )
    risk_entities = attach_card_counts(risk_entities, risk_cards)
    return {
        "risk_entities": risk_entities,
        "risk_cards": risk_cards,
        "risk_card_evidence": evidence,
        "risk_entity_timeline": build_empty_timeline(),
        "hospital_aggregates": build_hospital_aggregates(risk_entities),
        "drug_aggregates": build_drug_aggregates(risk_entities),
        "daily_reports": build_daily_reports(risk_entities, risk_cards),
        "proof_cases": pd.DataFrame(columns=PROOF_CASE_COLUMNS),
        "work_order_reserved": pd.DataFrame(columns=WORK_ORDER_RESERVED_COLUMNS),
    }


def build_base_frame(inputs: dict[str, pd.DataFrame], selected_candidate_ids: set[str] | None = None) -> pd.DataFrame:
    m5 = inputs["m5"].copy()
    if selected_candidate_ids is not None:
        m5 = m5[m5["candidate_id"].astype(str).isin(selected_candidate_ids)].copy()
    m1_cols = [
        "candidate_id",
        "selection_reason",
        "display_section",
        "is_high_risk",
        "user_visible_caveat",
        "probability_score",
        "churn_probability_H",
        "demand_shape_label",
        "history_sufficiency_flag",
        "probability_display_level",
        "display_mode",
    ]
    available_m1_cols = [col for col in m1_cols if col in inputs["m1"].columns]
    base = m5.merge(inputs["m1"][available_m1_cols].drop_duplicates("candidate_id"), on="candidate_id", how="left")
    gate_cols = ["candidate_id", "probability_display_allowed", "model_confidence_bucket", "choice_set_caveat", "selected_subset_caveat", "manual_review_required"]
    available_gate_cols = [col for col in gate_cols if col in inputs["gate"].columns]
    if available_gate_cols:
        base = base.merge(inputs["gate"][available_gate_cols].drop_duplicates("candidate_id"), on="candidate_id", how="left")
    for col in ["auto_dispatch_allowed", "probability_display_allowed", "choice_set_caveat", "selected_subset_caveat"]:
        base[col] = base.get(col, False)
        base[col] = base[col].fillna(False).astype(bool)
    return base


def build_risk_entities(base: pd.DataFrame) -> pd.DataFrame:
    renderer = BusinessCopyRenderer()
    report_month = infer_report_month(base)
    out = base.copy()
    out["report_month"] = report_month
    out["risk_entity_id"] = out["candidate_id"].map(lambda x: "re_" + stable_hash(str(x), 16))
    out["tenant_id"] = "tenant_demo"
    out["enterprise_id"] = "enterprise_demo"
    out["manufacturer_display_name"] = out["manufacturer_code"].map(lambda x: f"生产商 {short_code(x)}")
    out["hospital_display_name"] = out["hospital_code"].map(lambda x: f"医院 {short_code(x)}")
    out["drug_code"] = out["drug_group"]
    out["drug_display_name"] = out["drug_group"].map(lambda x: f"药品 {short_code(x)}")
    out["drug_category_code"] = ""
    out["product_line_code"] = out["drug_group"]
    out["product_line_display_name"] = out["drug_group"].map(lambda x: f"产品线 {short_code(x)}")
    out["primary_horizon"] = out["horizon"]
    out["region_code"] = "unknown"
    out["region_display_name"] = "未配置地区"
    out["is_probability_allowed"] = out["probability_display_level"].eq("probability_allowed")
    out["is_one_shot"] = out["candidate_type"].eq("one_shot")
    out["is_observation"] = out["candidate_type"].eq("demand_shape_observation") | out["final_candidate_status"].isin(["observation_only", "low_confidence_watch", "not_actionable"])
    p = pd.to_numeric(out["churn_probability_H"], errors="coerce")
    out["risk_probability_value"] = np.where(out["is_probability_allowed"] & ~out["is_one_shot"], p, np.nan)
    out["probability_display_mode"] = out["display_mode"].fillna("hide_probability")
    out["risk_level"] = risk_level(out, p)
    out["risk_color"] = out["risk_level"].map({"red": "red", "orange": "orange", "yellow": "yellow", "observation": "yellow", "attention": "yellow", "insufficient": "gray"}).fillna("gray")
    out["is_high_risk"] = out["risk_level"].isin(["red", "orange"]) & ~out["is_observation"] & ~out["is_one_shot"]
    out["risk_probability_display"] = risk_probability_display(out, p)
    out["palive_display"] = np.where(out["is_probability_allowed"] & ~out["is_one_shot"] & p.notna(), (1 - p).map(lambda x: f"{x:.0%}"), "不展示")
    out["palive_display_mode"] = np.where(out["is_probability_allowed"] & ~out["is_one_shot"], "derived_from_churn_probability", "hidden")
    out["risk_score_display"] = risk_score_display(out, p)
    out["potential_value_level"] = np.select([p.ge(0.75), p.ge(0.45)], ["high", "medium"], default="low")
    out["value_at_risk_display"] = "相对潜在影响：" + pd.Series(out["potential_value_level"], index=out.index).map({"high": "高", "medium": "中", "low": "低"}).fillna("待接入")
    out["business_priority_display"] = "月度工作清单排序"
    rendered = out.apply(renderer.render_for_row, axis=1, result_type="expand")
    out["main_reason_summary"] = rendered["one_line_diagnosis"]
    out["root_cause_label"] = root_cause_label(out)
    out["review_status"] = review_status(out)
    out["risk_card_count"] = 0
    out["has_work_order"] = False
    out["suggested_action_short"] = rendered["suggested_action_text"]
    out["user_visible_caveat"] = rendered["caveat_text"]
    out["created_at"] = pd.Timestamp.now().isoformat()
    out["auto_dispatch_allowed"] = False
    return select_cols(out, RISK_ENTITY_COLUMNS)


def build_cards_and_evidence(
    risk_entities: pd.DataFrame,
    m4: pd.DataFrame,
    *,
    max_cards_per_entity: int = 5,
    max_business_visible_evidence_per_card: int = 3,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    renderer = BusinessCopyRenderer()
    entity = risk_entities[["risk_entity_id", "candidate_id", "tenant_id", "risk_level", "risk_color", "primary_horizon", "risk_probability_display", "main_reason_summary", "suggested_action_short", "user_visible_caveat"]].copy()
    primary = entity.copy()
    primary["risk_card_id"] = "rc_" + primary["risk_entity_id"] + "_primary"
    primary["card_type"] = np.select(
        [
            risk_entities["is_one_shot"],
            risk_entities["is_observation"],
        ],
        ["one_shot_attention", "demand_shape_observation"],
        default="primary_risk",
    )
    primary["card_title"] = primary["card_type"].map({"one_shot_attention": "新进终端关注", "demand_shape_observation": "观察对象"}).fillna("月度风险复核")
    primary["card_level"] = primary["risk_level"]
    primary["card_color"] = primary["risk_color"]
    primary["horizon"] = primary["primary_horizon"]
    primary["card_summary"] = primary["main_reason_summary"]
    primary["candidate_reason"] = "monthly_mvc_model_package"
    primary["is_primary"] = True
    primary["source_module"] = "M5/M7"
    primary["evidence_count"] = 0
    primary["suggested_action"] = primary["suggested_action_short"]
    primary["created_at"] = pd.Timestamp.now().isoformat()

    selected_ids = set(entity["candidate_id"].dropna().astype(str))
    if m4.empty:
        return select_cols(primary, RISK_CARD_COLUMNS), pd.DataFrame(columns=RISK_EVIDENCE_COLUMNS)
    m4 = m4[m4["candidate_id"].astype(str).isin(selected_ids)].copy()
    hits = m4[m4["hit_flag"].astype(str).str.lower().isin(["true", "1"])].copy()
    hits = hits.merge(entity[["candidate_id", "risk_entity_id", "tenant_id", "user_visible_caveat"]], on="candidate_id", how="inner")
    if hits.empty:
        return select_cols(primary, RISK_CARD_COLUMNS), pd.DataFrame(columns=RISK_EVIDENCE_COLUMNS)
    hits["risk_card_id"] = "rc_" + hits["risk_entity_id"] + "_" + hits["detector_name"].astype(str).map(lambda x: stable_hash(x, 8))
    det_cards = hits.drop_duplicates(["risk_card_id"]).copy()
    det_cards["_card_rank"] = det_cards.groupby("risk_entity_id").cumcount()
    det_cards = det_cards[det_cards["_card_rank"] < max(0, max_cards_per_entity - 1)].copy()
    det_cards["card_type"] = det_cards["detector_name"].map(detector_card_type).fillna("evidence")
    det_cards["card_title"] = det_cards["detector_name"].map(renderer.detector_display_text)
    det_cards["card_level"] = det_cards["severity"].map({"strong": "orange", "medium": "yellow"}).fillna("yellow")
    det_cards["card_color"] = det_cards["card_level"].map({"orange": "orange", "yellow": "yellow"}).fillna("yellow")
    det_cards["horizon"] = det_cards["candidate_id"].astype(str).str.split("|").str[-1]
    det_cards["risk_probability_display"] = "不展示"
    det_cards["card_summary"] = det_cards["card_title"]
    det_cards["candidate_reason"] = det_cards["reason_code"]
    det_cards["is_primary"] = False
    det_cards["source_module"] = "M4"
    det_cards["evidence_count"] = 1
    det_cards["suggested_action"] = "建议业务人员结合实际采购情况复核。"
    det_cards["created_at"] = pd.Timestamp.now().isoformat()

    allowed_card_ids = set(det_cards["risk_card_id"].astype(str))
    evidence = hits[hits["risk_card_id"].astype(str).isin(allowed_card_ids)].copy()
    evidence["evidence_id"] = "ev_" + evidence["risk_card_id"].astype(str) + "_" + evidence.groupby("risk_card_id").cumcount().astype(str)
    evidence["evidence_type"] = evidence["detector_name"].map(detector_card_type).fillna("behavior_signal")
    evidence["evidence_level"] = evidence["severity"].fillna("medium")
    evidence["evidence_text"] = evidence["detector_name"].map(renderer.detector_display_text)
    evidence["business_metric_name"] = evidence["detector_name"].map(detector_metric_name).fillna("采购行为变化")
    evidence["business_metric_value"] = evidence["evidence_values"].astype(str).str[:180]
    evidence["source_feature_name"] = evidence["evidence_fields"]
    evidence["source_feature_value"] = evidence["business_metric_value"]
    evidence["visibility_level"] = "business_visible"
    evidence["sort_order"] = evidence.groupby("risk_card_id").cumcount() + 1
    evidence = evidence[evidence["sort_order"] <= max_business_visible_evidence_per_card].copy()
    evidence_counts = evidence.groupby("risk_card_id").size().reset_index(name="evidence_count")
    det_cards = det_cards.drop(columns=["evidence_count"], errors="ignore").merge(evidence_counts, on="risk_card_id", how="left")
    det_cards["evidence_count"] = det_cards["evidence_count"].fillna(0).astype(int)
    cards = pd.concat([select_cols(primary, RISK_CARD_COLUMNS), select_cols(det_cards, RISK_CARD_COLUMNS)], ignore_index=True)
    return cards, select_cols(evidence, RISK_EVIDENCE_COLUMNS)


def attach_card_counts(risk_entities: pd.DataFrame, risk_cards: pd.DataFrame) -> pd.DataFrame:
    counts = risk_cards.groupby("risk_entity_id").size().reset_index(name="risk_card_count")
    out = risk_entities.drop(columns=["risk_card_count"], errors="ignore").merge(counts, on="risk_entity_id", how="left")
    out["risk_card_count"] = out["risk_card_count"].fillna(0).astype(int)
    return out


def build_empty_timeline() -> pd.DataFrame:
    return pd.DataFrame(columns=TIMELINE_COLUMNS)


def build_hospital_aggregates(risk_entities: pd.DataFrame) -> pd.DataFrame:
    return risk_entities.groupby(["tenant_id", "hospital_code", "hospital_display_name"], dropna=False).agg(
        risk_entity_count=("risk_entity_id", "size"),
        high_risk_count=("is_high_risk", "sum"),
        observation_count=("is_observation", "sum"),
        one_shot_attention_count=("is_one_shot", "sum"),
    ).reset_index()


def build_drug_aggregates(risk_entities: pd.DataFrame) -> pd.DataFrame:
    return risk_entities.groupby(["tenant_id", "drug_group", "drug_group_source", "product_line_display_name"], dropna=False).agg(
        risk_entity_count=("risk_entity_id", "size"),
        high_risk_count=("is_high_risk", "sum"),
        observation_count=("is_observation", "sum"),
    ).reset_index()


def build_daily_reports(risk_entities: pd.DataFrame, risk_cards: pd.DataFrame) -> pd.DataFrame:
    report_month = str(risk_entities["report_month"].iloc[0]) if len(risk_entities) else pd.Timestamp.today().strftime("%Y-%m")
    batch_id = f"{report_month}-monthly-v1"
    payload = {
        "report_type": "monthly",
        "high_risk_entity_count": int(risk_entities["is_high_risk"].sum()) if len(risk_entities) else 0,
        "observation_count": int(risk_entities["is_observation"].sum()) if len(risk_entities) else 0,
        "one_shot_attention_count": int(risk_entities["is_one_shot"].sum()) if len(risk_entities) else 0,
        "customer_facing_probability_service_allowed": False,
        "auto_dispatch_allowed": False,
    }
    top_entities = risk_entities.sort_values(["is_high_risk", "risk_level"], ascending=[False, True]).head(50)
    return pd.DataFrame(
        [
            {
                "daily_report_id": f"monthly_{batch_id}",
                "report_type": "monthly",
                "report_month": report_month,
                "report_date": pd.Timestamp.today().date().isoformat(),
                "cutoff_month": report_month,
                "default_horizon": "H12",
                "title": f"{report_month} 生产商风险线索月度数据包",
                "summary_text": "月度风险线索数据包，供内部分析师视图和业务复核使用。",
                "high_risk_entity_count": int(risk_entities["is_high_risk"].sum()) if len(risk_entities) else 0,
                "new_high_risk_entity_count": int(risk_entities["is_high_risk"].sum()) if len(risk_entities) else 0,
                "key_hospital_count": int(risk_entities["hospital_code"].nunique()) if len(risk_entities) else 0,
                "key_drug_count": int(risk_entities["drug_group"].nunique()) if len(risk_entities) else 0,
                "proof_case_count": 0,
                "report_payload_json": json.dumps(payload, ensure_ascii=False),
                "linked_risk_entity_ids": json.dumps(top_entities["risk_entity_id"].tolist(), ensure_ascii=False),
                "linked_risk_card_ids": json.dumps(risk_cards["risk_card_id"].head(100).tolist(), ensure_ascii=False),
                "linked_proof_case_ids": json.dumps([], ensure_ascii=False),
                "created_at": pd.Timestamp.now().isoformat(),
            }
        ],
        columns=DAILY_REPORT_COLUMNS,
    )


def infer_report_month(df: pd.DataFrame) -> str:
    cutoff = pd.to_datetime(df["cutoff_month"], errors="coerce").max() if "cutoff_month" in df else pd.NaT
    return cutoff.strftime("%Y-%m") if not pd.isna(cutoff) else pd.Timestamp.today().strftime("%Y-%m")


def risk_level(df: pd.DataFrame, p: pd.Series) -> np.ndarray:
    return np.select(
        [
            df["candidate_type"].eq("one_shot"),
            df["final_candidate_status"].eq("not_actionable") | df["probability_display_level"].eq("hidden_data_insufficient"),
            df["candidate_type"].eq("demand_shape_observation") | df["final_candidate_status"].isin(["observation_only", "low_confidence_watch"]),
            p.ge(0.75),
            p.ge(0.55),
        ],
        ["attention", "insufficient", "observation", "red", "orange"],
        default="yellow",
    )


def risk_probability_display(df: pd.DataFrame, p: pd.Series) -> np.ndarray:
    return np.select(
        [
            df["is_one_shot"],
            df["probability_display_level"].eq("probability_allowed") & p.notna(),
            df["probability_display_level"].eq("risk_band_only"),
        ],
        ["不展示", p.map(lambda x: f"{x:.0%}"), df["risk_level"]],
        default="不展示",
    )


def risk_score_display(df: pd.DataFrame, p: pd.Series) -> np.ndarray:
    score = np.clip((p.fillna(0) * 100).round(), 0, 99).astype(int).astype(str)
    return np.where(df["probability_display_level"].eq("hidden_data_insufficient") | df["is_one_shot"] | df["is_observation"], df["risk_level"], score)


def root_cause_label(df: pd.DataFrame) -> np.ndarray:
    return np.select(
        [
            df["candidate_type"].eq("one_shot"),
            df["candidate_type"].eq("demand_shape_observation"),
            df["survival_state"].astype(str).str.contains("overdue|interval", regex=True, na=False),
            pd.to_numeric(df["detector_hit_count"], errors="coerce").fillna(0).gt(0),
        ],
        ["新进终端关注", "观察对象", "采购节奏异常", "近期采购频次变化"],
        default="月度复核对象",
    )


def review_status(df: pd.DataFrame) -> np.ndarray:
    return np.select(
        [
            df["final_candidate_status"].eq("priority_review"),
            df["final_candidate_status"].eq("manual_review"),
            df["final_candidate_status"].eq("observation_only"),
            df["final_candidate_status"].eq("one_shot_attention"),
            df["final_candidate_status"].eq("not_actionable"),
        ],
        ["待处理", "待业务确认", "已标记观察", "待业务确认", "不可行动"],
        default="跟进中",
    )


def detector_card_type(name: Any) -> str:
    return {
        "terminal_loss_warning": "interval_overdue",
        "purchase_interval_overdue_warning": "interval_overdue",
        "purchase_frequency_fluctuation_warning": "frequency_drop",
        "purchase_quantity_fluctuation_warning": "quantity_drop",
        "new_terminal_detection": "one_shot_attention",
    }.get(str(name), "evidence")


def detector_metric_name(name: Any) -> str:
    return {
        "terminal_loss_warning": "距离上次采购时间",
        "purchase_interval_overdue_warning": "采购间隔偏离",
        "purchase_frequency_fluctuation_warning": "近期采购频次变化",
        "purchase_quantity_fluctuation_warning": "近期采购数量变化",
        "new_terminal_detection": "新进事实",
    }.get(str(name), "采购行为变化")


def stable_hash(value: str, length: int = 12) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()[:length]


def short_code(value: Any, length: int = 8) -> str:
    text = str(value)
    return text if len(text) <= length else text[:length]


def select_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in cols:
        if col not in out:
            out[col] = np.nan
    return out[cols]


def json_clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if not math.isfinite(float(value)):
            return None
        return float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return value


def write_sample_csvs(batch_dir: Path, tables: dict[str, pd.DataFrame]) -> None:
    tables["risk_entities"].head(500).to_csv(batch_dir / "risk_entities_sample.csv", index=False, encoding="utf-8")
    tables["risk_cards"].head(500).to_csv(batch_dir / "risk_cards_sample.csv", index=False, encoding="utf-8")
    tables["risk_card_evidence"].head(500).to_csv(batch_dir / "risk_card_evidence_sample.csv", index=False, encoding="utf-8")
