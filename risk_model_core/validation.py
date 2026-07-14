"""Validation helpers for independent risk result batches."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .business_copy_renderer import validate_no_forbidden_claims
from .manifest import load_manifest
from .schemas import (
    RISK_CARD_REQUIRED_COLUMNS,
    RISK_ENTITY_HORIZON_PROFILE_REQUIRED_COLUMNS,
    RISK_ENTITY_REQUIRED_COLUMNS,
    RISK_EVIDENCE_REQUIRED_COLUMNS,
)


def validate_batch(batch_dir: str | Path) -> None:
    batch = Path(batch_dir)
    manifest = load_manifest(batch)
    _ = manifest
    validate_columns(load_table(batch, "risk_entities"), RISK_ENTITY_REQUIRED_COLUMNS, "risk_entities")
    horizon_profiles = load_table(batch, "risk_entity_horizon_profiles")
    if manifest.schema_version.endswith("_v2") or not horizon_profiles.empty:
        validate_columns(horizon_profiles, RISK_ENTITY_HORIZON_PROFILE_REQUIRED_COLUMNS, "risk_entity_horizon_profiles")
    validate_columns(load_table(batch, "risk_cards"), RISK_CARD_REQUIRED_COLUMNS, "risk_cards")
    validate_columns(load_table(batch, "risk_card_evidence"), RISK_EVIDENCE_REQUIRED_COLUMNS, "risk_card_evidence")


def validate_columns(df: pd.DataFrame, required: list[str], name: str) -> None:
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"{name} missing columns: {missing}")
    text_cols = [col for col in df.columns if col.endswith("_text") or col.endswith("_summary") or col.endswith("_title")]
    for col in text_cols:
        for value in df[col].dropna().astype(str).head(1000):
            validate_no_forbidden_claims(value)


def load_table(batch: Path, name: str) -> pd.DataFrame:
    parquet = batch / f"{name}.parquet"
    if parquet.exists():
        return pd.read_parquet(parquet)
    raise FileNotFoundError(f"Missing production Parquet table: {parquet}")
