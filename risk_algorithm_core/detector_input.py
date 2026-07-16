"""Cleaned input contract and shared order eligibility for Daily Detector."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json

import pandas as pd


CLEANED_DETECTOR_INPUT_STAGE = "cleaned_detector_facts"
NORMAL_COMPLETION_PHASE_CODES = frozenset({60, 70, 80})
DETECTOR_ORDER_REQUIRED_COLUMNS = frozenset(
    {
        "row_uid",
        "order_id",
        "order_date",
        "manufacturer_code",
        "hospital_code",
        "drug_code",
        "order_quantity",
        "order_amount",
        "purchase_unit",
        "purchase_unit_price",
        "order_phase_code",
        "order_terminal_flag",
        "order_failure_flag",
        "needs_manual_review",
    }
)


@dataclass(frozen=True, slots=True)
class CleanedDetectorInputManifest:
    input_batch_id: str
    input_stage: str
    cleaning_contract_version: str
    table_paths: dict[str, str]
    raw: dict[str, Any]


def load_cleaned_detector_orders(
    batch_dir: str | Path,
) -> tuple[CleanedDetectorInputManifest, pd.DataFrame]:
    """Load only a local batch that explicitly declares the cleaned contract.

    Daily Detector must never silently turn a ClickHouse/raw-source manifest into
    a production input. Source extraction and cleaning are separate upstream
    responsibilities.
    """
    root = Path(batch_dir)
    data = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    input_stage = str(data.get("input_stage") or "")
    source_system = str(data.get("source_system") or "").lower()
    table_format = str(data.get("table_format") or "parquet").lower()
    if input_stage != CLEANED_DETECTOR_INPUT_STAGE:
        raise ValueError(
            "Daily Detector requires input_stage=cleaned_detector_facts; "
            "raw or legacy monthly input batches are not accepted."
        )
    if source_system == "clickhouse" or table_format == "clickhouse":
        raise ValueError("Daily Detector cannot read ClickHouse directly; run the cleaning/export chain first.")
    contract = dict(data.get("cleaning_contract") or {})
    contract_version = str(contract.get("version") or "")
    if not contract_version:
        raise ValueError("Cleaned Detector input manifest is missing cleaning_contract.version")
    if contract.get("canonical_status_mapping_applied") is not True:
        raise ValueError("Cleaned Detector input must apply the canonical order-status mapping")
    if contract.get("direct_purchase_unit_price_only") is not True:
        raise ValueError("Cleaned Detector input must use the cleaned direct purchase unit price")

    table_paths = {str(k): str(v) for k, v in dict(data.get("table_paths") or {}).items()}
    orders_path = root / str(table_paths.get("orders") or "orders.parquet")
    if orders_path.suffix.lower() != ".parquet":
        raise ValueError("Production cleaned Detector input must be Parquet")
    orders = pd.read_parquet(orders_path)
    validate_cleaned_detector_orders(orders)
    manifest = CleanedDetectorInputManifest(
        input_batch_id=str(data.get("input_batch_id") or data.get("raw_batch_id") or root.name),
        input_stage=input_stage,
        cleaning_contract_version=contract_version,
        table_paths=table_paths,
        raw=data,
    )
    return manifest, orders


def validate_cleaned_detector_orders(orders: pd.DataFrame) -> None:
    missing = DETECTOR_ORDER_REQUIRED_COLUMNS.difference(orders.columns)
    if missing:
        raise ValueError(f"Cleaned Detector orders are missing required columns: {sorted(missing)}")
    if orders["row_uid"].isna().any() or orders["row_uid"].astype(str).duplicated().any():
        raise ValueError("Cleaned Detector orders require a non-null unique row_uid")


def classify_detector_order_eligibility(orders: pd.DataFrame) -> pd.DataFrame:
    """Return the single canonical eligibility decision shared by every rule."""
    validate_cleaned_detector_orders(orders)
    phase = pd.to_numeric(orders["order_phase_code"], errors="coerce")
    terminal = pd.to_numeric(orders["order_terminal_flag"], errors="coerce").eq(1)
    failure = pd.to_numeric(orders["order_failure_flag"], errors="coerce").eq(1)
    review = orders["needs_manual_review"].fillna(False).astype(bool)
    normal_phase = phase.isin(NORMAL_COMPLETION_PHASE_CODES)
    eligible = normal_phase & terminal & ~failure & ~review

    reason = pd.Series("eligible_normal_completion", index=orders.index, dtype="string")
    reason.loc[~terminal] = "not_terminal"
    reason.loc[terminal & failure] = "failure_or_cancelled_terminal"
    reason.loc[terminal & ~failure & ~normal_phase] = "non_normal_terminal_phase"
    reason.loc[terminal & ~failure & normal_phase & review] = "manual_review_required"
    return pd.DataFrame(
        {
            "row_uid": orders["row_uid"].astype(str),
            "order_phase_code": phase.astype("Int64"),
            "order_terminal_flag": terminal,
            "order_failure_flag": failure,
            "needs_manual_review": review,
            "detector_order_eligible": eligible,
            "detector_exclusion_reason": reason,
        },
        index=orders.index,
    )


def filter_detector_eligible_orders(orders: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    decisions = classify_detector_order_eligibility(orders)
    eligible = orders.loc[decisions["detector_order_eligible"]].copy()
    return eligible.reset_index(drop=True), decisions.reset_index(drop=True)
