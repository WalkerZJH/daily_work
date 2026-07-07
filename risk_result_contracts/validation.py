"""Validation for monthly risk result batches."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from .manifest import load_manifest
from .schemas import (
    MONTHLY_REPORT_REQUIRED_COLUMNS,
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
    load_manifest(batch)
    for table in STANDARD_TABLES:
        if not (batch / f"{table}.parquet").exists() and not (batch / f"{table}.csv").exists():
            raise FileNotFoundError(f"Missing standard result table: {table}")

    risk_entities = _load_table(batch, "risk_entities")
    risk_cards = _load_table(batch, "risk_cards")
    risk_card_evidence = _load_table(batch, "risk_card_evidence")
    monthly_reports = _load_table(batch, "monthly_reports")

    _require_columns(risk_entities, RISK_ENTITY_REQUIRED_COLUMNS, "risk_entities")
    _require_columns(risk_cards, RISK_CARD_REQUIRED_COLUMNS, "risk_cards")
    _require_columns(risk_card_evidence, RISK_EVIDENCE_REQUIRED_COLUMNS, "risk_card_evidence")
    _require_columns(monthly_reports, MONTHLY_REPORT_REQUIRED_COLUMNS, "monthly_reports")

    if "auto_dispatch_allowed" in risk_entities and bool(risk_entities["auto_dispatch_allowed"].fillna(False).any()):
        raise ValueError("risk_entities contains auto_dispatch_allowed=true.")

    entity_ids = set(risk_entities["risk_entity_id"].astype(str))
    if not set(risk_cards["risk_entity_id"].astype(str)).issubset(entity_ids):
        raise ValueError("risk_cards contains risk_entity_id outside risk_entities.")
    if not set(risk_card_evidence["risk_entity_id"].astype(str)).issubset(entity_ids):
        raise ValueError("risk_card_evidence contains risk_entity_id outside risk_entities.")

    _validate_no_forbidden_claims(risk_cards, ["card_title", "card_summary", "suggested_action"])
    _validate_no_forbidden_claims(risk_card_evidence, ["evidence_text"])


def _load_table(batch: Path, name: str) -> pd.DataFrame:
    parquet = batch / f"{name}.parquet"
    csv = batch / f"{name}.csv"
    if parquet.exists():
        return pd.read_parquet(parquet)
    if csv.exists():
        return pd.read_csv(csv)
    return pd.DataFrame()


def _require_columns(df: pd.DataFrame, columns: Iterable[str], name: str) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(f"{name} missing columns: {missing}")


def _validate_no_forbidden_claims(df: pd.DataFrame, columns: list[str]) -> None:
    for col in columns:
        if col not in df:
            continue
        for value in df[col].dropna().astype(str):
            bad = [claim for claim in FORBIDDEN_CLAIMS if claim in value]
            if bad:
                raise ValueError(f"Forbidden claim in {col}: {bad}")
