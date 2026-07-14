"""Validation for monthly risk result batches."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd
import pyarrow.parquet as pq

from .manifest import load_manifest
from .schemas import (
    ENTITY_DISPLAY_LOOKUP_REQUIRED_COLUMNS,
    ENTITY_DISPLAY_LOOKUP_UNIQUE_KEY,
    DAILY_DETECTOR_CLUE_REQUIRED_COLUMNS,
    DAILY_DETECTOR_RUN_REQUIRED_COLUMNS,
    DETECTOR_CATALOG_REQUIRED_COLUMNS,
    HIGH_RISK_DETECTOR_EVIDENCE_REQUIRED_COLUMNS,
    MONTHLY_REPORT_REQUIRED_COLUMNS,
    RISK_ENTITY_HORIZON_PROFILE_REQUIRED_COLUMNS,
    RISK_CARD_REQUIRED_COLUMNS,
    RISK_ENTITY_REQUIRED_COLUMNS,
    RISK_EVIDENCE_REQUIRED_COLUMNS,
    STANDARD_TABLES,
)


FORBIDDEN_CLAIMS = [
    "\u533b\u9662\u5df2\u7ecf\u786e\u5b9a\u6d41\u5931",
    "\u533b\u9662\u4e00\u5b9a\u4e0d\u4f1a\u518d\u91c7\u8d2d",
    "\u7ade\u54c1\u66ff\u4ee3\u5df2\u53d1\u751f",
    "\u653f\u7b56\u843d\u6807\u5df2\u53d1\u751f",
    "\u914d\u9001\u5546\u8d23\u4efb\u5df2\u786e\u8ba4",
]


def validate_result_batch(batch_dir: str | Path) -> None:
    batch = Path(batch_dir)
    manifest = load_manifest(batch)
    for table in STANDARD_TABLES:
        if table == "risk_entity_horizon_profiles" and not _requires_horizon_profiles(manifest.schema_version):
            continue
        _require_production_parquet_table(batch, table, manifest.raw)

    risk_entities = _load_table(batch, "risk_entities")
    risk_entity_horizon_profiles = _load_table(batch, "risk_entity_horizon_profiles")
    risk_cards = _load_table(batch, "risk_cards")
    risk_card_evidence = _load_table(batch, "risk_card_evidence")
    monthly_reports = _load_table(batch, "monthly_reports")
    entity_display_lookup = _load_table(batch, "entity_display_lookup")
    detector_catalog = _load_table(batch, "detector_catalog")
    daily_detector_runs = _load_table(batch, "daily_detector_runs")
    daily_detector_clues = _load_table(batch, "daily_detector_clues")
    high_risk_detector_evidence = _load_table(batch, "high_risk_detector_evidence")

    _require_columns(risk_entities, RISK_ENTITY_REQUIRED_COLUMNS, "risk_entities")
    if _requires_horizon_profiles(manifest.schema_version) or not risk_entity_horizon_profiles.empty:
        _require_columns(risk_entity_horizon_profiles, RISK_ENTITY_HORIZON_PROFILE_REQUIRED_COLUMNS, "risk_entity_horizon_profiles")
    _require_columns(risk_cards, RISK_CARD_REQUIRED_COLUMNS, "risk_cards")
    _require_columns(risk_card_evidence, RISK_EVIDENCE_REQUIRED_COLUMNS, "risk_card_evidence")
    _require_columns(monthly_reports, MONTHLY_REPORT_REQUIRED_COLUMNS, "monthly_reports")
    _require_columns(entity_display_lookup, ENTITY_DISPLAY_LOOKUP_REQUIRED_COLUMNS, "entity_display_lookup")
    _require_columns(detector_catalog, DETECTOR_CATALOG_REQUIRED_COLUMNS, "detector_catalog")
    _require_columns(daily_detector_runs, DAILY_DETECTOR_RUN_REQUIRED_COLUMNS, "daily_detector_runs")
    _require_columns(daily_detector_clues, DAILY_DETECTOR_CLUE_REQUIRED_COLUMNS, "daily_detector_clues")
    _require_columns(high_risk_detector_evidence, HIGH_RISK_DETECTOR_EVIDENCE_REQUIRED_COLUMNS, "high_risk_detector_evidence")
    _require_unique(entity_display_lookup, ENTITY_DISPLAY_LOOKUP_UNIQUE_KEY, "entity_display_lookup")

    _validate_full_recurring_persistence(manifest.raw, risk_entities)

    if "auto_dispatch_allowed" in risk_entities and bool(risk_entities["auto_dispatch_allowed"].fillna(False).any()):
        raise ValueError("risk_entities contains auto_dispatch_allowed=true.")

    entity_ids = set(risk_entities["risk_entity_id"].astype(str))
    if not risk_entity_horizon_profiles.empty and not set(risk_entity_horizon_profiles["risk_entity_id"].astype(str)).issubset(entity_ids):
        raise ValueError("risk_entity_horizon_profiles contains risk_entity_id outside risk_entities.")
    if not risk_entity_horizon_profiles.empty and "involved_amount_source" in risk_entity_horizon_profiles:
        forbidden_sources = {"order_amount_total", "purchase_amount_total", "full_history_amount", "all_history_amount"}
        sources = set(risk_entity_horizon_profiles["involved_amount_source"].dropna().astype(str))
        if sources & forbidden_sources:
            raise ValueError("risk_entity_horizon_profiles involved_amount must not use full-history amount sources.")
    if not set(risk_cards["risk_entity_id"].astype(str)).issubset(entity_ids):
        raise ValueError("risk_cards contains risk_entity_id outside risk_entities.")
    if not set(risk_card_evidence["risk_entity_id"].astype(str)).issubset(entity_ids):
        raise ValueError("risk_card_evidence contains risk_entity_id outside risk_entities.")
    if "detector_probability" in daily_detector_clues.columns:
        raise ValueError("daily_detector_clues must not expose detector_probability.")
    if not high_risk_detector_evidence.empty:
        if not set(high_risk_detector_evidence["risk_entity_id"].astype(str)).issubset(entity_ids):
            raise ValueError("high_risk_detector_evidence contains risk_entity_id outside risk_entities.")
    reserved = detector_catalog[detector_catalog["status"].astype(str).isin([
        "reserved",
        "interface_only",
        "missing_fields",
        "blocked_by_data",
        "blocked_by_missing_domain_concept",
        "not_implemented",
    ])]
    if not reserved.empty and reserved["enabled_by_default"].astype(str).str.lower().isin({"true", "1", "yes"}).any():
        raise ValueError("blocked or non-implemented detectors must not be enabled by default.")

    _validate_no_forbidden_claims(risk_cards, ["card_title", "card_summary", "suggested_action"])
    _validate_no_forbidden_claims(risk_card_evidence, ["evidence_text"])
    _validate_no_forbidden_claims(daily_detector_clues, ["evidence_text", "root_cause_label", "caveat"])
    _validate_no_forbidden_claims(high_risk_detector_evidence, ["evidence_text", "root_cause_label", "caveat"])


def _validate_full_recurring_persistence(manifest: dict, risk_entities: pd.DataFrame) -> None:
    full_count = manifest.get("full_recurring_count")
    persisted_count = manifest.get("persisted_recurring_count")
    if full_count is None and persisted_count is None:
        return
    if full_count is None or persisted_count is None:
        raise ValueError("Manifest must declare both full_recurring_count and persisted_recurring_count.")
    actual = int(
        risk_entities.get("candidate_type", pd.Series("recurring", index=risk_entities.index))
        .astype(str)
        .eq("recurring")
        .sum()
    )
    if int(full_count) != int(persisted_count) or int(persisted_count) != actual:
        raise ValueError(
            "Recurring candidate persistence mismatch: "
            f"full={full_count}, persisted={persisted_count}, actual={actual}"
        )


def _load_table(batch: Path, name: str) -> pd.DataFrame:
    parquet = batch / f"{name}.parquet"
    if parquet.exists():
        return pd.read_parquet(parquet)
    raise FileNotFoundError(f"Missing production Parquet table: {parquet}")


def _require_production_parquet_table(batch: Path, table: str, manifest: dict) -> None:
    parquet = batch / f"{table}.parquet"
    csv = batch / f"{table}.csv"
    if not parquet.exists():
        raise FileNotFoundError(f"Missing standard Parquet result table: {table}")
    if csv.exists():
        raise ValueError(f"Production batch contains forbidden CSV table beside Parquet: {csv}")
    metadata = pq.ParquetFile(parquet).metadata
    manifest_count = (manifest.get("result_table_row_counts") or {}).get(table)
    if manifest_count is not None and int(manifest_count) != int(metadata.num_rows):
        raise ValueError(
            f"{table} row count mismatch: manifest={manifest_count}, parquet={metadata.num_rows}"
        )
    declared_paths = _manifest_table_paths(manifest)
    declared_path = declared_paths.get(table)
    if declared_path is not None and not str(declared_path).endswith(".parquet"):
        raise ValueError(f"Manifest declares non-Parquet path for {table}: {declared_path}")


def _manifest_table_paths(manifest: dict) -> dict[str, str]:
    paths: dict[str, str] = {}
    horizon = manifest.get("horizon_profile_table") or {}
    if isinstance(horizon, dict) and horizon.get("table_name") and horizon.get("path"):
        paths[str(horizon["table_name"])] = str(horizon["path"])
    lookup = manifest.get("entity_display_lookup") or {}
    if isinstance(lookup, dict) and lookup.get("table_name") and lookup.get("path"):
        paths[str(lookup["table_name"])] = str(lookup["path"])
    oneshot = manifest.get("oneshot_terminals") or {}
    if isinstance(oneshot, dict) and oneshot.get("table_name") and oneshot.get("path"):
        paths[str(oneshot["table_name"])] = str(oneshot["path"])
    detector = manifest.get("detector_tables") or {}
    if isinstance(detector, dict):
        for table, path in detector.items():
            paths[str(table)] = str(path)
    return paths


def _requires_horizon_profiles(schema_version: str) -> bool:
    return str(schema_version).endswith("_v2") or "horizon_profile" in str(schema_version)


def _require_columns(df: pd.DataFrame, columns: Iterable[str], name: str) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(f"{name} missing columns: {missing}")


def _require_unique(df: pd.DataFrame, columns: list[str], name: str) -> None:
    if df.empty:
        return
    duplicated = df.duplicated(columns, keep=False)
    if bool(duplicated.any()):
        raise ValueError(f"{name} duplicate key rows: {columns}")


def _validate_no_forbidden_claims(df: pd.DataFrame, columns: list[str]) -> None:
    for col in columns:
        if col not in df:
            continue
        for value in df[col].dropna().astype(str):
            bad = [claim for claim in FORBIDDEN_CLAIMS if claim in value]
            if bad:
                raise ValueError(f"Forbidden claim in {col}: {bad}")
