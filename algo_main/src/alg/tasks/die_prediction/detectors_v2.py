"""M4 detector completion v2 evidence enhancements.

V2 adds only two evidence detectors:

- purchase_interval_overdue_warning
- purchase_frequency_decay_rate_test

The module does not modify probabilities, business-priority scores, survival
state, M4 v1 outputs, M5/M7 outputs, or apply FDR.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DETECTOR_VERSION = "v2"
EPSILON = 1e-9
KEY_COLS = ["manufacturer_code", "hospital_code", "drug_group", "drug_group_source", "cutoff_month", "horizon"]
V2_EVIDENCE_COLUMNS = [
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
    "p_value",
    "p_value_method",
    "fdr_eligible",
    "fdr_applied",
    "fdr_status",
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


def clip(value: float | pd.Series, lower: float = 0.0, upper: float = 100.0) -> float | pd.Series:
    return np.minimum(np.maximum(value, lower), upper)


def safe_numeric(series_or_value: Any, index: pd.Index | None = None) -> pd.Series:
    if isinstance(series_or_value, pd.Series):
        return pd.to_numeric(series_or_value, errors="coerce")
    if index is None:
        return pd.Series(pd.to_numeric(series_or_value, errors="coerce"))
    return pd.to_numeric(pd.Series(series_or_value, index=index), errors="coerce")


def safe_json(values: dict[str, Any]) -> str:
    clean: dict[str, Any] = {}
    for key, value in values.items():
        if value is None:
            clean[key] = None
        elif isinstance(value, float) and math.isnan(value):
            clean[key] = None
        elif isinstance(value, (np.integer, np.floating)):
            clean[key] = float(value)
        elif isinstance(value, (np.bool_,)):
            clean[key] = bool(value)
        else:
            clean[key] = value
    return json.dumps(clean, ensure_ascii=False, sort_keys=True)


def normal_one_sided_upper_tail(z_value: float) -> float:
    if z_value is None or math.isnan(z_value):
        return math.nan
    return 0.5 * math.erfc(z_value / math.sqrt(2.0))


def conditional_binomial_rate_drop_p_value(recent_count: float, base_count: float, recent_window: float, base_window: float) -> float:
    """P(X <= recent_count | X ~ Binomial(total_count, p_recent)).

    Counts are rounded because upstream count columns are integer counts. If
    reconstruction from v1 decay evidence creates tiny floating error, rounding
    restores the original count scale.
    """
    if any(pd.isna(v) for v in [recent_count, base_count, recent_window, base_window]):
        return math.nan
    if recent_count < 0 or base_count < 0 or recent_window <= 0 or base_window <= 0:
        return math.nan
    recent = int(round(float(recent_count)))
    base = int(round(float(base_count)))
    total = recent + base
    if total <= 0:
        return math.nan
    p_recent = float(recent_window) / float(recent_window + base_window)
    try:
        from scipy.stats import binom  # type: ignore

        return float(binom.cdf(recent, total, p_recent))
    except Exception:
        return _binomial_cdf_fallback(recent, total, p_recent)


def _binomial_cdf_fallback(k: int, n: int, p: float) -> float:
    if n < 0 or k < 0:
        return math.nan
    if k >= n:
        return 1.0
    if p <= 0:
        return 1.0
    if p >= 1:
        return 1.0 if k >= n else 0.0
    log_p = math.log(p)
    log_q = math.log1p(-p)
    logs = [
        math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * log_p + (n - i) * log_q
        for i in range(k + 1)
    ]
    max_log = max(logs)
    return float(math.exp(max_log) * sum(math.exp(v - max_log) for v in logs))


def _evidence_hash(row: pd.Series) -> str:
    payload = "|".join(
        str(row.get(col, ""))
        for col in [
            "candidate_id",
            "detector_family",
            "detector_name",
            "detector_version",
            "cutoff_month",
            "horizon",
            "reason_code",
            "evidence_values",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def finalize_v2_evidence(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in V2_EVIDENCE_COLUMNS:
        if col not in out.columns:
            out[col] = np.nan
    out["detector_version"] = out["detector_version"].fillna(DETECTOR_VERSION)
    out["fdr_applied"] = False
    out["previous_evidence_id"] = np.nan
    out["evidence_timeline_reference"] = np.nan
    out["evidence_hash"] = out.apply(_evidence_hash, axis=1)
    out["evidence_id"] = out["evidence_hash"].str.slice(0, 16)
    return out[V2_EVIDENCE_COLUMNS]


def purchase_interval_overdue_warning(survival: pd.DataFrame) -> pd.DataFrame:
    work = survival.copy()
    idx = work.index
    route = work.get("demand_shape_route", pd.Series("", index=idx)).fillna("").astype(str)
    state = work.get("survival_state", pd.Series("", index=idx)).fillna("").astype(str)
    shape = work.get("demand_shape_label", pd.Series("", index=idx)).fillna("").astype(str)
    history = work.get("history_sufficiency_flag", pd.Series("", index=idx)).fillna("").astype(str)
    survival_conf = safe_numeric(work.get("survival_confidence", pd.Series(np.nan, index=idx))).fillna(0.5)
    overdue_ratio = safe_numeric(work.get("overdue_ratio", pd.Series(np.nan, index=idx)))
    months_since = safe_numeric(work.get("months_since_last_purchase", pd.Series(np.nan, index=idx)))
    expected_months = safe_numeric(work.get("expected_interval_months", pd.Series(np.nan, index=idx)))
    days_since = safe_numeric(work.get("days_since_last_purchase_asof_cutoff", pd.Series(np.nan, index=idx)))
    median_days = safe_numeric(work.get("median_purchase_interval_days_asof_cutoff", pd.Series(np.nan, index=idx)))
    mad_days = safe_numeric(work.get("purchase_interval_mad_days_asof_cutoff", pd.Series(np.nan, index=idx)))

    if days_since.isna().all() and not months_since.isna().all():
        days_since = months_since * 30.4375
    if median_days.isna().all() and not expected_months.isna().all():
        median_days = expected_months * 30.4375

    observation_only = route.eq("observation_only")
    hit = (overdue_ratio.ge(2.0) | state.isin(["materially_overdue", "likely_churn_interval"])) & ~observation_only
    severity = pd.Series(clip((overdue_ratio.fillna(0.0) / 3.0) * 100.0), index=idx, dtype="float64")
    severity.loc[state.eq("materially_overdue")] = np.maximum(severity.loc[state.eq("materially_overdue")], 60.0)
    severity.loc[state.eq("likely_churn_interval")] = np.maximum(severity.loc[state.eq("likely_churn_interval")], 80.0)
    severity.loc[~hit] = 0.0

    confidence = survival_conf.copy()
    confidence.loc[history.ne("history_sufficient")] = np.minimum(confidence.loc[history.ne("history_sufficient")], 0.6)
    confidence.loc[shape.isin(["intermittent", "lumpy"])] = np.minimum(confidence.loc[shape.isin(["intermittent", "lumpy"])], 0.6)
    confidence.loc[observation_only] = np.minimum(confidence.loc[observation_only], 0.4)

    robust_z = (days_since - median_days) / mad_days.clip(lower=EPSILON)
    mad_available = mad_days.notna() & mad_days.gt(0) & days_since.notna() & median_days.notna()
    p_value = robust_z.map(normal_one_sided_upper_tail)
    p_value.loc[~mad_available] = np.nan
    p_value_method = pd.Series("not_available_mad_missing", index=idx, dtype="object")
    p_value_method.loc[mad_available] = "robust_interval_z_normal_approx"
    fdr_eligible = mad_available
    fdr_status = pd.Series("not_ready_mad_missing", index=idx, dtype="object")
    fdr_status.loc[mad_available] = "ready_for_future_fdr"

    reason = np.where(
        observation_only,
        "observation_only_guardrail",
        np.where(hit, np.where(state.isin(["materially_overdue", "likely_churn_interval"]), state, "overdue_ratio_ge_2"), "not_overdue_enough"),
    )
    interpretation = np.where(
        observation_only,
        "该对象属于低置信需求形态，当前仅建议观察，不输出强采购节奏异常预警。",
        np.where(
            hit,
            "该医院-药品关系距离上次采购已超过其历史采购间隔，建议人工核查是否为正常采购周期延后或潜在终端流失风险。",
            "当前未达到采购节奏异常证据阈值。",
        ),
    )

    rows = work.copy()
    rows["detector_family"] = "terminal_dynamic"
    rows["detector_name"] = "purchase_interval_overdue_warning"
    rows["detector_version"] = DETECTOR_VERSION
    rows["hit_flag"] = hit
    rows["severity"] = severity
    rows["confidence"] = confidence
    rows["p_value"] = p_value
    rows["p_value_method"] = p_value_method
    rows["fdr_eligible"] = fdr_eligible
    rows["fdr_applied"] = False
    rows["fdr_status"] = fdr_status
    rows["evidence_window_start"] = ""
    rows["evidence_window_end"] = rows.get("cutoff_month", "")
    rows["evidence_fields"] = (
        "survival_state;survival_confidence;overdue_ratio;months_since_last_purchase;"
        "expected_interval_months;purchase_interval_mad_days_asof_cutoff;demand_shape_route"
    )
    rows["evidence_values"] = [
        safe_json(
            {
                "survival_state": s,
                "survival_confidence": c,
                "overdue_ratio": r,
                "months_since_last_purchase": m,
                "expected_interval_months": e,
                "days_since_last_purchase_asof_cutoff": d,
                "median_purchase_interval_days_asof_cutoff": md,
                "purchase_interval_mad_days_asof_cutoff": mad,
                "robust_z": z,
                "demand_shape_route": rt,
            }
        )
        for s, c, r, m, e, d, md, mad, z, rt in zip(
            state, confidence, overdue_ratio, months_since, expected_months, days_since, median_days, mad_days, robust_z, route
        )
    ]
    rows["reason_code"] = reason
    rows["business_interpretation"] = interpretation
    rows["human_review_required"] = hit | observation_only | confidence.lt(0.7)
    rows["data_quality_status"] = "evaluated"
    rows["data_quality_note"] = np.where(mad_available, "", "interval_mad_missing_p_value_not_available")
    return finalize_v2_evidence(rows)


def parse_v1_frequency_evidence(v1_evidence: pd.DataFrame) -> pd.DataFrame:
    if v1_evidence is None or v1_evidence.empty or "detector_name" not in v1_evidence.columns:
        return pd.DataFrame()
    rows = v1_evidence.loc[v1_evidence["detector_name"].astype(str) == "purchase_frequency_fluctuation_warning"].copy()
    if rows.empty:
        return pd.DataFrame()
    parsed: list[dict[str, Any]] = []
    for _, row in rows.iterrows():
        try:
            values = json.loads(str(row.get("evidence_values", "{}")))
        except json.JSONDecodeError:
            values = {}
        order12 = pd.to_numeric(values.get("order12"), errors="coerce")
        decay3 = pd.to_numeric(values.get("decay3"), errors="coerce")
        decay6 = pd.to_numeric(values.get("decay6"), errors="coerce")
        rec = {
            "candidate_id": row.get("candidate_id"),
            "order_count_last_12m_asof_cutoff": order12,
            "frequency_decay_3m_vs_12m": decay3,
            "frequency_decay_6m_vs_12m": decay6,
            "frequency_counts_reconstructed_from_v1": True,
        }
        if pd.notna(order12) and pd.notna(decay3):
            rec["order_count_last_3m_asof_cutoff"] = decay3 * order12 / 4.0
        if pd.notna(order12) and pd.notna(decay6):
            rec["order_count_last_6m_asof_cutoff"] = decay6 * order12 / 2.0
        parsed.append(rec)
    return pd.DataFrame(parsed).drop_duplicates("candidate_id")


def enrich_frequency_inputs(survival: pd.DataFrame, v1_evidence: pd.DataFrame | None = None) -> pd.DataFrame:
    work = survival.copy()
    parsed = parse_v1_frequency_evidence(v1_evidence if v1_evidence is not None else pd.DataFrame())
    if not parsed.empty and "candidate_id" in work.columns:
        existing = set(work.columns)
        merge_cols = ["candidate_id"] + [c for c in parsed.columns if c != "candidate_id" and c not in existing]
        # Prefer explicit survival columns if they exist; otherwise add parsed fields.
        work = work.merge(parsed[merge_cols], on="candidate_id", how="left") if len(merge_cols) > 1 else work
    if "frequency_counts_reconstructed_from_v1" not in work.columns:
        work["frequency_counts_reconstructed_from_v1"] = False
    return work


def _frequency_window_metrics(recent_count: float, recent_months: float, base_count: float, base_months: float, threshold: float) -> dict[str, Any]:
    if any(pd.isna(v) for v in [recent_count, base_count]) or base_count < 0:
        return {
            "valid": False,
            "rate_ratio": math.nan,
            "p_value": math.nan,
            "severity": 0.0,
            "hit": False,
            "reason": "invalid_or_missing_order_count_windows",
        }
    rate_recent = recent_count / recent_months
    rate_base = base_count / base_months
    rate_ratio = rate_recent / max(rate_base, EPSILON)
    p_value = conditional_binomial_rate_drop_p_value(recent_count, base_count, recent_months, base_months)
    severity = float(clip((1.0 - rate_ratio) * 100.0))
    hit = bool(rate_ratio < threshold and pd.notna(p_value) and p_value <= 0.10 and base_count >= 3)
    if hit:
        reason = "frequency_drop_statistically_supported"
    elif rate_ratio < threshold:
        reason = "frequency_drop_not_statistically_supported"
    else:
        reason = "no_frequency_rate_drop"
    return {
        "valid": True,
        "rate_ratio": float(rate_ratio),
        "p_value": float(p_value) if pd.notna(p_value) else math.nan,
        "severity": severity,
        "hit": hit,
        "reason": reason,
    }


def purchase_frequency_decay_rate_test(survival: pd.DataFrame, v1_evidence: pd.DataFrame | None = None) -> pd.DataFrame:
    work = enrich_frequency_inputs(survival, v1_evidence)
    records: list[dict[str, Any]] = []
    for _, row in work.iterrows():
        order3 = pd.to_numeric(row.get("order_count_last_3m_asof_cutoff"), errors="coerce")
        order6 = pd.to_numeric(row.get("order_count_last_6m_asof_cutoff"), errors="coerce")
        order12 = pd.to_numeric(row.get("order_count_last_12m_asof_cutoff"), errors="coerce")
        base9 = order12 - order3 if pd.notna(order12) and pd.notna(order3) else math.nan
        base6 = order12 - order6 if pd.notna(order12) and pd.notna(order6) else math.nan
        m3 = _frequency_window_metrics(order3, 3.0, base9, 9.0, 0.6)
        m6 = _frequency_window_metrics(order6, 6.0, base6, 6.0, 0.7)
        valid_metrics = [m for m in [m3, m6] if m["valid"]]
        hit_metrics = [m for m in valid_metrics if m["hit"]]

        not_evaluable = len(valid_metrics) == 0
        if hit_metrics:
            hit = True
            if m3["hit"] and m6["hit"]:
                reason = "frequency_drop_multi_window"
            elif m3["hit"]:
                reason = "frequency_drop_3m_vs_previous_9m"
            else:
                reason = "frequency_drop_6m_vs_previous_6m"
        else:
            hit = False
            reason = "not_evaluable" if not_evaluable else (
                "frequency_drop_not_statistically_supported"
                if any(m["reason"] == "frequency_drop_not_statistically_supported" for m in valid_metrics)
                else "no_frequency_rate_drop"
            )

        p_candidates = [m["p_value"] for m in valid_metrics if pd.notna(m["p_value"])]
        p_value = min(p_candidates) if p_candidates else math.nan
        severity = max([m["severity"] for m in valid_metrics], default=0.0)
        max_base = max([base9 if pd.notna(base9) else -1, base6 if pd.notna(base6) else -1])
        if max_base >= 6:
            confidence = 0.8
        elif max_base >= 3:
            confidence = 0.6
        else:
            confidence = 0.4
        shape = str(row.get("demand_shape_label", ""))
        history = str(row.get("history_sufficiency_flag", ""))
        if shape in {"intermittent", "lumpy"}:
            confidence = min(confidence, 0.5)
        if history != "history_sufficient":
            confidence = min(confidence, 0.6)

        if not_evaluable:
            data_quality_status = "not_evaluable"
            data_quality_note = "invalid_or_missing_order_count_windows"
            p_method = "not_available_missing_or_invalid_counts"
            fdr_eligible = False
            fdr_status = "not_ready_missing_counts"
            interpretation = "采购频次到达率检验所需窗口计数字段缺失或无效，当前不输出频次衰减证据。"
            severity = 0.0
        else:
            data_quality_status = "evaluated"
            extra_note = "counts_reconstructed_from_v1_decay_evidence" if bool(row.get("frequency_counts_reconstructed_from_v1", False)) else ""
            data_quality_note = extra_note
            p_method = "conditional_binomial_rate_drop_test"
            fdr_eligible = bool(p_candidates)
            fdr_status = "ready_for_future_fdr" if fdr_eligible else "not_ready_p_value_missing"
            interpretation = (
                "近期采购频次相对前期基线下降，并通过到达率检验形成辅助证据，建议结合采购周期和业务现场信息人工核查。"
                if hit
                else "当前频次下降未形成统计支持的强证据，仅作为弱观察或不命中。"
            )

        out = row.to_dict()
        out.update(
            {
                "detector_family": "sales_fluctuation",
                "detector_name": "purchase_frequency_decay_rate_test",
                "detector_version": DETECTOR_VERSION,
                "hit_flag": hit,
                "severity": severity if hit else min(severity, 39.0),
                "confidence": confidence,
                "p_value": p_value,
                "p_value_method": p_method,
                "fdr_eligible": fdr_eligible,
                "fdr_applied": False,
                "fdr_status": fdr_status,
                "evidence_window_start": "",
                "evidence_window_end": row.get("cutoff_month", ""),
                "evidence_fields": (
                    "order_count_last_3m_asof_cutoff;order_count_last_6m_asof_cutoff;"
                    "order_count_last_12m_asof_cutoff;rate_ratio_3m_vs_previous_9m;"
                    "rate_ratio_6m_vs_previous_6m;p_value"
                ),
                "evidence_values": safe_json(
                    {
                        "order_count_last_3m_asof_cutoff": order3,
                        "order_count_last_6m_asof_cutoff": order6,
                        "order_count_last_12m_asof_cutoff": order12,
                        "base_count_previous_9m": base9,
                        "base_count_previous_6m": base6,
                        "rate_ratio_3m_vs_previous_9m": m3["rate_ratio"],
                        "rate_ratio_6m_vs_previous_6m": m6["rate_ratio"],
                        "p_value_3m_vs_previous_9m": m3["p_value"],
                        "p_value_6m_vs_previous_6m": m6["p_value"],
                        "counts_reconstructed_from_v1": bool(row.get("frequency_counts_reconstructed_from_v1", False)),
                    }
                ),
                "reason_code": reason,
                "business_interpretation": interpretation,
                "human_review_required": bool(hit or confidence < 0.7),
                "data_quality_status": data_quality_status,
                "data_quality_note": data_quality_note,
            }
        )
        records.append(out)
    return finalize_v2_evidence(pd.DataFrame(records))


def family_summary(evidence: pd.DataFrame) -> pd.DataFrame:
    if evidence.empty:
        return pd.DataFrame(
            columns=[
                "detector_family",
                "detector_name",
                "detector_status",
                "input_row_count",
                "evaluated_row_count",
                "hit_count",
                "hit_rate",
                "avg_severity",
                "avg_confidence",
                "p_value_available_count",
                "fdr_eligible_count",
                "fdr_applied_count",
                "not_evaluable_count",
                "data_quality_note",
            ]
        )
    rows: list[dict[str, Any]] = []
    for (family, name), group in evidence.groupby(["detector_family", "detector_name"], dropna=False):
        evaluated = group["data_quality_status"].astype(str).ne("not_evaluable")
        hit = group["hit_flag"].astype(bool)
        rows.append(
            {
                "detector_family": family,
                "detector_name": name,
                "detector_status": "implemented",
                "input_row_count": len(group),
                "evaluated_row_count": int(evaluated.sum()),
                "hit_count": int(hit.sum()),
                "hit_rate": float(hit.mean()) if len(group) else 0.0,
                "avg_severity": float(pd.to_numeric(group["severity"], errors="coerce").mean()),
                "avg_confidence": float(pd.to_numeric(group["confidence"], errors="coerce").mean()),
                "p_value_available_count": int(group["p_value"].notna().sum()),
                "fdr_eligible_count": int(group["fdr_eligible"].astype(bool).sum()),
                "fdr_applied_count": int(group["fdr_applied"].astype(bool).sum()),
                "not_evaluable_count": int((~evaluated).sum()),
                "data_quality_note": ";".join(sorted(set(group["data_quality_note"].dropna().astype(str)) - {""})),
            }
        )
    return pd.DataFrame(rows)


def p_value_readiness_report(evidence: pd.DataFrame) -> pd.DataFrame:
    if evidence.empty:
        return pd.DataFrame(
            columns=[
                "detector_name",
                "evaluated_row_count",
                "p_value_available_count",
                "p_value_missing_count",
                "fdr_eligible_count",
                "fdr_applied_count",
                "p_value_method",
                "readiness_note",
            ]
        )
    rows: list[dict[str, Any]] = []
    for name, group in evidence.groupby("detector_name", dropna=False):
        evaluated = group["data_quality_status"].astype(str).ne("not_evaluable")
        available = group["p_value"].notna()
        methods = sorted(set(group["p_value_method"].dropna().astype(str)))
        rows.append(
            {
                "detector_name": name,
                "evaluated_row_count": int(evaluated.sum()),
                "p_value_available_count": int(available.sum()),
                "p_value_missing_count": int((~available).sum()),
                "fdr_eligible_count": int(group["fdr_eligible"].astype(bool).sum()),
                "fdr_applied_count": int(group["fdr_applied"].astype(bool).sum()),
                "p_value_method": ";".join(methods),
                "readiness_note": (
                    "ready_for_future_fdr"
                    if available.any() and group["fdr_eligible"].astype(bool).any()
                    else "partial_or_not_ready_for_fdr"
                ),
            }
        )
    return pd.DataFrame(rows)


def run_detectors_v2(survival: pd.DataFrame, v1_evidence: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    interval = purchase_interval_overdue_warning(survival)
    frequency = purchase_frequency_decay_rate_test(survival, v1_evidence)
    combined = pd.concat([interval, frequency], ignore_index=True)
    return {
        "interval": interval,
        "frequency": frequency,
        "combined": combined,
        "family_summary": family_summary(combined),
        "p_value_readiness": p_value_readiness_report(combined),
    }


__all__ = [
    "V2_EVIDENCE_COLUMNS",
    "conditional_binomial_rate_drop_p_value",
    "family_summary",
    "finalize_v2_evidence",
    "normal_one_sided_upper_tail",
    "parse_v1_frequency_evidence",
    "p_value_readiness_report",
    "purchase_frequency_decay_rate_test",
    "purchase_interval_overdue_warning",
    "run_detectors_v2",
]
