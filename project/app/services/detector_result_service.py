from __future__ import annotations

import math
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

SOURCE = "risk_model_core"
MISSING_WARNING = "DAILY_DETECTOR_RESULTS_NOT_AVAILABLE"
SEMANTIC_CAVEATS = [
    "detector_score is rule inspection score, not probability",
    "daily detector clues do not create risk_entities",
    "monthly_risk_probability comes from monthly risk_result_batch and does not change daily",
    "monthly model probabilities do not change daily",
]
CONFIG_EDIT_SEMANTICS = (
    "规则参数调整后，将在下一次巡检运行后生效，历史结果不会被静默改写。"
)


class DetectorResultService:
    def __init__(self, repository: RiskResultRepository):
        self.repository = repository

    def status(
        self,
        *,
        report_month: str | None = None,
        run_date: str | None = None,
    ) -> dict[str, Any]:
        runs = self._read_frame(
            "list_daily_detector_runs",
            report_month=report_month,
            run_date=run_date,
        )
        if runs.empty:
            return {
                "ready": False,
                "run_date": None,
                "detector_run_id": None,
                "detector_config_version": None,
                "clue_count": 0,
                "attached_high_risk_count": 0,
                "highest_detector_score": None,
                "enabled_detectors": None,
                "config_effective_note": CONFIG_EDIT_SEMANTICS,
                "source": SOURCE,
                "warnings": [MISSING_WARNING],
            }
        latest = _latest_run(runs)
        clues = self._read_frame(
            "list_daily_detector_clues",
            detector_run_id=_text(latest.get("detector_run_id")) or None,
        )
        return {
            "ready": True,
            "run_date": _text(latest.get("run_date")),
            "detector_run_id": _text(latest.get("detector_run_id")) or None,
            "detector_config_version": _text(latest.get("detector_config_version")) or None,
            "clue_count": _int(latest.get("clue_count")),
            "attached_high_risk_count": _int(latest.get("attached_high_risk_count")),
            "highest_detector_score": _highest_detector_score(clues),
            "enabled_detectors": _clean_value(latest.get("enabled_detectors")),
            "config_effective_note": CONFIG_EDIT_SEMANTICS,
            "source": SOURCE,
            "warnings": [],
        }

    def catalog(self) -> dict[str, Any]:
        catalog = self._read_frame("list_detector_catalog")
        items = [_catalog_item(row) for _, row in catalog.iterrows()]
        return {
            "ready": bool(items),
            "source": SOURCE,
            "items": items,
            "semantic_caveats": SEMANTIC_CAVEATS,
            "warnings": [] if items else [MISSING_WARNING],
        }

    def runs(
        self,
        *,
        report_month: str | None = None,
        run_date: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        runs = self._read_frame(
            "list_daily_detector_runs",
            report_month=report_month,
            run_date=run_date,
        )
        runs = _sort_frame(runs, ["run_date", "created_at"], ascending=False)
        if limit is not None:
            runs = runs.head(max(int(limit), 0))
        items = [_run_item(row) for _, row in runs.iterrows()]
        return {
            "ready": bool(items),
            "source": SOURCE,
            "items": items,
            "warnings": [] if items else [MISSING_WARNING],
        }

    def run_dates(
        self,
        *,
        report_month: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        runs = self._read_frame("list_daily_detector_runs", report_month=report_month)
        runs = _sort_frame(runs, ["run_date", "created_at"], ascending=False).head(max(int(limit), 0))
        items = []
        for _, row in runs.iterrows():
            items.append(
                {
                    "detector_run_id": _text(row.get("detector_run_id")),
                    "run_date": _text(row.get("run_date")),
                    "report_month": _text(row.get("report_month")),
                    "status": "ready",
                    "detector_config_version": _text(row.get("detector_config_version")),
                    "clue_count": _int(row.get("clue_count")),
                    "attached_high_risk_count": _int(row.get("attached_high_risk_count")),
                }
            )
        return {
            "ready": bool(items),
            "source": SOURCE,
            "items": items,
            "semantic_caveats": SEMANTIC_CAVEATS,
            "warnings": [] if items else [MISSING_WARNING],
        }

    def clues(
        self,
        *,
        detector_run_id: str | None = None,
        run_date: str | None = None,
        detector_id: str | None = None,
        detector_family: str | None = None,
        manufacturer_code: str | None = None,
        hospital_code: str | None = None,
        drug_group: str | None = None,
        horizon: str | None = None,
        sort_by: str = "detector_score",
        only_monthly_high_risk: bool | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        runs = self._read_frame("list_daily_detector_runs", run_date=run_date)
        latest_run = _latest_run(runs) if not runs.empty else {}
        effective_run_date = run_date or _text(latest_run.get("run_date")) or None
        effective_run_id = detector_run_id or _text(latest_run.get("detector_run_id")) or None
        filters = {
            "detector_run_id": detector_run_id,
            "run_date": effective_run_date,
            "detector_id": detector_id,
            "detector_family": detector_family,
            "manufacturer_code": manufacturer_code,
            "hospital_code": hospital_code,
            "drug_group": drug_group,
        }
        clues = self._read_frame("list_daily_detector_clues", **filters)
        if only_monthly_high_risk is not None and not clues.empty:
            mask = clues.get(
                "is_monthly_high_risk_entity", pd.Series(False, index=clues.index)
            ).map(_bool)
            clues = clues[mask.eq(bool(only_monthly_high_risk))]
        clues = _sort_clues(clues, sort_by)
        total = int(len(clues))
        current_page = max(int(page), 1)
        current_size = min(max(int(page_size), 1), 200)
        start = (current_page - 1) * current_size
        catalog = {item["detector_id"]: item for item in self.catalog()["items"]}
        items = [
            _clue_item(row, catalog)
            for _, row in clues.iloc[start : start + current_size].iterrows()
        ]
        ready = bool(latest_run) or total > 0
        return {
            "ready": ready,
            "source": SOURCE,
            "clues": items,
            "items": items,
            "total": total,
            "run_date": effective_run_date,
            "detector_run_id": effective_run_id,
            "pagination": {
                "page": current_page,
                "page_size": current_size,
                "total": total,
            },
            "semantic_caveats": SEMANTIC_CAVEATS,
            "warnings": [] if ready else [MISSING_WARNING],
        }

    def risk_entity_detector_evidence(
        self,
        *,
        risk_entity_id: str,
        detector_run_id: str | None = None,
        run_date: str | None = None,
        detector_family: str | None = None,
        detector_id: str | None = None,
    ) -> dict[str, Any]:
        entity = self.repository.get_risk_entity(risk_entity_id)
        if entity is None:
            raise KeyError(risk_entity_id)
        evidence = self._read_high_risk_evidence(risk_entity_id, detector_run_id)
        evidence = _filter_frame(
            evidence,
            {
                "run_date": run_date,
                "detector_family": detector_family,
                "detector_id": detector_id,
            },
        )
        catalog = {item["detector_id"]: item for item in self.catalog()["items"]}
        return {
            "risk_entity_id": risk_entity_id,
            "source": SOURCE,
            "monthly_risk_probability": _first_number(
                entity,
                ["monthly_risk_probability", "risk_probability_value", "churn_probability_H"],
            ),
            "monthly_loss_value": _first_number(
                entity,
                ["monthly_loss_value", "loss_value", "value_at_risk_H", "value_at_risk_proxy"],
            ),
            "items": [_evidence_item(row) for _, row in evidence.iterrows()],
            "catalog_by_detector_id": catalog,
            "semantic_caveats": SEMANTIC_CAVEATS,
            "warnings": [] if not evidence.empty else ["NO_HIGH_RISK_DETECTOR_EVIDENCE"],
        }

    def config_status(self) -> dict[str, Any]:
        runs = self._read_frame("list_daily_detector_runs")
        latest = _latest_run(runs) if not runs.empty else {}
        return {
            "effective_config_version": _text(latest.get("detector_config_version")) or None,
            "latest_run_id": _text(latest.get("detector_run_id")) or None,
            "latest_run_date": _text(latest.get("run_date")) or None,
            "pending_config_version": None,
            "pending_config_exists": False,
            "pending_config_supported": False,
            "next_run_required": False,
            "history_rewrite_allowed": False,
            "config_edit_semantics": CONFIG_EDIT_SEMANTICS,
            "warnings": [] if not runs.empty else [MISSING_WARNING],
        }

    def _read_high_risk_evidence(
        self,
        risk_entity_id: str,
        detector_run_id: str | None,
    ) -> pd.DataFrame:
        try:
            return self.repository.list_high_risk_detector_evidence(
                risk_entity_id=risk_entity_id,
                detector_run_id=detector_run_id,
            )
        except (KeyError, ValueError, FileNotFoundError, NotImplementedError, AttributeError):
            return pd.DataFrame()

    def _read_frame(self, method_name: str, **filters: Any) -> pd.DataFrame:
        clean_filters = {key: value for key, value in filters.items() if value is not None}
        try:
            method = getattr(self.repository, method_name)
            frame = method(**clean_filters)
        except (KeyError, ValueError, FileNotFoundError, NotImplementedError, AttributeError):
            return pd.DataFrame()
        return frame if isinstance(frame, pd.DataFrame) else pd.DataFrame(frame)


def build_default_detector_result_service() -> DetectorResultService:
    batch_dir = os.getenv("RISK_RESULT_BATCH_DIR")
    if batch_dir:
        return DetectorResultService(ParquetRiskResultRepository(batch_dir))
    return DetectorResultService(_empty_repository())


def _catalog_item(row: pd.Series) -> dict[str, Any]:
    return {
        "detector_id": _text(row.get("detector_id")),
        "detector_family": _text(row.get("detector_family")),
        "detector_name": _text(row.get("detector_name")),
        "status": _text(row.get("status")),
        "enabled_by_default": _bool(row.get("enabled_by_default")),
        "method": _text(row.get("method")),
        "required_fields": _clean_value(row.get("required_fields")),
        "optional_fields": _clean_value(row.get("optional_fields")),
        "output_schema_version": _text(row.get("output_schema_version")),
        "caveat": _text(row.get("caveat")) or None,
    }


def _run_item(row: pd.Series) -> dict[str, Any]:
    return {
        "detector_run_id": _text(row.get("detector_run_id")),
        "run_date": _text(row.get("run_date")),
        "report_month": _text(row.get("report_month")),
        "source_result_batch_id": _text(row.get("source_result_batch_id")) or None,
        "detector_config_version": _text(row.get("detector_config_version")),
        "enabled_detectors": _clean_value(row.get("enabled_detectors")),
        "scanned_entity_count": _int(row.get("scanned_entity_count")),
        "clue_count": _int(row.get("clue_count")),
        "attached_high_risk_count": _int(row.get("attached_high_risk_count")),
        "created_at": _text(row.get("created_at")) or None,
    }


def _clue_item(row: pd.Series, catalog: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    detector_id = _text(row.get("detector_id"))
    catalog_item = (catalog or {}).get(detector_id, {})
    monthly_high = _bool(row.get("is_monthly_high_risk_entity"))
    hospital_code = _text(row.get("hospital_code")) or None
    drug_group = _text(row.get("drug_group")) or None
    return {
        "clue_id": _text(row.get("detector_clue_id")),
        "detector_clue_id": _text(row.get("detector_clue_id")),
        "detector_run_id": _text(row.get("detector_run_id")),
        "run_date": _text(row.get("run_date")),
        "tenant_id": _text(row.get("tenant_id")) or None,
        "manufacturer_code": _text(row.get("manufacturer_code")) or None,
        "hospital_code": hospital_code,
        "hospital_name": hospital_code,
        "drug_group": drug_group,
        "drug_name": drug_group,
        "detector_id": detector_id,
        "detector_family": _text(row.get("detector_family")),
        "detector_family_label": _text(row.get("detector_family")),
        "detector_name_label": _text(catalog_item.get("detector_name") or detector_id),
        "detector_score": _number_or_none(row.get("detector_score")),
        "detector_score_label": "规则巡检分",
        "detector_level": _text(row.get("detector_level")) or None,
        "confidence": _number_or_none(row.get("confidence")),
        "hit_flag": _bool(row.get("hit_flag")),
        "root_cause_label": _text(row.get("root_cause_label")) or None,
        "evidence_text": _text(row.get("evidence_text")) or None,
        "evidence_payload": _clean_value(row.get("evidence_payload")),
        "is_monthly_high_risk_entity": monthly_high,
        "risk_entity_id": _text(row.get("risk_entity_id")),
        "monthly_risk_probability": _number_or_none(row.get("monthly_risk_probability")),
        "monthly_loss_value": _number_or_none(row.get("monthly_loss_value")),
        "action": "查看月报风险" if monthly_high else "仅规则命中",
        "display_rank": _int_or_none(row.get("display_rank")),
        "caveat": _text(row.get("caveat")) or None,
        "created_at": _text(row.get("created_at")) or None,
    }


def _evidence_item(row: pd.Series) -> dict[str, Any]:
    return {
        "risk_entity_id": _text(row.get("risk_entity_id")),
        "detector_run_id": _text(row.get("detector_run_id")),
        "run_date": _text(row.get("run_date")),
        "detector_id": _text(row.get("detector_id")),
        "detector_family": _text(row.get("detector_family")),
        "detector_score": _number_or_none(row.get("detector_score")),
        "confidence": _number_or_none(row.get("confidence")),
        "root_cause_label": _text(row.get("root_cause_label")) or None,
        "evidence_text": _text(row.get("evidence_text")) or None,
        "evidence_payload": _clean_value(row.get("evidence_payload")),
        "caveat": _text(row.get("caveat")) or None,
        "created_at": _text(row.get("created_at")) or None,
    }


def _latest_run(runs: pd.DataFrame) -> dict[str, Any]:
    ordered = _sort_frame(runs, ["run_date", "created_at"], ascending=False)
    return ordered.iloc[0].to_dict() if not ordered.empty else {}


def _sort_frame(frame: pd.DataFrame, columns: list[str], *, ascending: bool) -> pd.DataFrame:
    if frame.empty:
        return frame
    available = [column for column in columns if column in frame]
    if not available:
        return frame
    return frame.sort_values(available, ascending=ascending, na_position="last", kind="mergesort")


def _sort_clues(frame: pd.DataFrame, sort_by: str) -> pd.DataFrame:
    if frame.empty:
        return frame
    if sort_by == "detector_score" and "detector_score" in frame:
        return frame.sort_values("detector_score", ascending=False, na_position="last", kind="mergesort")
    if sort_by == "risk_probability" and "monthly_risk_probability" in frame:
        return frame.sort_values("monthly_risk_probability", ascending=False, na_position="last", kind="mergesort")
    if sort_by == "loss_value" and "monthly_loss_value" in frame:
        return frame.sort_values("monthly_loss_value", ascending=False, na_position="last", kind="mergesort")
    return _sort_frame(frame, ["display_rank", "created_at"], ascending=True)


def _highest_detector_score(clues: pd.DataFrame) -> float | None:
    if clues.empty or "detector_score" not in clues:
        return None
    values = pd.to_numeric(clues["detector_score"], errors="coerce").dropna()
    if values.empty:
        return None
    return float(values.max())


def _filter_frame(frame: pd.DataFrame, filters: dict[str, Any]) -> pd.DataFrame:
    out = frame.copy()
    for column, value in filters.items():
        if value is None or column not in out:
            continue
        out = out[out[column].astype(str).eq(str(value))]
    return out


def _first_number(row: dict[str, Any], fields: list[str]) -> float | None:
    for field in fields:
        value = _number_or_none(row.get(field))
        if value is not None:
            return value
    return None


def _clean_value(value: Any) -> Any:
    if _is_missing(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _text(value: Any) -> str:
    if _is_missing(value):
        return ""
    return str(value)


def _bool(value: Any) -> bool:
    if _is_missing(value):
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _int_or_none(value: Any) -> int | None:
    if _is_missing(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _number_or_none(value: Any) -> float | None:
    if _is_missing(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(number) else number


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


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
