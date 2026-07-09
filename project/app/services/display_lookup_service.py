from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from risk_model_core import (  # noqa: E402
    InMemoryRiskResultRepository,
    ParquetRiskResultRepository,
    RiskResultRepository,
)
from risk_model_core.manifest import RiskResultManifest  # noqa: E402

LOOKUP_TABLE = "entity_display_lookup"
LOOKUP_SOURCE = "risk_model_core"
LOOKUP_SCHEMA_VERSION = "v1"
MISSING_WARNING = "ENTITY_DISPLAY_LOOKUP_NOT_AVAILABLE"


class DisplayLookupService:
    def __init__(self, repository: RiskResultRepository):
        self.repository = repository

    def status(self) -> dict[str, Any]:
        try:
            lookup = self._load_lookup()
        except (KeyError, ValueError, FileNotFoundError, NotImplementedError, AttributeError):
            return _missing_status()
        if lookup is None or lookup.empty:
            return _missing_status()
        fallback_policy = _fallback_policy(lookup)
        return {
            "ready": "conditional" if fallback_policy == "batch_display_name_or_code_fallback" else True,
            "status": "ready",
            "source": LOOKUP_SOURCE,
            "table": LOOKUP_TABLE,
            "row_count": int(len(lookup)),
            "schema_version": LOOKUP_SCHEMA_VERSION,
            "hospital_name_ready": _column_ready(lookup, "hospital_display_name"),
            "drug_name_ready": _column_ready(lookup, "drug_display_name"),
            "manufacturer_name_ready": _column_ready(lookup, "manufacturer_display_name"),
            "region_ready": _column_ready(lookup, "region_display_name"),
            "fallback_policy": fallback_policy,
            "warnings": [],
        }

    def _load_lookup(self) -> pd.DataFrame:
        loader = getattr(self.repository, "load_entity_display_lookup", None)
        if callable(loader):
            return loader()
        return self.repository.load_table(LOOKUP_TABLE)


def build_default_display_lookup_service() -> DisplayLookupService:
    batch_dir = os.getenv("RISK_RESULT_BATCH_DIR")
    if batch_dir:
        return DisplayLookupService(ParquetRiskResultRepository(batch_dir))
    return DisplayLookupService(_empty_repository())


def _missing_status() -> dict[str, Any]:
    return {
        "ready": False,
        "status": "missing",
        "source": LOOKUP_SOURCE,
        "table": LOOKUP_TABLE,
        "row_count": 0,
        "hospital_name_ready": False,
        "drug_name_ready": False,
        "manufacturer_name_ready": False,
        "region_ready": False,
        "fallback_policy": "code_fallback_when_lookup_missing",
        "warnings": [MISSING_WARNING],
    }


def _column_ready(frame: pd.DataFrame, column: str) -> bool:
    if column not in frame:
        return False
    return bool(frame[column].map(_text_or_empty).str.len().gt(0).any())


def _fallback_policy(frame: pd.DataFrame) -> str:
    quality = frame.get("display_name_quality")
    if quality is None:
        return "batch_display_name_or_code_fallback"
    values = {str(value).lower() for value in quality.dropna().unique()}
    if values and values.issubset({"master", "verified"}):
        return "display_lookup"
    return "batch_display_name_or_code_fallback"


def _text_or_empty(value: Any) -> str:
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return "" if value is None else str(value)


def _empty_repository() -> InMemoryRiskResultRepository:
    manifest = RiskResultManifest(
        batch_id="empty",
        report_type="monthly",
        report_month="latest",
        report_date="",
        score_cutoff_month="",
        primary_horizon="H6",
        available_horizons=["H6"],
        schema_version="empty",
        data_backend="memory",
        allowed_usage=[],
        forbidden_usage=[],
        customer_facing_probability_service_allowed=False,
        auto_dispatch_allowed=False,
        proof_case_report_allowed=False,
        caveats=[],
        raw={},
    )
    return InMemoryRiskResultRepository(manifest, {})
