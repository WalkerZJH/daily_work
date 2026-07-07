"""Batch manifest schema for frontend/MVC risk result batches."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass(slots=True)
class ResultBatchManifest:
    batch_id: str
    report_type: str
    report_month: str
    report_date: str
    score_cutoff_month: str
    primary_horizon: str
    available_horizons: list[str]
    schema_version: str
    data_backend: str
    generated_at: str
    source_m_closure_batch: str
    allowed_usage: list[str]
    forbidden_usage: list[str]
    customer_facing_probability_service_allowed: bool
    auto_dispatch_allowed: bool
    proof_case_report_allowed: bool
    export_ready: bool
    export_formats_supported: list[str]
    caveats: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
