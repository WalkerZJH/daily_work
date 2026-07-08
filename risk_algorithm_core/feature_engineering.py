"""Production feature orchestration based on the verified exploration flow."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .cutoff_features import add_baseline_scores, build_source_cutoff_features, to_month_end
from .entity_month import build_fact_entity_month
from .facts import ENTITY_KEYS, build_fact_purchase_event_from_orders
from .purchase_sequence import build_entity_purchase_sequence


def engineer_features(entity_base: pd.DataFrame, orders: pd.DataFrame, cutoff_date: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build model/runtime features from raw orders using migrated source logic.

    The ``entity_base`` argument is retained for runner compatibility and
    metadata joins. The authoritative feature values come from:

    ``orders -> fact_purchase_event -> fact_entity_month -> source cutoff features``.
    """

    if orders.empty:
        return pd.DataFrame(), pd.DataFrame()

    cutoff_ts = to_month_end(cutoff_date)
    horizons = _horizons_from_entity_base(entity_base)
    purchase_events = build_fact_purchase_event_from_orders(_orders_with_master_metadata(orders, entity_base))
    entity_month = build_fact_entity_month(purchase_events)
    sequence = build_entity_purchase_sequence(purchase_events)
    cutoff_features, demand_profile, cutoff_report = build_source_cutoff_features(
        entity_month,
        [cutoff_ts],
        include_choice_context=False,
    )
    if cutoff_features.empty:
        return cutoff_features, _quality_report(0, 0, 0, 0, cutoff_report)

    expanded = cutoff_features.loc[cutoff_features.index.repeat(len(horizons))].copy().reset_index(drop=True)
    expanded["horizon"] = horizons * len(cutoff_features)
    expanded = add_baseline_scores(expanded)
    expanded["entity_id"] = (
        expanded["manufacturer_code"].astype(str)
        + "|"
        + expanded["hospital_code"].astype(str)
        + "|"
        + expanded["drug_group"].astype(str)
    )
    expanded["candidate_id"] = expanded["entity_id"].astype(str) + "|" + expanded["horizon"].astype(str)
    expanded["cutoff_month"] = pd.to_datetime(expanded["cutoff_month"], errors="coerce")
    expanded = _add_runtime_sidecar_features(expanded)
    expanded = _merge_runtime_metadata(expanded, entity_base)
    expanded = _ensure_entity_base_coverage(expanded, entity_base, cutoff_ts)

    quality = _quality_report(
        feature_rows=len(expanded),
        fact_rows=len(purchase_events),
        entity_month_rows=len(entity_month),
        sequence_rows=len(sequence),
        cutoff_report=cutoff_report,
        input_mode="raw_orders_mode",
    )
    return expanded.reset_index(drop=True), quality


def engineer_features_from_facts(
    entity_base: pd.DataFrame,
    fact_entity_month: pd.DataFrame,
    cutoff_date: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build runtime features from verified normalized monthly facts.

    This mode is used when the current workspace contains source-of-truth
    ``fact_entity_month`` outputs from the exploration flow. It avoids
    replaying order-level same-timestamp tie behavior and keeps parity anchored
    to the verified fact layer.
    """

    if fact_entity_month.empty:
        return pd.DataFrame(), pd.DataFrame()

    cutoff_ts = to_month_end(cutoff_date)
    horizons = _horizons_from_entity_base(entity_base)
    cutoff_features, demand_profile, cutoff_report = build_source_cutoff_features(
        fact_entity_month,
        [cutoff_ts],
        include_choice_context=False,
    )
    if cutoff_features.empty:
        return cutoff_features, _quality_report(0, 0, len(fact_entity_month), 0, cutoff_report, input_mode="normalized_fact_mode")

    expanded = cutoff_features.loc[cutoff_features.index.repeat(len(horizons))].copy().reset_index(drop=True)
    expanded["horizon"] = horizons * len(cutoff_features)
    expanded = add_baseline_scores(expanded)
    expanded["entity_id"] = (
        expanded["manufacturer_code"].astype(str)
        + "|"
        + expanded["hospital_code"].astype(str)
        + "|"
        + expanded["drug_group"].astype(str)
    )
    expanded["candidate_id"] = expanded["entity_id"].astype(str) + "|" + expanded["horizon"].astype(str)
    expanded["cutoff_month"] = pd.to_datetime(expanded["cutoff_month"], errors="coerce")
    expanded = _add_runtime_sidecar_features(expanded)
    expanded = _merge_runtime_metadata(expanded, entity_base)
    expanded = _ensure_entity_base_coverage(expanded, entity_base, cutoff_ts)

    quality = _quality_report(
        feature_rows=len(expanded),
        fact_rows=0,
        entity_month_rows=len(fact_entity_month),
        sequence_rows=0,
        cutoff_report=cutoff_report,
        input_mode="normalized_fact_mode",
    )
    return expanded.reset_index(drop=True), quality


def _orders_with_master_metadata(orders: pd.DataFrame, entity_base: pd.DataFrame) -> pd.DataFrame:
    out = orders.copy()
    if entity_base.empty:
        return out
    meta_cols = [
        "manufacturer_code",
        "hospital_code",
        "drug_group",
        "drug_category_code",
        "province_code",
        "city_code",
        "county_code",
        "hospital_level_code",
        "ownership_type_code",
    ]
    available = [c for c in meta_cols if c in entity_base.columns]
    if not {"manufacturer_code", "hospital_code", "drug_group"}.issubset(available):
        return out
    meta = entity_base[available].drop_duplicates(["manufacturer_code", "hospital_code", "drug_group"])
    out["drug_group"] = out.get("drug_group", out["drug_code"]).astype(str)
    out = out.merge(meta, on=["manufacturer_code", "hospital_code", "drug_group"], how="left", suffixes=("", "_entity"))
    for col in ["drug_category_code", "province_code", "city_code", "county_code", "hospital_level_code", "ownership_type_code"]:
        alt = f"{col}_entity"
        if alt in out.columns:
            if col in out.columns:
                out[col] = out[col].where(out[col].notna() & out[col].astype(str).ne(""), out[alt])
            else:
                out[col] = out[alt]
            out = out.drop(columns=[alt])
    return out


def _horizons_from_entity_base(entity_base: pd.DataFrame) -> list[str]:
    if not entity_base.empty and "horizon" in entity_base.columns:
        horizons = [str(x) for x in entity_base["horizon"].dropna().drop_duplicates().tolist()]
        if horizons:
            return horizons
    return ["H3", "H6", "H12"]


def _merge_runtime_metadata(features: pd.DataFrame, entity_base: pd.DataFrame) -> pd.DataFrame:
    if entity_base.empty:
        return _fallback_metadata(features)
    join_cols = ["manufacturer_code", "hospital_code", "drug_group", "horizon"]
    meta_cols = [
        "manufacturer_code",
        "hospital_code",
        "drug_group",
        "horizon",
        "hospital_display_name",
        "drug_display_name",
        "region_code",
        "region_display_name",
        "hospital_level",
        "product_line_code",
        "product_line_display_name",
    ]
    available = [c for c in meta_cols if c in entity_base.columns]
    if not set(join_cols).issubset(available):
        return _fallback_metadata(features)
    meta = entity_base[available].drop_duplicates(join_cols)
    out = features.merge(meta, on=join_cols, how="left")
    return _fallback_metadata(out)


def _ensure_entity_base_coverage(features: pd.DataFrame, entity_base: pd.DataFrame, cutoff_ts: pd.Timestamp) -> pd.DataFrame:
    join_cols = ["manufacturer_code", "hospital_code", "drug_group", "horizon"]
    if entity_base.empty or not set(join_cols).issubset(entity_base.columns):
        return features

    base = entity_base.drop_duplicates(join_cols).copy()
    existing = features[join_cols].drop_duplicates() if set(join_cols).issubset(features.columns) else pd.DataFrame(columns=join_cols)
    missing = base.merge(existing.assign(_present=True), on=join_cols, how="left")
    missing = missing[missing["_present"].isna()].drop(columns=["_present"])
    if missing.empty:
        return features

    rows = pd.DataFrame(index=missing.index, columns=features.columns)
    for col in missing.columns:
        if col in rows.columns:
            rows[col] = missing[col].to_numpy()
    rows["cutoff_month"] = cutoff_ts
    rows["entity_id"] = (
        rows["manufacturer_code"].astype(str)
        + "|"
        + rows["hospital_code"].astype(str)
        + "|"
        + rows["drug_group"].astype(str)
    )
    rows["candidate_id"] = rows["entity_id"].astype(str) + "|" + rows["horizon"].astype(str)
    for col in ["purchase_count_asof_cutoff", "active_month_count_asof_cutoff", "months_observed_asof_cutoff"]:
        if col in rows.columns:
            rows[col] = pd.to_numeric(rows[col], errors="coerce").fillna(0)
    for col in ["one_shot_flag", "is_one_shot"]:
        if col in rows.columns:
            rows[col] = rows[col].where(rows[col].notna(), False).astype(bool)
    rows = _fallback_metadata(rows).dropna(axis=1, how="all")
    return pd.concat([features, rows], ignore_index=True)


def _fallback_metadata(features: pd.DataFrame) -> pd.DataFrame:
    out = features.copy()
    out["hospital_display_name"] = out.get("hospital_display_name", out["hospital_code"]).fillna(out["hospital_code"]).astype(str)
    out["drug_display_name"] = out.get("drug_display_name", out["drug_group"]).fillna(out["drug_group"]).astype(str)
    out["region_code"] = out.get("region_code", out.get("province_code", "")).fillna("").astype(str)
    out["region_display_name"] = out.get("region_display_name", out["region_code"]).fillna("").astype(str)
    return out


def _add_runtime_sidecar_features(features: pd.DataFrame) -> pd.DataFrame:
    out = features.copy()
    recent_3 = pd.to_numeric(out.get("order_count_last_3m_asof_cutoff"), errors="coerce") / 3.0
    recent_12 = pd.to_numeric(out.get("order_count_last_12m_asof_cutoff"), errors="coerce") / 12.0
    out["purchase_frequency_recent"] = recent_3
    out["purchase_frequency_baseline"] = recent_12
    out["frequency_ratio"] = (recent_3 / recent_12.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
    q_recent = pd.to_numeric(out.get("purchase_quantity_sum_last_3m_asof_cutoff"), errors="coerce")
    q_12 = pd.to_numeric(out.get("purchase_quantity_sum_last_12m_asof_cutoff"), errors="coerce")
    q_baseline = q_12 / 4.0
    out["purchase_quantity_recent"] = q_recent
    out["purchase_quantity_baseline"] = q_baseline
    out["quantity_ratio"] = (q_recent / q_baseline.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
    horizon_num = pd.to_numeric(out["horizon"].astype(str).str.replace("H", "", regex=False), errors="coerce").fillna(6)
    out["value_at_risk_proxy"] = out["historical_avg_monthly_amount_asof_cutoff"].fillna(0) * horizon_num
    if out["value_at_risk_proxy"].nunique(dropna=True) >= 3:
        out["potential_value_level"] = pd.cut(
            out["value_at_risk_proxy"].rank(method="average", pct=True),
            bins=[-0.01, 0.5, 0.8, 1.0],
            labels=["low", "medium", "high"],
        ).astype(str)
    else:
        out["potential_value_level"] = "unknown"
    out["is_one_shot"] = out["one_shot_flag"].fillna(False).astype(bool)
    out["one_shot_attention_score"] = np.where(out["is_one_shot"], out["value_at_risk_proxy"].rank(pct=True), 0.0)
    out["probability_display_level"] = np.select(
        [
            out["history_sufficiency_flag"].eq("history_insufficient"),
            out["history_sufficiency_flag"].eq("history_sufficient"),
        ],
        ["hidden_data_insufficient", "probability_allowed"],
        default="risk_band_only",
    )
    out["display_mode"] = np.select(
        [
            out["probability_display_level"].eq("probability_allowed"),
            out["probability_display_level"].eq("hidden_data_insufficient"),
        ],
        ["show_probability", "hide_probability"],
        default="show_risk_band",
    )
    return out


def _quality_report(
    feature_rows: int,
    fact_rows: int,
    entity_month_rows: int,
    sequence_rows: int,
    cutoff_report: pd.DataFrame,
    input_mode: str,
) -> pd.DataFrame:
    rows = [
        {"metric": "runtime_input_mode", "value": input_mode},
        {"metric": "feature_rows", "value": feature_rows},
        {"metric": "source_truth_feature_rows", "value": feature_rows},
        {"metric": "fact_purchase_event_rows", "value": fact_rows},
        {"metric": "fact_entity_month_rows", "value": entity_month_rows},
        {"metric": "entity_purchase_sequence_rows", "value": sequence_rows},
    ]
    if not cutoff_report.empty:
        for col in ["all_seen_entity_count", "monitorable_entity_count", "excluded_by_monitor_gap_count"]:
            if col in cutoff_report:
                rows.append({"metric": col, "value": int(pd.to_numeric(cutoff_report[col], errors="coerce").fillna(0).sum())})
    return pd.DataFrame(rows)
