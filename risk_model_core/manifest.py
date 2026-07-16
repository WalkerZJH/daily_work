"""Manifest loading and validation for risk result batches."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json


REQUIRED_MANIFEST_FIELDS = [
    "batch_id",
    "report_type",
    "report_month",
    "report_date",
    "score_cutoff_month",
    "primary_horizon",
    "available_horizons",
    "schema_version",
    "data_backend",
    "allowed_usage",
    "forbidden_usage",
    "customer_facing_probability_service_allowed",
    "auto_dispatch_allowed",
    "proof_case_report_allowed",
    "caveats",
]

DAILY_DETECTOR_REQUIRED_MANIFEST_FIELDS = [
    "batch_id",
    "report_type",
    "schema_version",
    "data_backend",
    "observation_date",
    "detector_run_date",
    "detector_tables",
    "caveats",
]


@dataclass(frozen=True, slots=True)
class RiskResultManifest:
    batch_id: str
    report_type: str
    report_month: str
    report_date: str
    score_cutoff_month: str
    primary_horizon: str
    available_horizons: list[str]
    schema_version: str
    data_backend: str
    allowed_usage: list[str]
    forbidden_usage: list[str]
    customer_facing_probability_service_allowed: bool
    auto_dispatch_allowed: bool
    proof_case_report_allowed: bool
    caveats: list[str]
    raw: dict[str, Any]


def load_manifest(batch_dir: str | Path) -> RiskResultManifest:
    path = Path(batch_dir) / "manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_manifest(data)
    return RiskResultManifest(
        batch_id=str(data["batch_id"]),
        report_type=str(data["report_type"]),
        report_month=str(data.get("report_month") or data.get("expected_probability_report_month") or ""),
        report_date=str(data.get("report_date") or data.get("observation_date") or ""),
        score_cutoff_month=str(data.get("score_cutoff_month") or data.get("expected_probability_report_month") or ""),
        primary_horizon=str(data.get("primary_horizon") or ""),
        available_horizons=[str(x) for x in data.get("available_horizons", [])],
        schema_version=str(data["schema_version"]),
        data_backend=str(data["data_backend"]),
        allowed_usage=[str(x) for x in data.get("allowed_usage", [])],
        forbidden_usage=[str(x) for x in data.get("forbidden_usage", [])],
        customer_facing_probability_service_allowed=bool(data.get("customer_facing_probability_service_allowed", False)),
        auto_dispatch_allowed=bool(data.get("auto_dispatch_allowed", False)),
        proof_case_report_allowed=bool(data.get("proof_case_report_allowed", False)),
        caveats=[str(x) for x in data["caveats"]],
        raw=data,
    )


def validate_manifest(manifest: dict[str, Any]) -> None:
    report_type = manifest.get("report_type")
    required = (
        DAILY_DETECTOR_REQUIRED_MANIFEST_FIELDS
        if report_type == "daily_detector"
        else REQUIRED_MANIFEST_FIELDS
    )
    missing = [field for field in required if field not in manifest]
    if missing:
        raise ValueError(f"Manifest missing required fields: {missing}")
    if manifest.get("data_backend") != "parquet":
        raise ValueError("Production risk result repository requires data_backend=parquet.")
    if report_type != "daily_detector" and manifest.get("auto_dispatch_allowed") is not False:
        raise ValueError("auto_dispatch_allowed must be false for this risk model core stage.")
    if report_type != "daily_detector" and manifest.get("customer_facing_probability_service_allowed") is not False:
        raise ValueError("customer_facing_probability_service_allowed must be false for this stage.")
