"""M4 detector evidence prototype helpers.

Detectors produce structured evidence only. They do not modify
``churn_probability_H`` or ``relative_business_priority_score_H`` and detector
severity/confidence are not probabilities.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable

import numpy as np
import pandas as pd


DETECTOR_VERSION = "detector_v1"
KEY_COLS = ["manufacturer_code", "hospital_code", "drug_group", "drug_group_source", "cutoff_month", "horizon"]
EVIDENCE_COLUMNS = [
    "candidate_id",
    "manufacturer_code",
    "hospital_code",
    "drug_group",
    "drug_group_source",
    "cutoff_month",
    "horizon",
    "detector_family",
    "detector_name",
    "detector_version",
    "hit_flag",
    "severity",
    "confidence",
    "evidence_window_start",
    "evidence_window_end",
    "evidence_fields",
    "evidence_values",
    "reason_code",
    "business_interpretation",
    "human_review_required",
    "data_quality_status",
    "data_quality_note",
    "evidence_id",
    "evidence_hash",
    "previous_evidence_id",
    "evidence_timeline_reference",
]


def clip(value: pd.Series | float, lower: float = 0.0, upper: float = 100.0) -> pd.Series | float:
    return np.minimum(np.maximum(value, lower), upper)


def normalize_cutoff_month(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "cutoff_month" in out.columns:
        out["cutoff_month"] = pd.to_datetime(out["cutoff_month"], errors="coerce").dt.to_period("M").astype(str)
    return out


def ensure_drug_group_source(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "drug_group_source" not in out.columns:
        out["drug_group_source"] = "drug_code"
    return out


def _safe_json(values: dict[str, object]) -> str:
    clean = {}
    for key, value in values.items():
        if pd.isna(value) if not isinstance(value, (list, dict, tuple)) else False:
            clean[key] = None
        elif isinstance(value, (np.integer, np.floating)):
            clean[key] = float(value)
        else:
            clean[key] = value
    return json.dumps(clean, ensure_ascii=False, sort_keys=True)


def _evidence_hash(row: pd.Series) -> str:
    payload = "|".join(
        str(row.get(col, ""))
        for col in [
            "candidate_id",
            "detector_family",
            "detector_name",
            "cutoff_month",
            "horizon",
            "reason_code",
            "evidence_values",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def finalize_evidence(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in EVIDENCE_COLUMNS:
        if col not in out.columns:
            out[col] = np.nan
    out["detector_version"] = out["detector_version"].fillna(DETECTOR_VERSION)
    out["previous_evidence_id"] = np.nan
    out["evidence_timeline_reference"] = np.nan
    out["evidence_hash"] = out.apply(_evidence_hash, axis=1)
    out["evidence_id"] = out["evidence_hash"].str.slice(0, 16)
    return out[EVIDENCE_COLUMNS]


def enrich_with_features(survival: pd.DataFrame, features: pd.DataFrame | None) -> pd.DataFrame:
    base = normalize_cutoff_month(ensure_drug_group_source(survival))
    if features is None or features.empty:
        return base
    feat = normalize_cutoff_month(ensure_drug_group_source(features))
    join_cols = [c for c in ["manufacturer_code", "hospital_code", "drug_group", "drug_group_source", "cutoff_month"] if c in base.columns and c in feat.columns]
    keep = join_cols + [
        c
        for c in [
            "order_count_last_1m_asof_cutoff",
            "order_count_last_3m_asof_cutoff",
            "order_count_last_6m_asof_cutoff",
            "order_count_last_12m_asof_cutoff",
            "purchase_quantity_sum_last_1m_asof_cutoff",
            "purchase_quantity_sum_last_3m_asof_cutoff",
            "purchase_quantity_sum_last_6m_asof_cutoff",
            "historical_avg_monthly_quantity_asof_cutoff",
            "historical_median_monthly_quantity_asof_cutoff",
            "purchase_count_asof_cutoff",
            "active_month_count_asof_cutoff",
            "months_observed_asof_cutoff",
            "first_purchase_month",
        ]
        if c in feat.columns
    ]
    return base.merge(feat[keep].drop_duplicates(join_cols), on=join_cols, how="left") if join_cols else base


def terminal_loss_warning(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    route = work.get("demand_shape_route", pd.Series("", index=work.index)).fillna("").astype(str)
    state = work.get("survival_state", pd.Series("", index=work.index)).fillna("").astype(str)
    ratio = pd.to_numeric(work.get("overdue_ratio", pd.Series(np.nan, index=work.index)), errors="coerce")
    survival_conf = pd.to_numeric(work.get("survival_confidence", pd.Series(np.nan, index=work.index)), errors="coerce").fillna(0)
    history = work.get("history_sufficiency_flag", pd.Series("", index=work.index)).fillna("").astype(str)
    shape = work.get("demand_shape_label", pd.Series("", index=work.index)).fillna("").astype(str)
    hit = state.isin(["materially_overdue", "likely_churn_interval"]) & ~route.isin(["observation_only"])
    severity = clip((ratio.fillna(0) / 3.0) * 100)
    severity = pd.Series(severity, index=work.index, dtype="float64")
    severity.loc[state.eq("materially_overdue")] = np.maximum(severity.loc[state.eq("materially_overdue")], 60)
    severity.loc[state.eq("likely_churn_interval")] = np.maximum(severity.loc[state.eq("likely_churn_interval")], 80)
    severity.loc[~hit] = 0
    confidence = survival_conf.copy()
    confidence.loc[history.ne("history_sufficient")] = np.minimum(confidence.loc[history.ne("history_sufficient")], 0.6)
    confidence.loc[shape.isin(["intermittent", "lumpy"])] = np.minimum(confidence.loc[shape.isin(["intermittent", "lumpy"])], 0.6)
    reason = np.where(
        route.eq("observation_only"),
        "observation_only_guardrail",
        np.where(hit, state, "not_overdue_enough"),
    )
    interpretation = np.where(
        route.eq("observation_only"),
        "该对象属于低置信需求形态，当前仅建议观察，不输出强终端丢失预警。",
        np.where(
            hit,
            "该医院-药品关系距离上次采购已超过其历史采购间隔，存在终端流失风险，建议人工核查。",
            "当前未达到终端丢失预警的 interval-aware 证据阈值。",
        ),
    )
    rows = work.copy()
    rows["detector_family"] = "terminal_dynamic"
    rows["detector_name"] = "terminal_loss_warning"
    rows["hit_flag"] = hit
    rows["severity"] = severity
    rows["confidence"] = confidence
    rows["reason_code"] = reason
    rows["business_interpretation"] = interpretation
    rows["human_review_required"] = hit | route.eq("observation_only")
    rows["data_quality_status"] = "evaluated"
    rows["data_quality_note"] = ""
    rows["evidence_window_start"] = ""
    rows["evidence_window_end"] = rows.get("cutoff_month", "")
    rows["evidence_fields"] = "survival_state;survival_confidence;overdue_ratio;demand_shape_route"
    rows["evidence_values"] = [
        _safe_json(
            {
                "survival_state": s,
                "survival_confidence": c,
                "overdue_ratio": r,
                "demand_shape_route": d,
            }
        )
        for s, c, r, d in zip(state, confidence, ratio, route)
    ]
    return finalize_evidence(rows)


def _frequency_decay(work: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
    order3 = pd.to_numeric(work.get("order_count_last_3m_asof_cutoff", pd.Series(np.nan, index=work.index)), errors="coerce")
    order6 = pd.to_numeric(work.get("order_count_last_6m_asof_cutoff", pd.Series(np.nan, index=work.index)), errors="coerce")
    order12 = pd.to_numeric(work.get("order_count_last_12m_asof_cutoff", pd.Series(np.nan, index=work.index)), errors="coerce")
    hist_rate = order12 / 12.0
    decay3 = pd.to_numeric(work.get("frequency_decay_3m_vs_12m", pd.Series(np.nan, index=work.index)), errors="coerce")
    decay6 = pd.to_numeric(work.get("frequency_decay_6m_vs_12m", pd.Series(np.nan, index=work.index)), errors="coerce")
    decay3 = decay3.fillna((order3 / 3.0) / hist_rate.replace(0, np.nan))
    decay6 = decay6.fillna((order6 / 6.0) / hist_rate.replace(0, np.nan))
    return decay3, decay6, order12


def purchase_frequency_fluctuation_warning(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    decay3, decay6, order12 = _frequency_decay(work)
    missing = decay3.isna() & decay6.isna()
    hit3 = decay3.lt(0.5)
    hit6 = decay6.lt(0.6)
    hit = (hit3 | hit6) & ~missing
    sev3 = ((0.5 - decay3) / 0.5 * 100).clip(lower=0, upper=100)
    sev6 = ((0.6 - decay6) / 0.6 * 100).clip(lower=0, upper=100)
    severity = pd.concat([sev3, sev6], axis=1).max(axis=1).fillna(0)
    history = work.get("history_sufficiency_flag", pd.Series("", index=work.index)).fillna("").astype(str)
    shape = work.get("demand_shape_label", pd.Series("", index=work.index)).fillna("").astype(str)
    confidence = pd.Series(np.where(history.eq("history_sufficient"), 0.8, 0.6), index=work.index, dtype="float64")
    confidence.loc[order12.lt(3)] = np.minimum(confidence.loc[order12.lt(3)], 0.4)
    confidence.loc[shape.eq("lumpy")] = np.minimum(confidence.loc[shape.eq("lumpy")], 0.5)
    reason = np.where(
        missing,
        "frequency_fields_missing",
        np.where(hit3 & hit6, "frequency_drop_multi_window", np.where(hit3, "frequency_drop_3m", np.where(hit6, "frequency_drop_6m", "no_frequency_drop"))),
    )
    rows = work.copy()
    rows["detector_family"] = "sales_fluctuation"
    rows["detector_name"] = "purchase_frequency_fluctuation_warning"
    rows["hit_flag"] = hit
    rows["severity"] = np.where(hit, severity, 0)
    rows["confidence"] = np.where(missing, np.nan, confidence)
    rows["reason_code"] = reason
    rows["business_interpretation"] = np.where(hit, "近期采购频次相对自身历史频次明显下降。", "当前未发现稳定的采购频次下降证据。")
    rows.loc[missing, "business_interpretation"] = "频次字段缺失，当前无法评估采购频次波动。"
    rows["human_review_required"] = hit
    rows["data_quality_status"] = np.where(missing, "not_evaluable", "evaluated")
    rows["data_quality_note"] = np.where(missing, "frequency detector missing order count fields", "")
    rows["evidence_window_start"] = "last_3m_or_6m"
    rows["evidence_window_end"] = rows.get("cutoff_month", "")
    rows["evidence_fields"] = "order_count_last_3m_asof_cutoff;order_count_last_6m_asof_cutoff;order_count_last_12m_asof_cutoff;frequency_decay_3m_vs_12m;frequency_decay_6m_vs_12m"
    rows["evidence_values"] = [
        _safe_json({"decay3": d3, "decay6": d6, "order12": o12})
        for d3, d6, o12 in zip(decay3, decay6, order12)
    ]
    return finalize_evidence(rows)


def purchase_quantity_fluctuation_warning(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    q3 = pd.to_numeric(work.get("purchase_quantity_sum_last_3m_asof_cutoff", pd.Series(np.nan, index=work.index)), errors="coerce")
    recent = q3 / 3.0
    hist = pd.to_numeric(work.get("historical_avg_monthly_quantity_asof_cutoff", pd.Series(np.nan, index=work.index)), errors="coerce")
    median = pd.to_numeric(work.get("historical_median_monthly_quantity_asof_cutoff", pd.Series(np.nan, index=work.index)), errors="coerce")
    hist = hist.fillna(median)
    ratio = recent / hist.replace(0, np.nan)
    missing = ratio.isna()
    drop = ratio.lt(0.5)
    spike = ratio.gt(3.0)
    hit = (drop | spike) & ~missing
    severity_drop = ((0.5 - ratio) / 0.5 * 100).clip(lower=0, upper=100)
    severity_spike = ((ratio - 3.0) / 3.0 * 100).clip(lower=0, upper=100)
    severity = np.where(drop, severity_drop, np.where(spike, severity_spike, 0))
    purchase_count = pd.to_numeric(work.get("purchase_count_asof_cutoff", pd.Series(np.nan, index=work.index)), errors="coerce")
    shape = work.get("demand_shape_label", pd.Series("", index=work.index)).fillna("").astype(str)
    confidence = (purchase_count / 6.0).clip(lower=0, upper=0.8).fillna(0.4)
    confidence.loc[shape.eq("lumpy")] = np.minimum(confidence.loc[shape.eq("lumpy")], 0.5)
    reason = np.where(missing, "quantity_fields_missing", np.where(drop, "quantity_drop", np.where(spike, "quantity_spike", "no_quantity_fluctuation")))
    rows = work.copy()
    rows["detector_family"] = "sales_fluctuation"
    rows["detector_name"] = "purchase_quantity_fluctuation_warning"
    rows["hit_flag"] = hit
    rows["severity"] = np.where(hit, severity, 0)
    rows["confidence"] = np.where(missing, np.nan, confidence)
    rows["reason_code"] = reason
    rows["business_interpretation"] = np.where(drop, "近期采购量相对历史水平明显下降。", np.where(spike, "近期采购量相对历史水平明显上升。", "当前未发现稳定的采购量异常变化证据。"))
    rows.loc[missing, "business_interpretation"] = "数量字段缺失，当前无法评估采购量波动。"
    rows["human_review_required"] = hit
    rows["data_quality_status"] = np.where(missing, "not_evaluable", "evaluated")
    rows["data_quality_note"] = np.where(missing, "quantity detector missing recent or historical quantity fields", "")
    rows["evidence_window_start"] = "last_3m"
    rows["evidence_window_end"] = rows.get("cutoff_month", "")
    rows["evidence_fields"] = "purchase_quantity_sum_last_3m_asof_cutoff;historical_avg_monthly_quantity_asof_cutoff;historical_median_monthly_quantity_asof_cutoff"
    rows["evidence_values"] = [
        _safe_json({"recent_monthly_quantity": r, "historical_quantity": h, "recent_vs_history_ratio": q})
        for r, h, q in zip(recent, hist, ratio)
    ]
    return finalize_evidence(rows)


def new_terminal_detection(one_shot: pd.DataFrame | None) -> pd.DataFrame:
    if one_shot is None or one_shot.empty:
        return pd.DataFrame(columns=EVIDENCE_COLUMNS)
    work = ensure_drug_group_source(one_shot).copy()
    first_month = work.get("first_purchase_month", pd.Series("", index=work.index))
    hit = first_month.notna() & first_month.astype(str).ne("")
    rows = work.copy()
    rows["candidate_id"] = rows[["manufacturer_code", "hospital_code", "drug_group", "drug_group_source"]].astype(str).agg("|".join, axis=1)
    rows["cutoff_month"] = first_month
    rows["horizon"] = ""
    rows["detector_family"] = "terminal_dynamic"
    rows["detector_name"] = "new_terminal_detection"
    rows["hit_flag"] = hit
    rows["severity"] = np.where(hit, 40.0, 0.0)
    rows["confidence"] = np.where(hit, 0.6, np.nan)
    rows["reason_code"] = np.where(hit, "first_seen", "unknown_new_terminal")
    rows["business_interpretation"] = np.where(hit, "该对象为 one-shot 新进事实，仅表示首次采购记录存在，不代表 recurring 流失概率。", "缺少首次采购月份，无法判断新进事实。")
    rows["human_review_required"] = hit
    rows["data_quality_status"] = np.where(hit, "evaluated", "not_evaluable")
    rows["data_quality_note"] = "new terminal fact only; no recurring churn_probability generated"
    rows["evidence_window_start"] = first_month
    rows["evidence_window_end"] = first_month
    rows["evidence_fields"] = "first_purchase_month;one_shot_value_score"
    rows["evidence_values"] = [
        _safe_json({"first_purchase_month": m, "one_shot_value_score": v})
        for m, v in zip(first_month, work.get("one_shot_value_score", pd.Series(np.nan, index=work.index)))
    ]
    return finalize_evidence(rows)


def interface_only_detectors() -> pd.DataFrame:
    rows = []
    specs = [
        ("price_warning", "low_price_purchase_warning", "price detector interface only; reliable comparable price not available in v1"),
        ("price_warning", "order_price_spread_warning", "price detector interface only; reliable comparable price not available in v1"),
        ("delivery_response", "rejection_response_warning", "delivery response detector interface only; delivery_time/arrival_time missingness too high in v1"),
        ("delivery_response", "delayed_response_warning", "delivery response detector interface only; delivery_time/arrival_time missingness too high in v1"),
        ("delivery_response", "low_delivery_rate_warning", "delivery response detector interface only; delivery_time/arrival_time missingness too high in v1"),
    ]
    for family, name, note in specs:
        rows.append(
            {
                "candidate_id": "",
                "manufacturer_code": "",
                "hospital_code": "",
                "drug_group": "",
                "drug_group_source": "",
                "cutoff_month": "",
                "horizon": "",
                "detector_family": family,
                "detector_name": name,
                "detector_version": DETECTOR_VERSION,
                "hit_flag": False,
                "severity": np.nan,
                "confidence": np.nan,
                "evidence_window_start": "",
                "evidence_window_end": "",
                "evidence_fields": "",
                "evidence_values": "{}",
                "reason_code": "interface_only_not_evaluable",
                "business_interpretation": "当前仅保留 detector 接口，不输出有效证据。",
                "human_review_required": False,
                "data_quality_status": "not_evaluable",
                "data_quality_note": note,
            }
        )
    return finalize_evidence(pd.DataFrame(rows))


def family_summary(evidence: pd.DataFrame, input_row_count: int) -> pd.DataFrame:
    if evidence.empty:
        return pd.DataFrame()
    rows = []
    for (family, name), group in evidence.groupby(["detector_family", "detector_name"], dropna=False):
        interface = group["data_quality_status"].eq("not_evaluable").all() and len(group) <= 5 and group["candidate_id"].fillna("").eq("").all()
        status = "interface_only" if interface else ("skipped_missing_fields" if group["data_quality_status"].eq("not_evaluable").all() else "implemented")
        rows.append(
            {
                "detector_family": family,
                "detector_name": name,
                "detector_status": status,
                "input_row_count": int(input_row_count),
                "evaluated_row_count": int(group["data_quality_status"].eq("evaluated").sum()),
                "hit_count": int(group["hit_flag"].fillna(False).astype(bool).sum()),
                "hit_rate": float(group["hit_flag"].fillna(False).astype(bool).mean()) if len(group) else np.nan,
                "avg_severity": pd.to_numeric(group["severity"], errors="coerce").mean(),
                "avg_confidence": pd.to_numeric(group["confidence"], errors="coerce").mean(),
                "not_evaluable_count": int(group["data_quality_status"].eq("not_evaluable").sum()),
                "data_quality_note": "; ".join(sorted(group["data_quality_note"].dropna().astype(str).unique()))[:500],
            }
        )
    return pd.DataFrame(rows).sort_values(["detector_family", "detector_name"]).reset_index(drop=True)
