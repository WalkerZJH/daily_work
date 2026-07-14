"""Build daily detector result tables from monthly result-batch data."""

from __future__ import annotations

from typing import Any
import datetime as dt
import json
import math

import pandas as pd

from .detector_catalog import build_detector_catalog
from .detector_config import DailyDetectorConfig, load_daily_detector_config
from .detector_results import (
    DAILY_DETECTOR_CLUE_COLUMNS,
    DAILY_DETECTOR_RUN_COLUMNS,
    DETECTOR_CATALOG_COLUMNS,
    HIGH_RISK_DETECTOR_EVIDENCE_COLUMNS,
)


ROOT_CAUSE_LABELS = {
    "purchase_interval_ipi": "采购节奏异常",
    "purchase_quantity_trend": "采购量金额趋势衰减",
    "purchase_frequency_drop": "采购频次衰减",
}


def build_daily_detector_tables(
    *,
    risk_entities: pd.DataFrame,
    scan_features: pd.DataFrame,
    report_month: str,
    run_date: str | None = None,
    source_raw_batch_id: str = "",
    source_result_batch_id: str = "",
    detector_config: DailyDetectorConfig | None = None,
) -> dict[str, pd.DataFrame]:
    config = detector_config or load_daily_detector_config()
    run_date = run_date or dt.date.today().isoformat()
    created_at = dt.datetime.now(dt.UTC).isoformat()
    detector_run_id = f"{report_month}-{config.config_version}-{run_date}"
    catalog = build_detector_catalog(config)
    enabled_catalog = catalog[
        catalog["enabled_by_default"].astype(bool)
        & catalog["status"].isin(["implemented"])
        & catalog["detector_id"].isin(["purchase_interval_ipi", "purchase_quantity_trend", "purchase_frequency_drop"])
    ].copy()

    monthly_map = _monthly_entity_map(risk_entities)
    clues = _build_clues(
        scan_features,
        monthly_map,
        enabled_catalog,
        config,
        detector_run_id,
        run_date,
        created_at,
    )
    clues = _ensure_columns(clues, DAILY_DETECTOR_CLUE_COLUMNS)
    if not clues.empty:
        clues = clues.sort_values(["detector_score", "confidence"], ascending=[False, False], na_position="last").reset_index(drop=True)
        clues["display_rank"] = range(1, len(clues) + 1)

    attached = clues[clues["is_monthly_high_risk_entity"].fillna(False) & clues["hit_flag"].fillna(False)].copy()
    attached = attached[attached["risk_entity_id"].notna()]
    evidence = attached[
        [
            "risk_entity_id",
            "detector_run_id",
            "run_date",
            "detector_id",
            "detector_family",
            "detector_score",
            "confidence",
            "root_cause_label",
            "evidence_text",
            "evidence_payload",
            "caveat",
            "created_at",
        ]
    ].reset_index(drop=True)
    evidence = _ensure_columns(evidence, HIGH_RISK_DETECTOR_EVIDENCE_COLUMNS)

    runs = pd.DataFrame(
        [
            {
                "detector_run_id": detector_run_id,
                "run_date": run_date,
                "report_month": report_month,
                "source_raw_batch_id": source_raw_batch_id,
                "source_result_batch_id": source_result_batch_id,
                "detector_config_version": config.config_version,
                "enabled_detectors": ",".join(enabled_catalog["detector_id"].astype(str).tolist()),
                "scanned_entity_count": int(_scan_entity_count(scan_features)),
                "clue_count": int(len(clues)),
                # Historical column name retained for batch compatibility. It
                # now counts evidence attached to recurring candidates.
                "attached_high_risk_count": int(len(evidence)),
                "created_at": created_at,
            }
        ]
    )
    return {
        "detector_catalog": _ensure_columns(catalog, DETECTOR_CATALOG_COLUMNS),
        "daily_detector_runs": _ensure_columns(runs, DAILY_DETECTOR_RUN_COLUMNS),
        "daily_detector_clues": clues,
        "high_risk_detector_evidence": evidence,
    }


def _build_clues(
    scan_features: pd.DataFrame,
    monthly_map: dict[str, dict[str, Any]],
    enabled_catalog: pd.DataFrame,
    config: DailyDetectorConfig,
    detector_run_id: str,
    run_date: str,
    created_at: str,
) -> pd.DataFrame:
    if scan_features.empty or enabled_catalog.empty:
        return pd.DataFrame(columns=DAILY_DETECTOR_CLUE_COLUMNS)
    rows: list[dict[str, Any]] = []
    enabled_ids = set(enabled_catalog["detector_id"].astype(str))
    for row in scan_features.to_dict(orient="records"):
        if "purchase_interval_ipi" in enabled_ids:
            result = _interval_result(row, config.detectors.get("purchase_interval_ipi", {}))
            if result["detector_score"] > 0:
                rows.append(_clue_row(row, monthly_map, result, detector_run_id, run_date, created_at))
        if "purchase_quantity_trend" in enabled_ids:
            result = _quantity_result(row, config.detectors.get("purchase_quantity_trend", {}))
            if result["detector_score"] > 0:
                rows.append(_clue_row(row, monthly_map, result, detector_run_id, run_date, created_at))
        if "purchase_frequency_drop" in enabled_ids:
            result = _frequency_result(row, config.detectors.get("purchase_frequency_drop", {}))
            if result["detector_score"] > 0:
                rows.append(_clue_row(row, monthly_map, result, detector_run_id, run_date, created_at))
    return pd.DataFrame(rows)


def _interval_result(row: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    days = _num(row.get("days_since_last_purchase"), 0.0)
    median = _first_num(row, ["historical_interval_median", "median_purchase_interval_days"], 0.0)
    raw_mad = _first_num(row, ["historical_interval_mad", "mad_purchase_interval_days"], 0.0)
    mad_floor = float(cfg.get("mad_floor_days", 3) or 3)
    mad = max(raw_mad, mad_floor)
    z = max((days - median) / mad, 0.0) if median > 0 else 0.0
    z_hit = float(cfg.get("z_hit", 1.5) or 1.5)
    z_full = float(cfg.get("z_full", 3.5) or 3.5)
    score = _scaled_score(z, z_hit, z_full)
    purchase_count = _first_num(row, ["purchase_count_total", "purchase_count"], 0.0)
    confidence = min(purchase_count / float(cfg.get("confidence_n", 12) or 12), 1.0)
    hit = z >= z_hit and purchase_count >= float(cfg.get("min_purchase_count", 4) or 4)
    payload = {
        "method": "median_mad_robust_z_v1",
        "current_gap_days": days,
        "historical_median_interval_days": median,
        "historical_mad_days": raw_mad,
        "mad_floor_days": mad_floor,
        "robust_z": round(z, 4),
        "z_hit": z_hit,
        "z_full": z_full,
        "purchase_count": purchase_count,
        "min_purchase_count": float(cfg.get("min_purchase_count", 4) or 4),
    }
    return _result("purchase_interval_ipi", "interval", score, confidence, hit, payload)


def _quantity_result(row: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    ratio = _first_num(row, ["quantity_ratio", "recent_base_quantity_ratio"], math.nan)
    threshold = float(cfg.get("drop_ratio_hit", 0.6) or 0.6)
    score = 0.0 if math.isnan(ratio) else min(max((threshold - ratio) / threshold * 100.0, 0.0), 100.0)
    purchase_count = _first_num(row, ["purchase_count_total", "purchase_count"], 0.0)
    confidence = min(purchase_count / float(cfg.get("confidence_n", 6) or 6), 1.0)
    hit = not math.isnan(ratio) and ratio <= threshold
    payload = {
        "method": "simplified_ratio_v1",
        "recent_quantity": _nullable_num(row, ["recent_quantity", "recent_purchase_quantity", "quantity_recent"]),
        "baseline_quantity": _nullable_num(row, ["baseline_quantity", "base_quantity", "historical_quantity"]),
        "recent_window_months": _nullable_num(row, ["recent_window_months", "recent_month_count"]),
        "baseline_window_months": _nullable_num(row, ["baseline_window_months", "baseline_month_count"]),
        "quantity_ratio": None if math.isnan(ratio) else round(ratio, 4),
        "drop_ratio_hit": threshold,
    }
    return _result("purchase_quantity_trend", "quantity", score, confidence, hit, payload)


def _frequency_result(row: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    ratio = _first_num(row, ["frequency_ratio", "recent_base_frequency_ratio"], math.nan)
    threshold = float(cfg.get("freq_drop_ratio", 0.6) or 0.6)
    base_rate = _first_num(row, ["purchase_frequency_baseline", "baseline_frequency", "base_rate"], 0.0)
    score = 0.0 if math.isnan(ratio) else min(max((threshold - ratio) / threshold * 100.0, 0.0), 100.0)
    confidence = min(base_rate / float(cfg.get("confidence_base_rate", 2.0) or 2.0), 1.0)
    hit = not math.isnan(ratio) and ratio <= threshold and base_rate >= float(cfg.get("min_base_rate", 1.0) or 1.0)
    payload = {
        "method": "recent_base_rate_ratio_v1",
        "recent_purchase_count": _nullable_num(row, ["recent_purchase_count", "recent_order_count"]),
        "baseline_purchase_count": _nullable_num(row, ["baseline_purchase_count", "baseline_order_count"]),
        "recent_window_months": _nullable_num(row, ["recent_window_months", "recent_month_count"]),
        "baseline_window_months": _nullable_num(row, ["baseline_window_months", "baseline_month_count"]),
        "recent_frequency": _nullable_num(row, ["recent_frequency", "recent_purchase_frequency"]),
        "baseline_frequency": base_rate,
        "frequency_ratio": None if math.isnan(ratio) else round(ratio, 4),
        "freq_drop_ratio": threshold,
        "min_base_rate": float(cfg.get("min_base_rate", 1.0) or 1.0),
    }
    return _result("purchase_frequency_drop", "frequency", score, confidence, hit, payload)


def _result(detector_id: str, detector_family: str, score: float, confidence: float, hit: bool, payload: dict[str, Any]) -> dict[str, Any]:
    level = "high" if score >= 80 else "medium" if score >= 40 else "low" if score > 0 else "stable"
    return {
        "detector_id": detector_id,
        "detector_family": detector_family,
        "detector_score": round(float(score), 4),
        "detector_level": level,
        "confidence": round(float(max(min(confidence, 1.0), 0.0)), 4),
        "hit_flag": bool(hit),
        "root_cause_label": ROOT_CAUSE_LABELS[detector_id],
        "evidence_text": _evidence_text(detector_id, payload),
        "evidence_payload": json.dumps(payload, ensure_ascii=False, sort_keys=True),
        "caveat": "detector_score_is_not_probability; no causal claim",
    }


def _clue_row(
    row: dict[str, Any],
    monthly_map: dict[str, dict[str, Any]],
    result: dict[str, Any],
    detector_run_id: str,
    run_date: str,
    created_at: str,
) -> dict[str, Any]:
    key = _lookup_key(row)
    monthly = monthly_map.get(key)
    is_monthly = monthly is not None
    risk_entity_id = monthly.get("risk_entity_id") if monthly else pd.NA
    return {
        "detector_clue_id": f"{detector_run_id}|{result['detector_id']}|{key}",
        "detector_run_id": detector_run_id,
        "run_date": run_date,
        "tenant_id": str(row.get("tenant_id") or (monthly or {}).get("tenant_id") or "default_tenant"),
        "manufacturer_code": str(row.get("manufacturer_code") or ""),
        "hospital_code": str(row.get("hospital_code") or ""),
        "drug_group": str(row.get("drug_group") or row.get("drug_code") or ""),
        "is_monthly_high_risk_entity": bool(is_monthly),
        "risk_entity_id": risk_entity_id,
        "monthly_risk_probability": _monthly_value(monthly, "monthly_risk_probability") if monthly else pd.NA,
        "monthly_loss_value": _monthly_value(monthly, "monthly_loss_value") if monthly else pd.NA,
        "display_rank": 0,
        "created_at": created_at,
        **result,
    }


def _monthly_entity_map(risk_entities: pd.DataFrame) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    if risk_entities.empty:
        return mapping
    for row in risk_entities.to_dict(orient="records"):
        if str(row.get("candidate_type") or "recurring") != "recurring":
            continue
        row = dict(row)
        row["monthly_risk_probability"] = _first_num(row, ["risk_probability_value", "churn_probability_H"], math.nan)
        row["monthly_loss_value"] = _first_num(row, ["value_at_risk_H", "value_at_risk_proxy", "recent_order_amount", "avg_order_amount"], math.nan)
        for key in {str(row.get("risk_entity_id") or ""), str(row.get("candidate_id") or "")}:
            if key:
                mapping[key] = row
    return mapping


def _lookup_key(row: dict[str, Any]) -> str:
    return str(row.get("risk_entity_id") or row.get("candidate_id") or row.get("entity_id") or "")


def _monthly_value(monthly: dict[str, Any] | None, key: str) -> Any:
    if not monthly:
        return pd.NA
    value = monthly.get(key)
    if isinstance(value, float) and math.isnan(value):
        return pd.NA
    return value


def _scan_entity_count(scan_features: pd.DataFrame) -> int:
    for column in ["entity_id", "risk_entity_id", "candidate_id"]:
        if column in scan_features:
            return int(scan_features[column].astype(str).nunique())
    return int(len(scan_features))


def _evidence_text(detector_id: str, payload: dict[str, Any]) -> str:
    if detector_id == "purchase_interval_ipi":
        return "采购间隔较历史节奏拉长，需要结合近期需求计划复核。"
    if detector_id == "purchase_quantity_trend":
        return "近期采购量或金额低于历史基线，需要业务复核。"
    if detector_id == "purchase_frequency_drop":
        return "近期采购频次低于历史基线，需要业务复核。"
    return "结构化 detector 证据，需要业务复核。"


def _scaled_score(value: float, hit: float, full: float) -> float:
    if value <= hit:
        return 0.0
    if full <= hit:
        return 100.0
    return min(max((value - hit) / (full - hit) * 100.0, 0.0), 100.0)


def _first_num(row: dict[str, Any], keys: list[str], default: float) -> float:
    for key in keys:
        value = _num(row.get(key), math.nan)
        if not math.isnan(value):
            return value
    return default


def _nullable_num(row: dict[str, Any], keys: list[str]) -> float | None:
    value = _first_num(row, keys, math.nan)
    return None if math.isnan(value) else value


def _num(value: Any, default: float) -> float:
    try:
        if value is None:
            return default
        result = float(value)
        if math.isnan(result):
            return default
        return result
    except (TypeError, ValueError):
        return default


def _ensure_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = frame.copy()
    for column in columns:
        if column not in out:
            out[column] = pd.NA
    return out[columns]
