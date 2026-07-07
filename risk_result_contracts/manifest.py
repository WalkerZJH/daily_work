"""Manifest helpers for monthly risk result batches."""

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
    data = json.loads((Path(batch_dir) / "manifest.json").read_text(encoding="utf-8"))
    validate_manifest(data)
    return RiskResultManifest(
        batch_id=str(data["batch_id"]),
        report_type=str(data["report_type"]),
        report_month=str(data["report_month"]),
        report_date=str(data["report_date"]),
        score_cutoff_month=str(data["score_cutoff_month"]),
        primary_horizon=str(data["primary_horizon"]),
        available_horizons=[str(x) for x in data["available_horizons"]],
        schema_version=str(data["schema_version"]),
        data_backend=str(data["data_backend"]),
        allowed_usage=[str(x) for x in data["allowed_usage"]],
        forbidden_usage=[str(x) for x in data["forbidden_usage"]],
        customer_facing_probability_service_allowed=bool(data["customer_facing_probability_service_allowed"]),
        auto_dispatch_allowed=bool(data["auto_dispatch_allowed"]),
        proof_case_report_allowed=bool(data["proof_case_report_allowed"]),
        caveats=[str(x) for x in data["caveats"]],
        raw=data,
    )


def validate_manifest(manifest: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_MANIFEST_FIELDS if field not in manifest]
    if missing:
        raise ValueError(f"Manifest missing required fields: {missing}")
    if manifest.get("report_type") != "monthly":
        raise ValueError("risk_result_batch report_type must be monthly.")
    if manifest.get("auto_dispatch_allowed") is not False:
        raise ValueError("auto_dispatch_allowed must be false.")
    if manifest.get("customer_facing_probability_service_allowed") is not False:
        raise ValueError("customer_facing_probability_service_allowed must be false.")
    if manifest.get("proof_case_report_allowed") is not False:
        raise ValueError("proof_case_report_allowed must be false until customer-confirmed proof cases exist.")


def write_manifest(batch_dir: str | Path, manifest: dict[str, Any]) -> None:
    validate_manifest(manifest)
    path = Path(batch_dir)
    path.mkdir(parents=True, exist_ok=True)
    (path / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=True, indent=2), encoding="utf-8")
