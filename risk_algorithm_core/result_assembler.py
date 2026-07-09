"""Assemble standard monthly risk_result_batch outputs."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import datetime as dt

import pandas as pd

from risk_result_contracts import validate_result_batch, write_manifest
from .daily_detector_runner import build_daily_detector_tables
from .entity_display_lookup import ENTITY_DISPLAY_LOOKUP_SCHEMA_VERSION, build_entity_display_lookup


def assemble_result_batch(
    output_root: str | Path,
    run_id: str,
    report_month: str,
    cutoff_date: str,
    raw_batch_id: str,
    model_artifact_id: str,
    primary_horizon: str,
    available_horizons: list[str],
    candidate_status: pd.DataFrame,
    risk_cards: pd.DataFrame,
    risk_card_evidence: pd.DataFrame,
    feature_frame: pd.DataFrame,
    worklist_config: dict[str, Any],
    score_frame: pd.DataFrame | None = None,
    normalized_tables: dict[str, pd.DataFrame] | None = None,
    artifact_metadata: dict[str, Any] | None = None,
    write_parquet: bool = True,
) -> Path:
    batch_id = f"{report_month}-monthly-risk-algorithm-{run_id}"
    batch_dir = Path(output_root) / f"report_month={report_month}" / f"batch_id={batch_id}"
    batch_dir.mkdir(parents=True, exist_ok=True)

    risk_entities = _build_risk_entities(candidate_status, report_month)
    timeline = _build_timeline(risk_entities, feature_frame)
    hospital_aggregates = _build_hospital_aggregates(risk_entities)
    drug_aggregates = _build_drug_aggregates(risk_entities)
    monthly_reports = _build_monthly_reports(report_month, risk_entities)
    proof_cases = pd.DataFrame(columns=["proof_case_id", "risk_entity_id", "candidate_id", "proof_status"])
    work_order_reserved = _build_work_order_reserved(risk_entities)
    entity_display_lookup = build_entity_display_lookup(
        risk_entities,
        normalized_tables or {},
        report_month,
        raw_batch_id,
    )
    detector_tables = build_daily_detector_tables(
        risk_entities=risk_entities,
        scan_features=feature_frame,
        report_month=report_month,
        run_date=dt.date.today().isoformat(),
        source_raw_batch_id=raw_batch_id,
        source_result_batch_id=batch_id,
    )
    horizon_profiles = _build_risk_entity_horizon_profiles(
        risk_entities,
        candidate_status,
        feature_frame,
        report_month,
        available_horizons,
        score_frame=score_frame,
        high_risk_detector_evidence=detector_tables.get("high_risk_detector_evidence"),
    )

    tables = {
        "risk_entities": risk_entities,
        "risk_entity_horizon_profiles": horizon_profiles,
        "risk_cards": risk_cards,
        "risk_card_evidence": risk_card_evidence,
        "risk_entity_timeline": timeline,
        "hospital_aggregates": hospital_aggregates,
        "drug_aggregates": drug_aggregates,
        "monthly_reports": monthly_reports,
        "proof_cases": proof_cases,
        "work_order_reserved": work_order_reserved,
        "entity_display_lookup": entity_display_lookup,
        **detector_tables,
    }
    data_backend = _write_tables(batch_dir, tables, write_parquet)
    artifact_metadata = artifact_metadata or {}
    manifest = {
        "batch_id": batch_id,
        "result_batch_id": batch_id,
        "report_type": "monthly",
        "report_month": report_month,
        "report_date": dt.date.today().isoformat(),
        "run_date": dt.date.today().isoformat(),
        "score_as_of_date": cutoff_date,
        "score_cutoff_month": report_month,
        "cutoff_date": cutoff_date,
        "primary_horizon": primary_horizon,
        "available_horizons": available_horizons,
        "schema_version": "risk_result_batch_monthly_v2",
        "data_backend": data_backend,
        "raw_batch_id": raw_batch_id,
        "algorithm_core_version": "risk_algorithm_core_v1",
        "model_artifact_id": model_artifact_id,
        "model_family": artifact_metadata.get("model_family", "unknown"),
        "feature_group": artifact_metadata.get("feature_group", "unknown"),
        "calibration": artifact_metadata.get("calibration", artifact_metadata.get("probability_calibration", "raw")),
        "excludes_choice_set": bool(artifact_metadata.get("excludes_choice_set", True)),
        "risk_result_schema_version": "risk_result_batch_monthly_v2",
        "horizon_profile_table": {
            "table_name": "risk_entity_horizon_profiles",
            "schema_version": "risk_entity_horizon_profile_v1",
            "path": f"risk_entity_horizon_profiles.{data_backend}",
            "row_count": int(len(horizon_profiles)),
            "involved_amount_definition": "purchase_amount_sum_last_{horizon_months}m_asof_cutoff",
        },
        "feature_schema_version": artifact_metadata.get("feature_schema_version", "production_features_v1"),
        "detector_config_version": "daily_detector_rules_v1",
        "detector_tables": {
            "detector_catalog": f"detector_catalog.{data_backend}",
            "daily_detector_runs": f"daily_detector_runs.{data_backend}",
            "daily_detector_clues": f"daily_detector_clues.{data_backend}",
            "high_risk_detector_evidence": f"high_risk_detector_evidence.{data_backend}",
        },
        "detector_score_probability_interpretation": "detector_score_is_not_probability",
        "detector_default_scope": "monthly_high_risk_entities",
        "worklist_config": worklist_config,
        "allowed_usage": ["internal_diagnostic", "analyst_view", "monthly_business_review"],
        "forbidden_usage": ["auto_dispatch", "formal_customer_probability_service", "definitive_churn_claim"],
        "customer_facing_probability_service_allowed": False,
        "auto_dispatch_allowed": False,
        "proof_case_report_allowed": False,
        "raw_orders_mode_ready": False,
        "fact_mode_ready": True,
        "conditional_fact_mode_ready": True,
        "readiness_level": "conditional_fact_mode_ready",
        "deprecated_frontend_fields": {
            "business_score": "not emitted by model-core customer payloads; downstream display must use horizon profile involved_amount and probability fields",
            "fill_policy": "removed from model-core payloads; user-scope selection is a backend responsibility",
        },
        "result_table_row_counts": {name: int(len(df)) for name, df in tables.items()},
        "entity_display_lookup": {
            "table_name": "entity_display_lookup",
            "schema_version": ENTITY_DISPLAY_LOOKUP_SCHEMA_VERSION,
            "path": f"entity_display_lookup.{data_backend}",
            "row_count": int(len(entity_display_lookup)),
        },
        "caveats": [
            "bounded monthly worklist",
            "not full SQL universe claim",
            "business review required",
            "raw_orders_mode_ready=false; current formal readiness is conditional_fact_mode_ready",
        ],
    }
    write_manifest(batch_dir, manifest)
    validate_result_batch(batch_dir)
    return batch_dir


def _build_risk_entities(status: pd.DataFrame, report_month: str) -> pd.DataFrame:
    out = pd.DataFrame()
    out["risk_entity_id"] = status["candidate_id"].astype(str)
    out["candidate_id"] = status["candidate_id"].astype(str)
    out["entity_id"] = status.get("entity_id", status["candidate_id"].astype(str).str.replace(r"\|H\d+$", "", regex=True)).astype(str)
    out["tenant_id"] = status.get("tenant_id", "default_tenant")
    out["enterprise_id"] = status.get("enterprise_id", "default_enterprise")
    out["manufacturer_code"] = status["manufacturer_code"].astype(str)
    out["manufacturer_display_name"] = status["manufacturer_code"].astype(str)
    out["hospital_code"] = status["hospital_code"].astype(str)
    out["hospital_display_name"] = status.get("hospital_display_name", status["hospital_code"]).fillna(status["hospital_code"]).astype(str)
    out["drug_code"] = status["drug_group"].astype(str)
    out["drug_group"] = status["drug_group"].astype(str)
    out["drug_group_source"] = status.get("drug_group_source", "drug_code")
    out["drug_display_name"] = status.get("drug_display_name", status["drug_group"]).fillna(status["drug_group"]).astype(str)
    out["report_month"] = report_month
    out["cutoff_month"] = status["cutoff_month"].astype(str)
    out["primary_horizon"] = status["horizon"].astype(str)
    out["risk_probability_display"] = status.apply(lambda r: "hidden" if bool(r["is_one_shot"]) or bool(r["is_observation"]) else "risk band", axis=1)
    out["risk_probability_value"] = status["churn_probability_H"].where(~status["is_one_shot"] & ~status["is_observation"], pd.NA)
    out["probability_display_mode"] = status["probability_display_mode"]
    out["risk_level"] = status["risk_level"]
    out["risk_color"] = status["risk_color"]
    out["risk_score_display"] = status["risk_score"].round(4).astype(str)
    out["palive_display"] = "hidden"
    out["palive_display_mode"] = "derived_from_churn_probability_hidden_unless_allowed"
    out["value_at_risk_display"] = status.get("potential_value_level", "relative")
    out["potential_value_level"] = status.get("potential_value_level", "unknown")
    out["business_priority_display"] = "relative"
    out["main_reason_summary"] = status["selection_reason"]
    out["risk_type_label"] = status["selection_reason"]
    out["region_code"] = status.get("region_code", "")
    out["region_display_name"] = status.get("region_display_name", "")
    out["review_status"] = status["final_candidate_status"]
    out["final_candidate_status"] = status["final_candidate_status"]
    out["review_priority"] = status["review_priority"]
    out["evidence_strength"] = status["evidence_strength"]
    out["risk_card_count"] = 0
    out["has_work_order"] = False
    out["is_high_risk"] = status["is_high_risk"].astype(bool)
    out["is_observation"] = status["is_observation"].astype(bool)
    out["is_one_shot"] = status["is_one_shot"].astype(bool)
    out["is_probability_allowed"] = False
    out["user_visible_caveat"] = status["selection_caveat"]
    out["suggested_action_short"] = status["candidate_type"].map(
        {
            "recurring": "Review purchasing context",
            "one_shot": "Check second-purchase opportunity",
            "observation": "Continue monitoring",
            "demand_shape_observation": "Continue monitoring",
        }
    ).fillna("Manual review")
    out["auto_dispatch_allowed"] = False
    out["created_at"] = dt.datetime.now(dt.UTC).isoformat()
    return out


def _build_risk_entity_horizon_profiles(
    risk_entities: pd.DataFrame,
    status: pd.DataFrame,
    feature_frame: pd.DataFrame,
    report_month: str,
    available_horizons: list[str],
    *,
    score_frame: pd.DataFrame | None = None,
    high_risk_detector_evidence: pd.DataFrame | None = None,
) -> pd.DataFrame:
    columns = [
        "risk_entity_id",
        "candidate_id",
        "entity_id",
        "report_month",
        "horizon",
        "risk_probability",
        "involved_amount",
        "involved_amount_source",
        "risk_level",
        "risk_band",
        "main_reason_summary",
        "reason",
        "detector_evidence_count",
        "updated_at",
    ]
    if risk_entities.empty:
        return pd.DataFrame(columns=columns)

    status_source = _with_entity_horizon(status)
    feature_source = _with_entity_horizon(feature_frame)
    score_source = _with_entity_horizon(score_frame if score_frame is not None else pd.DataFrame())
    evidence_counts = _detector_evidence_counts(high_risk_detector_evidence)
    updated_at = dt.datetime.now(dt.UTC).isoformat()
    rows: list[dict[str, Any]] = []
    horizons = [str(h) for h in available_horizons] or ["H3", "H6", "H12"]

    for _, entity in risk_entities.iterrows():
        risk_entity_id = str(entity["risk_entity_id"])
        entity_id = _base_entity_id(entity)
        primary_horizon = str(entity.get("primary_horizon") or entity.get("horizon") or "")
        hide_probability = bool(entity.get("is_one_shot", False)) or bool(entity.get("is_observation", False))
        for horizon in horizons:
            status_row = _first_profile_row(status_source, entity_id, horizon)
            feature_row = _first_profile_row(feature_source, entity_id, horizon)
            score_row = _first_profile_row(score_source, entity_id, horizon)
            probability = pd.NA if hide_probability else _profile_probability(score_row, status_row, entity, horizon, primary_horizon)
            involved_amount, involved_source = _profile_involved_amount(feature_row, status_row, horizon)
            risk_level = _profile_text(status_row, ["risk_level"]) or (
                _text(entity.get("risk_level")) if horizon == primary_horizon else _risk_level_from_probability(probability)
            )
            risk_band = _profile_text(status_row, ["risk_band"]) or _risk_band_from_level(risk_level)
            reason = (
                _profile_text(status_row, ["main_reason_summary", "selection_reason", "risk_type_label"])
                or _text(entity.get("main_reason_summary"))
                or "Monthly result-batch horizon profile."
            )
            rows.append(
                {
                    "risk_entity_id": risk_entity_id,
                    "candidate_id": _profile_text(status_row, ["candidate_id"]) or f"{entity_id}|{horizon}",
                    "entity_id": entity_id,
                    "report_month": report_month,
                    "horizon": horizon,
                    "risk_probability": probability,
                    "involved_amount": involved_amount,
                    "involved_amount_source": involved_source,
                    "risk_level": risk_level,
                    "risk_band": risk_band,
                    "main_reason_summary": reason,
                    "reason": reason,
                    "detector_evidence_count": int(evidence_counts.get(risk_entity_id, 0)),
                    "updated_at": updated_at,
                }
            )
    return pd.DataFrame(rows, columns=columns)


def _build_timeline(risk_entities: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    out = risk_entities[["risk_entity_id", "candidate_id", "report_month"]].copy()
    out["timeline_id"] = "tl_" + out["risk_entity_id"].astype(str)
    out["tenant_id"] = risk_entities["tenant_id"]
    out["month"] = out["report_month"]
    out["purchase_count"] = pd.NA
    out["purchase_amount_display"] = "relative_or_unavailable"
    out["purchase_quantity_display"] = "available_in_source_features"
    out["last_purchase_date"] = pd.NA
    out["days_since_last_purchase"] = pd.NA
    out["risk_probability_display"] = "risk band"
    out["palive_display"] = "hidden"
    out["display_note"] = "monthly timeline placeholder generated from current batch"
    return out[["timeline_id", "risk_entity_id", "candidate_id", "tenant_id", "month", "purchase_count", "purchase_amount_display", "purchase_quantity_display", "last_purchase_date", "days_since_last_purchase", "risk_probability_display", "palive_display", "display_note"]]


def _build_hospital_aggregates(risk_entities: pd.DataFrame) -> pd.DataFrame:
    return risk_entities.groupby(["tenant_id", "hospital_code", "hospital_display_name"], dropna=False).agg(
        risk_entity_count=("risk_entity_id", "count"),
        high_risk_count=("is_high_risk", "sum"),
    ).reset_index()


def _build_drug_aggregates(risk_entities: pd.DataFrame) -> pd.DataFrame:
    return risk_entities.groupby(["tenant_id", "drug_group", "drug_group_source"], dropna=False).agg(
        risk_entity_count=("risk_entity_id", "count"),
        high_risk_count=("is_high_risk", "sum"),
    ).reset_index()


def _build_monthly_reports(report_month: str, risk_entities: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "monthly_report_id": f"monthly_{report_month}",
                "report_type": "monthly",
                "report_month": report_month,
                "title": f"{report_month} monthly risk clue review",
                "summary_text": f"{len(risk_entities)} bounded worklist entities generated for monthly review.",
            }
        ]
    )


def _build_work_order_reserved(risk_entities: pd.DataFrame) -> pd.DataFrame:
    out = risk_entities[["risk_entity_id", "candidate_id"]].copy()
    out["work_order_id"] = "reserved_" + out["risk_entity_id"].astype(str)
    out["work_order_status"] = "reserved_not_created"
    out["auto_dispatch_allowed"] = False
    return out[["work_order_id", "risk_entity_id", "candidate_id", "work_order_status", "auto_dispatch_allowed"]]


def _with_entity_horizon(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    if "entity_id" not in out and "candidate_id" in out:
        out["entity_id"] = out["candidate_id"].astype(str).str.replace(r"\|H\d+$", "", regex=True)
    if "horizon" not in out and "candidate_id" in out:
        extracted = out["candidate_id"].astype(str).str.extract(r"\|(H\d+)$", expand=False)
        out["horizon"] = extracted
    return out


def _base_entity_id(row: pd.Series) -> str:
    if "entity_id" in row.index and pd.notna(row.get("entity_id")):
        return str(row.get("entity_id"))
    return str(row.get("candidate_id", row.get("risk_entity_id", ""))).replace("|H3", "").replace("|H6", "").replace("|H12", "")


def _first_profile_row(df: pd.DataFrame, entity_id: str, horizon: str) -> pd.Series:
    if df.empty or "entity_id" not in df or "horizon" not in df:
        return pd.Series(dtype=object)
    rows = df[df["entity_id"].astype(str).eq(str(entity_id)) & df["horizon"].astype(str).eq(str(horizon))]
    return pd.Series(dtype=object) if rows.empty else rows.iloc[0]


def _profile_probability(score_row: pd.Series, status_row: pd.Series, entity_row: pd.Series, horizon: str, primary_horizon: str) -> float | Any:
    for row in [score_row, status_row]:
        for field in ["risk_probability", "churn_probability_H", "probability_score", "risk_probability_value"]:
            if field in row.index and pd.notna(row.get(field)):
                return round(float(row.get(field)), 6)
    if str(horizon) == str(primary_horizon):
        for field in ["risk_probability_value", "churn_probability_H", "risk_score_display", "risk_score"]:
            if field in entity_row.index and pd.notna(entity_row.get(field)):
                return round(float(entity_row.get(field)), 6)
    return pd.NA


def _profile_involved_amount(feature_row: pd.Series, status_row: pd.Series, horizon: str) -> tuple[float, str]:
    months = _horizon_months(horizon)
    window_source = f"purchase_amount_sum_last_{months}m_asof_cutoff"
    for row in [feature_row, status_row]:
        if window_source in row.index and pd.notna(row.get(window_source)):
            return max(float(row.get(window_source)), 0.0), window_source
    value_source = f"value_at_risk_amount_nonnegative_{horizon}_asof_cutoff"
    for row in [feature_row, status_row]:
        if value_source in row.index and pd.notna(row.get(value_source)):
            return max(float(row.get(value_source)), 0.0), value_source
    for source in ["value_at_risk_proxy", "value_at_risk_H", "recent_order_amount", "avg_order_amount"]:
        for row in [feature_row, status_row]:
            if source in row.index and pd.notna(row.get(source)):
                return max(float(row.get(source)), 0.0), source
    return 0.0, window_source


def _horizon_months(horizon: str) -> int:
    text = str(horizon).upper().replace("H", "")
    try:
        return int(text)
    except ValueError:
        return 6


def _profile_text(row: pd.Series, fields: list[str]) -> str:
    for field in fields:
        if field in row.index:
            text = _text(row.get(field))
            if text:
                return text
    return ""


def _text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"", "nan", "none", "<na>"} else text


def _risk_level_from_probability(probability: Any) -> str:
    if probability is pd.NA or pd.isna(probability):
        return "unavailable"
    value = float(probability)
    if value >= 0.8:
        return "red"
    if value >= 0.6:
        return "orange"
    if value >= 0.4:
        return "yellow"
    return "observation"


def _risk_band_from_level(risk_level: str) -> str:
    key = str(risk_level).lower()
    if key in {"red", "high"}:
        return "High risk"
    if key in {"orange", "medium"}:
        return "Medium risk"
    if key in {"yellow", "observation"}:
        return "Observation"
    if key == "attention":
        return "Attention"
    return "Data unavailable"


def _detector_evidence_counts(evidence: pd.DataFrame | None) -> dict[str, int]:
    if evidence is None or evidence.empty or "risk_entity_id" not in evidence:
        return {}
    return evidence.groupby("risk_entity_id").size().to_dict()


def _write_tables(batch_dir: Path, tables: dict[str, pd.DataFrame], write_parquet: bool) -> str:
    if write_parquet:
        try:
            for name, df in tables.items():
                df.to_parquet(batch_dir / f"{name}.parquet", index=False)
            return "parquet"
        except Exception:
            for path in batch_dir.glob("*.parquet"):
                path.unlink(missing_ok=True)
    for name, df in tables.items():
        df.to_csv(batch_dir / f"{name}.csv", index=False)
    return "csv"
