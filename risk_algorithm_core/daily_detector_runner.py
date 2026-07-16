"""Evaluate independent Daily Detector facts without monthly scoring."""

from __future__ import annotations

from typing import Any, Callable
import datetime as dt
import json
import math

import pandas as pd

from .detector_catalog import build_detector_catalog
from .detector_config import DailyDetectorConfig, load_daily_detector_config
from .detector_config_profiles import (
    build_manufacturer_config_profiles,
    build_run_config_snapshot,
    profile_payload_map,
    resolve_detector_config_profiles,
)
from .detector_results import (
    DAILY_DETECTOR_CLUE_COLUMNS,
    DAILY_DETECTOR_RESULT_COLUMNS,
    DAILY_DETECTOR_RUN_COLUMNS,
    DETECTOR_CATALOG_COLUMNS,
    HIGH_RISK_DETECTOR_EVIDENCE_COLUMNS,
)


ROOT_CAUSE_LABELS = {
    "purchase_interval_ipi": "采购节奏异常",
    "purchase_quantity_trend": "近期采购量下降",
    "purchase_quantity_spike": "近期采购量上升",
    "purchase_frequency_drop": "采购频次衰减",
    "purchase_frequency_spike": "近期采购频次上升",
    "low_price_warning": "采购单价低位提醒",
    "order_price_spread_warning": "采购价差提醒",
    "purchase_price_level_shift": "采购价格水平变化",
    "first_purchase_fact": "首次正常采购事实",
    "reactivated_purchase_fact": "恢复采购事实",
}

EVIDENCE_TEXT = {
    "purchase_interval_ipi": "当前采购间隔相对历史节奏偏长，需要业务复核。",
    "purchase_quantity_trend": "近期月均采购量低于历史基线，仅表示简单比例下降事实。",
    "purchase_quantity_spike": "近期月均采购量高于历史基线，仅表示采购量上升事实。",
    "purchase_frequency_drop": "近期月均采购频次低于历史基线，需要业务复核。",
    "purchase_frequency_spike": "近期月均采购频次高于历史基线，仅表示频次上升事实。",
    "low_price_warning": "当前直接采购单价低于同药品同单位的有效预警阈值。",
    "order_price_spread_warning": "近期同药品同单位订单价格的最大最小比超过阈值。",
    "purchase_price_level_shift": "近期直接采购单价中位数相对历史基线发生变化。",
    "first_purchase_fact": "观察日出现该实体在数据覆盖期内的首次正常完成采购。",
    "reactivated_purchase_fact": "观察日出现正常完成采购，且距此前采购超过配置静默期。",
}

DETECTOR_CAVEAT = "detector_score_is_not_probability; fact_only; no_causal_claim"


def build_daily_detector_tables(
    *,
    risk_entities: pd.DataFrame,
    scan_features: pd.DataFrame,
    report_month: str,
    run_date: str | None = None,
    source_raw_batch_id: str = "",
    source_result_batch_id: str = "",
    detector_config: DailyDetectorConfig | None = None,
    detector_ids: list[str] | None = None,
    config_profiles: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame]:
    config = detector_config or load_daily_detector_config()
    run_date = run_date or dt.date.today().isoformat()
    created_at = dt.datetime.now(dt.UTC).isoformat()
    selected_ids = detector_ids or config.runnable_detector_ids()
    unknown = sorted(set(selected_ids) - set(config.detectors))
    if unknown:
        raise ValueError(f"Unknown detector_id values: {unknown}")
    detector_run_id = _detector_run_id(report_month, run_date, config, selected_ids)
    catalog = build_detector_catalog(config)
    enabled_catalog = catalog[
        catalog["enabled_by_default"].astype(bool)
        & catalog["status"].isin(["implemented"])
        & catalog["detector_id"].isin(selected_ids)
    ].copy()
    missing_catalog = sorted(set(selected_ids) - set(enabled_catalog["detector_id"].astype(str)))
    if missing_catalog:
        raise ValueError(f"Enabled detectors are missing implemented catalog rows: {missing_catalog}")

    manufacturers = scan_features.get("manufacturer_code", pd.Series(dtype="object")).dropna().astype(str).unique()
    profiles = config_profiles
    if profiles is None:
        # Backward-compatible library use still creates explicit per-manufacturer
        # rows. The production CLI always requires a persisted profile table.
        profiles = build_manufacturer_config_profiles(
            manufacturers,
            config,
            detector_ids=selected_ids,
            created_by="in_memory_test_profile_generator",
            created_at=created_at,
        )
        profiles = profiles.copy()
        profiles["effective_from"] = "1900-01-01"

    resolved_parts: list[pd.DataFrame] = []
    missing_by_detector: dict[str, set[str]] = {}
    for detector_id in selected_ids:
        scope = str(config.detectors[detector_id].get("parameter_scope") or "manufacturer_specific")
        resolved, missing = resolve_detector_config_profiles(
            profiles,
            detector_id=detector_id,
            manufacturer_codes=manufacturers,
            observation_date=run_date,
            expected_parameter_scope=scope,
        )
        resolved_parts.append(resolved)
        missing_by_detector[detector_id] = set(missing)
    resolved_profiles = pd.concat(resolved_parts, ignore_index=True) if resolved_parts else profiles.iloc[0:0].copy()
    run_snapshot = build_run_config_snapshot(
        resolved_profiles,
        run_id=detector_run_id,
        observation_date=run_date,
        resolved_at=created_at,
    )
    results = _build_results(
        scan_features=scan_features,
        enabled_catalog=enabled_catalog,
        config=config,
        resolved_profiles=resolved_profiles,
        missing_by_detector=missing_by_detector,
        detector_run_id=detector_run_id,
        run_date=run_date,
        source_raw_batch_id=source_raw_batch_id,
        created_at=created_at,
    )
    results = _ensure_columns(results, DAILY_DETECTOR_RESULT_COLUMNS)

    monthly_map = _monthly_entity_map(risk_entities)
    clues = _build_clues_from_results(results, monthly_map, created_at)
    clues = _ensure_columns(clues, DAILY_DETECTOR_CLUE_COLUMNS)
    if not clues.empty:
        clues = clues.sort_values(
            ["detector_score", "confidence"], ascending=[False, False], na_position="last"
        ).reset_index(drop=True)
        clues["display_rank"] = range(1, len(clues) + 1)

    attached = clues[
        clues["is_monthly_high_risk_entity"].fillna(False) & clues["hit_flag"].fillna(False)
    ].copy()
    attached = attached[attached["risk_entity_id"].notna()]
    evidence = attached[
        [
            "risk_entity_id", "detector_run_id", "run_date", "detector_id", "detector_family",
            "detector_score", "confidence", "root_cause_label", "evidence_text", "evidence_payload",
            "caveat", "created_at",
        ]
    ].reset_index(drop=True)
    evidence = _ensure_columns(evidence, HIGH_RISK_DETECTOR_EVIDENCE_COLUMNS)

    runs = pd.DataFrame(
        [
            {
                "detector_run_id": detector_run_id,
                "detector_id": selected_ids[0] if len(selected_ids) == 1 else "",
                "detector_version": config.detector_version(selected_ids[0]) if len(selected_ids) == 1 else config.config_version,
                "run_date": run_date,
                "report_month": report_month,
                "source_raw_batch_id": source_raw_batch_id,
                "source_result_batch_id": source_result_batch_id,
                "detector_config_version": config.detector_version(selected_ids[0]) if len(selected_ids) == 1 else config.config_version,
                "enabled_detectors": ",".join(enabled_catalog["detector_id"].astype(str).tolist()),
                "scanned_entity_count": int(_scan_entity_count(scan_features)),
                "clue_count": int(len(clues)),
                "attached_high_risk_count": int(len(evidence)),
                "created_at": created_at,
            }
        ]
    )
    output_catalog = catalog[catalog["detector_id"].isin(selected_ids)].copy() if detector_ids is not None else catalog
    return {
        "detector_catalog": _ensure_columns(output_catalog, DETECTOR_CATALOG_COLUMNS),
        "detector_config_profiles": resolved_profiles.reset_index(drop=True),
        "detector_run_config_snapshot": run_snapshot,
        "daily_detector_runs": _ensure_columns(runs, DAILY_DETECTOR_RUN_COLUMNS),
        "daily_detector_results": results,
        "daily_detector_clues": clues,
        "high_risk_detector_evidence": evidence,
    }


def _build_results(
    *,
    scan_features: pd.DataFrame,
    enabled_catalog: pd.DataFrame,
    config: DailyDetectorConfig,
    resolved_profiles: pd.DataFrame,
    missing_by_detector: dict[str, set[str]],
    detector_run_id: str,
    run_date: str,
    source_raw_batch_id: str,
    created_at: str,
) -> pd.DataFrame:
    if scan_features.empty or enabled_catalog.empty:
        return pd.DataFrame(columns=DAILY_DETECTOR_RESULT_COLUMNS)
    evaluators: dict[str, Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]] = {
        "purchase_interval_ipi": _interval_result,
        "purchase_quantity_trend": _quantity_drop_result,
        "purchase_quantity_spike": _quantity_spike_result,
        "purchase_frequency_drop": _frequency_drop_result,
        "purchase_frequency_spike": _frequency_spike_result,
        "low_price_warning": _low_price_result,
        "order_price_spread_warning": _price_spread_result,
        "purchase_price_level_shift": _price_shift_result,
        "first_purchase_fact": _first_purchase_result,
        "reactivated_purchase_fact": _reactivated_purchase_result,
    }
    missing_evaluators = sorted(set(enabled_catalog["detector_id"].astype(str)) - set(evaluators))
    if missing_evaluators:
        raise ValueError(f"Enabled detectors have no registered evaluator: {missing_evaluators}")
    catalog_map = enabled_catalog.set_index("detector_id").to_dict(orient="index")
    payloads = profile_payload_map(resolved_profiles)
    profile_lookup = {
        (str(row.detector_id), str(row.manufacturer_code)): row
        for row in resolved_profiles.itertuples(index=False)
    }
    rows: list[dict[str, Any]] = []
    for feature in scan_features.to_dict(orient="records"):
        manufacturer = str(feature.get("manufacturer_code") or "")
        entity_key = _lookup_key(feature)
        for detector_id in enabled_catalog["detector_id"].astype(str):
            profile = profile_lookup.get((detector_id, manufacturer))
            if profile is None or manufacturer in missing_by_detector.get(detector_id, set()):
                evaluation = _inapplicable(
                    detector_id,
                    catalog_map[detector_id]["detector_family"],
                    "config_missing",
                    "config_missing",
                )
                config_id = ""
                config_hash = ""
                detector_version = config.detector_version(detector_id)
            else:
                evaluation = evaluators[detector_id](feature, payloads[str(profile.config_id)])
                config_id = str(profile.config_id)
                config_hash = str(profile.config_hash)
                detector_version = str(profile.detector_version)
            result_id = f"{detector_run_id}|{detector_id}|{entity_key}|{feature.get('purchase_unit') or ''}"
            rows.append(
                {
                    "detector_result_id": result_id,
                    "run_id": detector_run_id,
                    "source_raw_batch_id": source_raw_batch_id,
                    "observation_date": run_date,
                    "manufacturer_code": manufacturer,
                    "hospital_code": str(feature.get("hospital_code") or ""),
                    "drug_code": str(feature.get("drug_group") or feature.get("drug_code") or ""),
                    "purchase_unit": feature.get("purchase_unit"),
                    "detector_family": catalog_map[detector_id]["detector_family"],
                    "detector_id": detector_id,
                    "detector_name": catalog_map[detector_id]["detector_name"],
                    "detector_version": detector_version,
                    "config_id": config_id,
                    "config_hash": config_hash,
                    "demand_shape_label": feature.get("demand_shape_label"),
                    "created_at": created_at,
                    **evaluation,
                }
            )
    return pd.DataFrame(rows)


def _build_clues_from_results(
    results: pd.DataFrame,
    monthly_map: dict[str, dict[str, Any]],
    created_at: str,
) -> pd.DataFrame:
    if results.empty:
        return pd.DataFrame(columns=DAILY_DETECTOR_CLUE_COLUMNS)
    hit_results = results.loc[results["hit_flag"].fillna(False)].copy()
    rows: list[dict[str, Any]] = []
    for result in hit_results.to_dict(orient="records"):
        key = "|".join(
            [str(result.get("manufacturer_code") or ""), str(result.get("hospital_code") or ""), str(result.get("drug_code") or "")]
        )
        monthly = monthly_map.get(key)
        rows.append(
            {
                "detector_clue_id": result["detector_result_id"],
                "detector_run_id": result["run_id"],
                "run_date": result["observation_date"],
                "tenant_id": str((monthly or {}).get("tenant_id") or "default_tenant"),
                "manufacturer_code": result["manufacturer_code"],
                "hospital_code": result["hospital_code"],
                "drug_group": result["drug_code"],
                "detector_id": result["detector_id"],
                "detector_family": result["detector_family"],
                "detector_name": result["detector_name"],
                "detector_version": result["detector_version"],
                "config_id": result["config_id"],
                "config_hash": result["config_hash"],
                "detector_score": _score_from_result(result),
                "detector_level": result["severity"],
                "confidence": result["confidence"],
                "hit_flag": True,
                "root_cause_label": ROOT_CAUSE_LABELS[result["detector_id"]],
                "evidence_text": result["evidence_text"],
                "evidence_payload": result["evidence_payload"],
                "is_monthly_high_risk_entity": bool(monthly is not None),
                "risk_entity_id": (monthly or {}).get("risk_entity_id", pd.NA),
                "monthly_risk_probability": _monthly_value(monthly, "monthly_risk_probability"),
                "monthly_loss_value": _monthly_value(monthly, "monthly_loss_value"),
                "display_rank": 0,
                "caveat": result["caveat"],
                "created_at": created_at,
            }
        )
    return pd.DataFrame(rows)


def _interval_result(row: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    days = _num(row.get("days_since_last_purchase"), 0.0)
    median = _first_num(row, ["historical_interval_median", "median_purchase_interval_days"], 0.0)
    raw_mad = _first_num(row, ["historical_interval_mad", "mad_purchase_interval_days"], 0.0)
    mad_floor = float(cfg.get("mad_floor_days", 3) or 3)
    mad = max(raw_mad, mad_floor)
    z = max((days - median) / mad, 0.0) if median > 0 else 0.0
    threshold = float(cfg.get("z_hit", 1.5) or 1.5)
    full = float(cfg.get("z_full", 3.5) or 3.5)
    purchase_count = _first_num(row, ["purchase_count_total", "purchase_count"], 0.0)
    minimum = float(cfg.get("min_purchase_count", 4) or 4)
    payload = {
        "method": "median_mad_robust_z_v1", "current_gap_days": days,
        "historical_median_interval_days": median, "historical_mad_days": raw_mad,
        "mad_floor_days": mad_floor, "robust_z": round(z, 4), "effective_z_hit": threshold,
        "purchase_count": purchase_count, "effective_min_purchase_count": minimum,
    }
    if median <= 0 or purchase_count < minimum:
        return _inapplicable_with_payload("purchase_interval_ipi", "interval", "insufficient_history", payload)
    hit = z >= threshold
    return _applicable(
        "purchase_interval_ipi", "interval", hit, _scaled_score(z, threshold, full),
        min(purchase_count / float(cfg.get("confidence_n", 12) or 12), 1.0),
        current=days, baseline=median, comparison=z, threshold=threshold, operator=">=",
        window_start=row.get("data_history_start"), window_end=row.get("observation_date"), payload=payload,
    )


def _quantity_drop_result(row: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    ratio = _first_num(row, ["quantity_ratio", "recent_base_quantity_ratio"], math.nan)
    base_threshold = float(cfg.get("drop_ratio_hit", 0.6) or 0.6)
    modifier = _shape_modifier(row, cfg)
    threshold = base_threshold * modifier
    baseline = _first_num(row, ["baseline_quantity"], math.nan)
    minimum = float(cfg.get("min_baseline_quantity", 1) or 1)
    payload = _quantity_payload(row, ratio, base_threshold, modifier, threshold)
    payload["method"] = "simplified_ratio_v1"
    if math.isnan(ratio) or (not math.isnan(baseline) and baseline < minimum):
        return _inapplicable_with_payload("purchase_quantity_trend", "quantity", "insufficient_history", payload)
    hit = ratio <= threshold
    score = max((threshold - ratio) / max(threshold, 1e-9) * 100.0, 0.0)
    return _applicable(
        "purchase_quantity_trend", "quantity", hit, score, _sample_confidence(row, cfg),
        current=_nullable_num(row, ["recent_quantity"]), baseline=baseline, comparison=ratio,
        threshold=threshold, operator="<=", window_start=row.get("baseline_window_start"),
        window_end=row.get("recent_window_end"), payload=payload,
    )


def _quantity_spike_result(row: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    ratio = _first_num(row, ["quantity_ratio"], math.nan)
    base_threshold = float(cfg.get("spike_ratio_hit", 3.0) or 3.0)
    modifier = _shape_modifier(row, cfg)
    threshold = base_threshold * modifier
    baseline = _first_num(row, ["baseline_quantity"], math.nan)
    minimum = float(cfg.get("min_baseline_quantity", 1) or 1)
    payload = _quantity_payload(row, ratio, base_threshold, modifier, threshold)
    payload["method"] = "recent_base_quantity_ratio_v1"
    if math.isnan(ratio) or (not math.isnan(baseline) and baseline < minimum):
        return _inapplicable_with_payload("purchase_quantity_spike", "quantity", "insufficient_history", payload)
    hit = ratio >= threshold
    score = max((ratio / max(threshold, 1e-9) - 1.0) * 100.0, 0.0)
    return _applicable(
        "purchase_quantity_spike", "quantity", hit, score, _sample_confidence(row, cfg),
        current=_nullable_num(row, ["recent_quantity"]), baseline=baseline, comparison=ratio,
        threshold=threshold, operator=">=", window_start=row.get("baseline_window_start"),
        window_end=row.get("recent_window_end"), payload=payload,
    )


def _frequency_drop_result(row: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    return _frequency_result(row, cfg, detector_id="purchase_frequency_drop", direction="drop")


def _frequency_spike_result(row: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    return _frequency_result(row, cfg, detector_id="purchase_frequency_spike", direction="spike")


def _frequency_result(
    row: dict[str, Any], cfg: dict[str, Any], *, detector_id: str, direction: str
) -> dict[str, Any]:
    ratio = _first_num(row, ["frequency_ratio", "recent_base_frequency_ratio"], math.nan)
    key = "freq_drop_ratio" if direction == "drop" else "freq_spike_ratio"
    default = 0.6 if direction == "drop" else 2.0
    base_threshold = float(cfg.get(key, default) or default)
    modifier = _shape_modifier(row, cfg)
    threshold = base_threshold * modifier
    baseline = _first_num(row, ["purchase_frequency_baseline", "baseline_frequency"], 0.0)
    minimum = float(cfg.get("min_base_rate", 1.0) or 1.0)
    payload = {
        "method": "recent_base_frequency_ratio_v1",
        "recent_order_count": _nullable_num(row, ["recent_order_count", "recent_purchase_count"]),
        "baseline_order_count": _nullable_num(row, ["baseline_order_count", "baseline_purchase_count"]),
        "recent_frequency": _nullable_num(row, ["recent_frequency"]),
        "baseline_frequency": baseline,
        "frequency_ratio": None if math.isnan(ratio) else round(ratio, 4),
        "base_threshold": base_threshold,
        "shape_modifier": modifier,
        "effective_threshold": threshold,
        "effective_min_base_frequency": minimum,
    }
    if math.isnan(ratio) or baseline < minimum:
        return _inapplicable_with_payload(detector_id, "frequency", "insufficient_history", payload)
    hit = ratio <= threshold if direction == "drop" else ratio >= threshold
    score = (
        max((threshold - ratio) / max(threshold, 1e-9) * 100.0, 0.0)
        if direction == "drop"
        else max((ratio / max(threshold, 1e-9) - 1.0) * 100.0, 0.0)
    )
    return _applicable(
        detector_id, "frequency", hit, score,
        min(baseline / float(cfg.get("confidence_base_rate", 2.0) or 2.0), 1.0),
        current=_nullable_num(row, ["recent_frequency"]), baseline=baseline, comparison=ratio,
        threshold=threshold, operator="<=" if direction == "drop" else ">=",
        window_start=row.get("baseline_window_start"), window_end=row.get("recent_window_end"), payload=payload,
    )


def _low_price_result(row: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    current = _num(row.get("current_unit_price"), math.nan)
    unit = str(row.get("purchase_unit") or "")
    drug = str(row.get("drug_group") or row.get("drug_code") or "")
    absolute = dict(cfg.get("absolute_warning_prices") or {})
    configured = absolute.get(f"{drug}|{unit}", absolute.get(drug))
    threshold_source = "configured_absolute" if configured is not None else "prior_market_p05"
    threshold = _num(configured, math.nan) if configured is not None else _num(row.get("market_reference_price"), math.nan)
    reference_orders = _num(row.get("reference_order_count"), 0.0)
    reference_hospitals = _num(row.get("reference_hospital_count"), 0.0)
    payload = {
        "method": "configured_price_or_prior_market_p05_v1", "current_unit_price": _json_num(current),
        "warning_unit_price": _json_num(threshold), "threshold_source": threshold_source,
        "reference_quantile": float(cfg.get("reference_quantile", 0.05) or 0.05),
        "reference_order_count": reference_orders, "reference_hospital_count": reference_hospitals,
        "price_deviation_ratio": _json_num(current / threshold if threshold > 0 and not math.isnan(current) else math.nan),
    }
    reason = _price_common_inapplicable_reason(row, current)
    if reason:
        return _inapplicable_with_payload("low_price_warning", "price", reason, payload)
    if configured is None and (
        reference_orders < float(cfg.get("min_reference_order_count", 30) or 30)
        or reference_hospitals < float(cfg.get("min_reference_hospital_count", 5) or 5)
    ):
        return _inapplicable_with_payload("low_price_warning", "price", "insufficient_reference", payload)
    if math.isnan(threshold) or threshold <= 0:
        return _inapplicable_with_payload("low_price_warning", "price", "threshold_missing", payload)
    hit = current < threshold
    score = max((threshold - current) / threshold * 100.0, 0.0)
    return _applicable(
        "low_price_warning", "price", hit, score, min(reference_orders / 100.0, 1.0),
        current=current, baseline=threshold, comparison=current / threshold, threshold=threshold, operator="<",
        window_start=row.get("data_history_start"), window_end=row.get("observation_date"), payload=payload,
    )


def _price_spread_result(row: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    ratio = _num(row.get("price_spread_ratio"), math.nan)
    count = _num(row.get("price_recent_order_count"), 0.0)
    threshold = float(cfg.get("spread_ratio_threshold", 1.8) or 1.8)
    payload = {
        "method": "recent_max_min_ratio_v1", "order_count": count,
        "min_price": _json_num(_num(row.get("min_price"), math.nan)),
        "max_price": _json_num(_num(row.get("max_price"), math.nan)),
        "median_price": _json_num(_num(row.get("median_price"), math.nan)),
        "price_spread_ratio": _json_num(ratio), "threshold": threshold,
        "window": [row.get("recent_window_start"), row.get("recent_window_end")],
    }
    reason = _price_common_inapplicable_reason(row, _num(row.get("median_price"), math.nan), require_current=False)
    if reason:
        return _inapplicable_with_payload("order_price_spread_warning", "price", reason, payload)
    if count < float(cfg.get("min_order_count", 2) or 2) or math.isnan(ratio):
        return _inapplicable_with_payload("order_price_spread_warning", "price", "insufficient_history", payload)
    hit = ratio >= threshold
    return _applicable(
        "order_price_spread_warning", "price", hit,
        max((ratio / threshold - 1.0) * 100.0, 0.0), min(count / 10.0, 1.0),
        current=_num(row.get("max_price"), math.nan), baseline=_num(row.get("min_price"), math.nan),
        comparison=ratio, threshold=threshold, operator=">=", window_start=row.get("recent_window_start"),
        window_end=row.get("recent_window_end"), payload=payload,
    )


def _price_shift_result(row: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    ratio = _num(row.get("price_ratio"), math.nan)
    recent = _num(row.get("recent_price"), math.nan)
    baseline = _num(row.get("baseline_price"), math.nan)
    recent_count = _num(row.get("price_recent_order_count"), 0.0)
    baseline_count = _num(row.get("price_baseline_order_count"), 0.0)
    upper = float(cfg.get("upper_ratio_threshold", 1.25) or 1.25)
    lower = float(cfg.get("lower_ratio_threshold", 0.8) or 0.8)
    direction = "up" if ratio >= upper else "down" if ratio <= lower else "stable"
    payload = {
        "method": "recent_baseline_median_ratio_v1", "recent_price": _json_num(recent),
        "baseline_price": _json_num(baseline), "price_ratio": _json_num(ratio), "direction": direction,
        "effective_upper_threshold": upper, "effective_lower_threshold": lower,
        "recent_order_count": recent_count, "baseline_order_count": baseline_count,
    }
    reason = _price_common_inapplicable_reason(row, recent, require_current=False)
    if reason:
        return _inapplicable_with_payload("purchase_price_level_shift", "price", reason, payload)
    if (
        recent_count < float(cfg.get("min_recent_order_count", 2) or 2)
        or baseline_count < float(cfg.get("min_baseline_order_count", 5) or 5)
        or math.isnan(ratio)
    ):
        return _inapplicable_with_payload("purchase_price_level_shift", "price", "insufficient_history", payload)
    hit = direction != "stable"
    threshold = upper if direction == "up" else lower
    operator = ">=" if direction == "up" else "<="
    score = abs(math.log(max(ratio, 1e-9))) * 100.0 if hit else 0.0
    return _applicable(
        "purchase_price_level_shift", "price", hit, score, min((recent_count + baseline_count) / 20.0, 1.0),
        current=recent, baseline=baseline, comparison=ratio, threshold=threshold, operator=operator,
        window_start=row.get("baseline_window_start"), window_end=row.get("recent_window_end"), payload=payload,
    )


def _first_purchase_result(row: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    observation = str(row.get("observation_date") or "")
    first_date = _date_text(row.get("first_purchase_date"))
    payload = {
        "method": "first_normal_completed_purchase_fact_v1", "first_purchase_date": first_date,
        "first_order_id": row.get("first_order_id"), "first_purchase_quantity": _json_num(_num(row.get("first_purchase_quantity"), math.nan)),
        "first_purchase_amount": _json_num(_num(row.get("first_purchase_amount"), math.nan)),
        "data_history_start": row.get("data_history_start"),
    }
    if first_date != observation:
        return _inapplicable_with_payload("first_purchase_fact", "purchase_fact", "no_first_purchase_on_observation_date", payload)
    return _applicable(
        "first_purchase_fact", "purchase_fact", True, 100.0, 1.0,
        current=1.0, baseline=math.nan, comparison=math.nan, threshold=1.0, operator="fact",
        window_start=first_date, window_end=first_date, payload=payload,
    )


def _reactivated_purchase_result(row: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    current_flag = bool(row.get("current_purchase_flag") or False)
    silence = _num(row.get("silence_days"), math.nan)
    gap = float(cfg.get("configured_gap_days", 180) or 180)
    payload = {
        "method": "normal_purchase_after_silence_v1", "current_purchase_date": row.get("observation_date") if current_flag else None,
        "previous_purchase_date": _date_text(row.get("previous_purchase_date")), "silence_days": _json_num(silence),
        "configured_gap_days": gap,
    }
    if not current_flag:
        return _inapplicable_with_payload("reactivated_purchase_fact", "purchase_fact", "no_purchase_on_observation_date", payload)
    if math.isnan(silence):
        return _inapplicable_with_payload("reactivated_purchase_fact", "purchase_fact", "no_previous_purchase", payload)
    hit = silence > gap
    return _applicable(
        "reactivated_purchase_fact", "purchase_fact", hit,
        max((silence / gap - 1.0) * 100.0, 0.0), 1.0,
        current=silence, baseline=gap, comparison=silence, threshold=gap, operator=">",
        window_start=_date_text(row.get("previous_purchase_date")), window_end=row.get("observation_date"), payload=payload,
    )


def _applicable(
    detector_id: str,
    family: str,
    hit: bool,
    score: float,
    confidence: float,
    *,
    current: Any,
    baseline: Any,
    comparison: Any,
    threshold: Any,
    operator: str,
    window_start: Any,
    window_end: Any,
    payload: dict[str, Any],
) -> dict[str, Any]:
    score = min(max(float(score), 0.0), 100.0)
    severity = "high" if score >= 80 else "medium" if score >= 40 else "low" if hit else "stable"
    return {
        "hit_flag": bool(hit), "severity": severity, "confidence": round(max(min(float(confidence), 1.0), 0.0), 4),
        "eligibility_status": "applicable", "inapplicable_reason": pd.NA,
        "evidence_window_start": window_start, "evidence_window_end": window_end,
        "current_value": _nullable_scalar(current), "baseline_value": _nullable_scalar(baseline),
        "comparison_value": _nullable_scalar(comparison), "threshold_value": _nullable_scalar(threshold),
        "threshold_operator": operator, "evidence_payload": json.dumps(
            payload, ensure_ascii=False, sort_keys=True, default=_json_default
        ),
        "evidence_text": EVIDENCE_TEXT[detector_id],
        "hit_reason": ROOT_CAUSE_LABELS[detector_id] if hit else "threshold_not_met",
        "caveat": DETECTOR_CAVEAT,
    }


def _inapplicable(detector_id: str, family: str, eligibility: str, reason: str) -> dict[str, Any]:
    return _inapplicable_with_payload(detector_id, family, reason, {"eligibility_status": eligibility, "reason": reason})


def _inapplicable_with_payload(
    detector_id: str, family: str, reason: str, payload: dict[str, Any]
) -> dict[str, Any]:
    return {
        "hit_flag": False, "severity": "not_evaluable", "confidence": pd.NA,
        "eligibility_status": reason if reason in {"config_missing", "insufficient_reference"} else "inapplicable",
        "inapplicable_reason": reason, "evidence_window_start": pd.NA, "evidence_window_end": pd.NA,
        "current_value": pd.NA, "baseline_value": pd.NA, "comparison_value": pd.NA,
        "threshold_value": pd.NA, "threshold_operator": pd.NA,
        "evidence_payload": json.dumps(payload, ensure_ascii=False, sort_keys=True, default=_json_default),
        "evidence_text": EVIDENCE_TEXT[detector_id], "hit_reason": reason, "caveat": DETECTOR_CAVEAT,
    }


def _quantity_payload(
    row: dict[str, Any], ratio: float, base_threshold: float, modifier: float, threshold: float
) -> dict[str, Any]:
    amount_ratio = _num(row.get("amount_ratio"), math.nan)
    return {
        "recent_quantity": _nullable_num(row, ["recent_quantity"]),
        "baseline_quantity": _nullable_num(row, ["baseline_quantity"]),
        "quantity_ratio": _json_num(ratio), "recent_amount": _nullable_num(row, ["recent_amount"]),
        "baseline_amount": _nullable_num(row, ["baseline_amount"]), "amount_ratio": _json_num(amount_ratio),
        "amount_direction_consistent": None if math.isnan(amount_ratio) or math.isnan(ratio) else bool((ratio <= 1) == (amount_ratio <= 1)),
        "recent_window": [row.get("recent_window_start"), row.get("recent_window_end")],
        "baseline_window": [row.get("baseline_window_start"), row.get("baseline_window_end")],
        "demand_shape_label": row.get("demand_shape_label"), "base_threshold": base_threshold,
        "shape_modifier": modifier, "effective_threshold": threshold,
    }


def _shape_modifier(row: dict[str, Any], cfg: dict[str, Any]) -> float:
    modifiers = dict(cfg.get("demand_shape_modifiers") or {})
    return float(modifiers.get(str(row.get("demand_shape_label") or "smooth"), 1.0) or 1.0)


def _sample_confidence(row: dict[str, Any], cfg: dict[str, Any]) -> float:
    count = _first_num(row, ["purchase_count_total", "purchase_count"], 0.0)
    return min(count / float(cfg.get("confidence_n", 6) or 6), 1.0)


def _price_common_inapplicable_reason(
    row: dict[str, Any], price: float, *, require_current: bool = True
) -> str | None:
    if _num(row.get("entity_purchase_unit_count"), 1.0) > 1:
        return "multiple_purchase_units_for_entity"
    if not str(row.get("purchase_unit") or ""):
        return "purchase_unit_missing"
    if require_current and not bool(row.get("current_purchase_flag") or False):
        return "no_purchase_on_observation_date"
    if math.isnan(price) or price <= 0:
        return "purchase_unit_price_missing_or_nonpositive"
    return None


def _score_from_result(result: dict[str, Any]) -> float:
    current = _num(result.get("comparison_value"), math.nan)
    threshold = _num(result.get("threshold_value"), math.nan)
    operator = str(result.get("threshold_operator") or "")
    if math.isnan(current) or math.isnan(threshold):
        return 100.0 if result.get("hit_flag") else 0.0
    if operator in {">", ">="}:
        return min(max((current / max(threshold, 1e-9) - 1.0) * 100.0, 1.0), 100.0)
    if operator in {"<", "<="}:
        return min(max((threshold - current) / max(abs(threshold), 1e-9) * 100.0, 1.0), 100.0)
    return 100.0 if result.get("hit_flag") else 0.0


def _detector_run_id(report_month: str, run_date: str, config: DailyDetectorConfig, detector_ids: list[str]) -> str:
    if len(detector_ids) == 1:
        detector_id = detector_ids[0]
        return f"{report_month}-{detector_id}-{config.detector_version(detector_id)}-{run_date}"
    return f"{report_month}-{config.config_version}-{run_date}"


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
        key = "|".join(
            [str(row.get("manufacturer_code") or ""), str(row.get("hospital_code") or ""), str(row.get("drug_group") or row.get("drug_code") or "")]
        )
        mapping[key] = row
        for legacy_key in {str(row.get("risk_entity_id") or ""), str(row.get("candidate_id") or "")}:
            if legacy_key:
                mapping[legacy_key] = row
    return mapping


def _lookup_key(row: dict[str, Any]) -> str:
    return str(row.get("entity_id") or row.get("risk_entity_id") or row.get("candidate_id") or "")


def _monthly_value(monthly: dict[str, Any] | None, key: str) -> Any:
    if not monthly:
        return pd.NA
    value = monthly.get(key)
    return pd.NA if isinstance(value, float) and math.isnan(value) else value


def _scan_entity_count(scan_features: pd.DataFrame) -> int:
    for column in ["entity_id", "risk_entity_id", "candidate_id"]:
        if column in scan_features:
            return int(scan_features[column].astype(str).nunique())
    return int(len(scan_features))


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
        if value is None or value is pd.NA:
            return default
        result = float(value)
        return default if math.isnan(result) else result
    except (TypeError, ValueError):
        return default


def _json_num(value: float) -> float | None:
    return None if math.isnan(value) else round(float(value), 6)


def _nullable_scalar(value: Any) -> Any:
    if value is None or value is pd.NA:
        return pd.NA
    if isinstance(value, float) and math.isnan(value):
        return pd.NA
    return value


def _date_text(value: Any) -> str | None:
    if value is None or value is pd.NA or pd.isna(value):
        return None
    return pd.Timestamp(value).date().isoformat()


def _json_default(value: Any) -> Any:
    if value is pd.NA or pd.isna(value):
        return None
    if isinstance(value, (pd.Timestamp, dt.datetime, dt.date)):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _ensure_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = frame.copy()
    for column in columns:
        if column not in out:
            out[column] = pd.NA
    return out[columns]
