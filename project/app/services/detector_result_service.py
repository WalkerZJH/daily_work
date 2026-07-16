from __future__ import annotations

import math
import os
import sys
import json
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
    open_detector_result_repository,
)
from risk_model_core.manifest import RiskResultManifest  # noqa: E402
from app.services.result_batch_discovery import latest_detector_batch

SOURCE = "risk_model_core"
MISSING_WARNING = "DAILY_DETECTOR_RESULTS_NOT_AVAILABLE"
SEMANTIC_CAVEATS = [
    "detector_score is rule inspection score, not probability",
    "daily detector clues do not create risk_entities",
    "monthly_risk_probability comes from monthly risk_result_batch and does not change daily",
    "monthly model probabilities do not change daily",
]
_CLUE_DETAIL_COLUMNS = [
    "detector_clue_id", "detector_run_id", "run_date", "tenant_id",
    "manufacturer_code", "manufacturer_display_name", "hospital_code",
    "hospital_display_name", "drug_group", "drug_display_name",
    "region_display_name", "product_line_name", "detector_id", "detector_family",
    "detector_score", "detector_level", "confidence", "hit_flag", "root_cause_label",
    "evidence_text", "evidence_payload", "is_monthly_high_risk_entity", "risk_entity_id",
    "monthly_risk_probability", "monthly_loss_value", "display_rank", "caveat", "created_at",
]
CONFIG_EDIT_SEMANTICS = "当前阶段仅使用只读管理员参数表；不提供用户参数修改入口。"


class DetectorResultService:
    def __init__(self, repository: RiskResultRepository):
        self.repository = repository

    def status(
        self,
        *,
        report_month: str | None = None,
        run_date: str | None = None,
        manufacturer_code: str | None = None,
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
        latest_date = _text(latest.get("run_date"))
        latest_runs = runs[
            runs.get("run_date", pd.Series("", index=runs.index)).astype(str).eq(latest_date)
        ]
        clues = self._read_frame(
            "list_daily_detector_clues",
            run_date=latest_date or None,
            manufacturer_code=manufacturer_code,
        )
        run_ids = [_text(value) for value in latest_runs.get("detector_run_id", pd.Series(dtype=str)) if _text(value)]
        config_versions = sorted({_text(value) for value in latest_runs.get("detector_config_version", pd.Series(dtype=str)) if _text(value)})
        enabled = []
        for value in latest_runs.get("enabled_detectors", pd.Series(dtype=str)):
            enabled.extend(item for item in _text(value).split(",") if item)
        return {
            "ready": True,
            "run_date": latest_date,
            "detector_run_id": ";".join(run_ids) or None,
            "detector_config_version": ";".join(config_versions) or None,
            "clue_count": int(len(clues)),
            "attached_high_risk_count": int(
                pd.to_numeric(latest_runs.get("attached_high_risk_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
            ),
            "highest_detector_score": _highest_detector_score(clues),
            "enabled_detectors": ",".join(dict.fromkeys(enabled)) or None,
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
        if not clues.empty:
            clues = clues[clues.get("hit_flag", pd.Series(False, index=clues.index)).map(_bool)]
        clues = _merge_entity_display_lookup(clues, self.repository)
        clues = _sort_clues(clues, sort_by)
        clues = _deduplicate_clues(clues)
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

    def results(
        self,
        *,
        observation_date: str | None = None,
        detector_id: str | None = None,
        detector_family: str | None = None,
        manufacturer_code: str | None = None,
        hospital_code: str | None = None,
        drug_code: str | None = None,
        eligibility_status: str | None = None,
        hit_flag: bool | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        frame = self._read_frame(
            "list_daily_detector_results",
            observation_date=observation_date,
            detector_id=detector_id,
            detector_family=detector_family,
            manufacturer_code=manufacturer_code,
            hospital_code=hospital_code,
            drug_code=drug_code,
            eligibility_status=eligibility_status,
            hit_flag=hit_flag,
        )
        frame = _sort_frame(frame, ["observation_date", "created_at"], ascending=False)
        total = int(len(frame))
        current_page = max(int(page), 1)
        current_size = min(max(int(page_size), 1), 200)
        start = (current_page - 1) * current_size
        items = [_result_item(row) for _, row in frame.iloc[start : start + current_size].iterrows()]
        return {
            "ready": bool(total),
            "source": SOURCE,
            "items": items,
            "total": total,
            "pagination": {"page": current_page, "page_size": current_size, "total": total},
            "semantic_caveats": SEMANTIC_CAVEATS,
            "warnings": [] if total else [MISSING_WARNING],
        }

    def clue_detail(
        self,
        *,
        detector_clue_id: str,
        detector_run_id: str | None = None,
        run_date: str | None = None,
        manufacturer_code: str | None = None,
    ) -> dict[str, Any]:
        """Return one detector fact without loading the detector clue list."""
        row = self.repository.get_daily_detector_clue_by_id(
            detector_clue_id,
            columns=_CLUE_DETAIL_COLUMNS,
        )
        if row is None or not _matches_clue_context(
            row,
            detector_run_id=detector_run_id,
            run_date=run_date,
            manufacturer_code=manufacturer_code,
        ):
            raise KeyError(detector_clue_id)
        catalog = {item["detector_id"]: item for item in self.catalog()["items"]}
        item = _clue_item(row, catalog)
        item["evidence_payload"] = _safe_evidence_payload(row.get("evidence_payload"))
        return {
            "ready": True,
            "source": SOURCE,
            "item": item,
            "semantic_caveats": SEMANTIC_CAVEATS,
            "warnings": [],
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
            "items": [_evidence_item(row, catalog) for _, row in evidence.iterrows()],
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
            "parameter_source": "admin_parameter_table",
            "parameter_editable": False,
            "personalized_parameter_profiles": "deferred_not_implemented",
            "display_filter_policy": "request_only_no_persistence",
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
    batch_dir = _default_batch_dir()
    if batch_dir:
        return DetectorResultService(open_detector_result_repository(batch_dir))
    return DetectorResultService(_empty_repository())


def _default_batch_dir() -> str | Path | None:
    batch_root = os.getenv("RISK_RESULT_BATCH_ROOT")
    if batch_root:
        return latest_detector_batch(batch_root)
    return os.getenv("RISK_RESULT_BATCH_DIR")


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
    manufacturer_code = _text(row.get("manufacturer_code")) or None
    manufacturer_display_name = _text(row.get("manufacturer_display_name")) or None
    hospital_code = _text(row.get("hospital_code")) or None
    hospital_display_name = _text(row.get("hospital_display_name")) or None
    drug_group = _text(row.get("drug_group")) or None
    drug_display_name = _text(row.get("drug_display_name")) or None
    return {
        "clue_id": _text(row.get("detector_clue_id")),
        "detector_clue_id": _text(row.get("detector_clue_id")),
        "detector_run_id": _text(row.get("detector_run_id")),
        "run_date": _text(row.get("run_date")),
        "tenant_id": _text(row.get("tenant_id")) or None,
        "manufacturer_code": manufacturer_code,
        "manufacturer_display_name": manufacturer_display_name,
        "manufacturer_name": manufacturer_display_name or manufacturer_code,
        "hospital_code": hospital_code,
        "hospital_display_name": hospital_display_name,
        "hospital_name": hospital_display_name or hospital_code,
        "drug_group": drug_group,
        "drug_display_name": drug_display_name,
        "drug_name": drug_display_name or drug_group,
        "region_display_name": _text(row.get("region_display_name")) or None,
        "product_line_name": _text(row.get("product_line_name")) or None,
        "detector_id": detector_id,
        "detector_family": _text(row.get("detector_family")),
        "detector_family_label": _detector_family_label(_text(row.get("detector_family"))),
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


def _result_item(row: pd.Series) -> dict[str, Any]:
    keys = [
        "detector_result_id", "run_id", "source_raw_batch_id", "observation_date",
        "manufacturer_code", "hospital_code", "drug_code", "purchase_unit", "detector_family",
        "detector_id", "detector_name", "detector_version", "config_id", "config_hash",
        "hit_flag", "severity", "confidence", "eligibility_status", "inapplicable_reason",
        "demand_shape_label", "evidence_window_start", "evidence_window_end", "current_value",
        "baseline_value", "comparison_value", "threshold_value", "threshold_operator",
        "evidence_payload", "evidence_text", "hit_reason", "caveat", "created_at",
    ]
    item = {key: _clean_value(row.get(key)) for key in keys}
    item["hit_flag"] = _bool(row.get("hit_flag"))
    item["confidence"] = _number_or_none(row.get("confidence"))
    item["evidence_payload"] = _safe_evidence_payload(row.get("evidence_payload"))
    return item


def _evidence_item(row: pd.Series, catalog: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    detector_id = _text(row.get("detector_id"))
    catalog_item = (catalog or {}).get(detector_id, {})
    detector_family = _text(row.get("detector_family"))
    payload = _json_object(row.get("evidence_payload"))
    contract = _evidence_contract(detector_id, catalog_item, payload)
    return {
        "risk_entity_id": _text(row.get("risk_entity_id")),
        "detector_run_id": _text(row.get("detector_run_id")),
        "run_date": _text(row.get("run_date")),
        "detector_id": detector_id,
        "detector_family": detector_family,
        "detector_family_label": _detector_family_label(detector_family),
        "detector_name": _text(catalog_item.get("detector_name") or detector_id),
        "detector_name_label": _text(catalog_item.get("detector_name") or detector_id),
        "detector_version": _text(payload.get("method") or catalog_item.get("method")) or None,
        "observation_date": _text(row.get("run_date")) or None,
        "hit_flag": _bool(row.get("hit_flag", True)),
        "detector_score": _number_or_none(row.get("detector_score")),
        "confidence": _number_or_none(row.get("confidence")),
        "root_cause_label": _text(row.get("root_cause_label")) or None,
        "evidence_text": _text(row.get("evidence_text")) or None,
        "evidence_payload": payload,
        "monitoring_logic": contract["monitoring_logic"],
        "observed_values": contract["observed_values"],
        "decision": contract["decision"],
        "caveat": _text(row.get("caveat")) or None,
        "created_at": _text(row.get("created_at")) or None,
    }


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _safe_evidence_payload(value: Any) -> Any:
    """Convert evidence to a JSON-safe value without inventing business meaning."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return value
    return _json_safe_value(value)


def _json_safe_value(value: Any) -> Any:
    if _is_missing(value):
        return None
    if hasattr(value, "item"):
        return _json_safe_value(value.item())
    if isinstance(value, dict):
        return {str(key): _json_safe_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe_value(item) for item in value]
    if isinstance(value, float) and math.isnan(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _matches_clue_context(
    row: dict[str, Any],
    *,
    detector_run_id: str | None,
    run_date: str | None,
    manufacturer_code: str | None,
) -> bool:
    return all(
        requested is None or _text(row.get(field)) == str(requested)
        for field, requested in {
            "detector_run_id": detector_run_id,
            "run_date": run_date,
            "manufacturer_code": manufacturer_code,
        }.items()
    )


def _evidence_contract(
    detector_id: str,
    catalog_item: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    method = _text(payload.get("method") or catalog_item.get("method"))
    if detector_id == "purchase_interval_ipi":
        return {
            "monitoring_logic": {
                "metric": "days_since_last_purchase",
                "current_window": "observation_date",
                "baseline_window": "entity historical purchase intervals",
                "formula": "(current_gap - historical_median_interval) / max(historical_MAD, mad_floor_days)",
                "eligibility": {"purchase_count": payload.get("purchase_count"), "min_purchase_count": payload.get("min_purchase_count")},
                "hit_condition": "robust_z >= z_hit and purchase_count >= min_purchase_count",
                "method": method,
            },
            "observed_values": {
                "current_gap_days": payload.get("current_gap_days", payload.get("days_since_last_purchase")),
                "historical_median_interval_days": payload.get("historical_median_interval_days", payload.get("median_days")),
                "historical_mad_days": payload.get("historical_mad_days", payload.get("mad_days")),
                "mad_floor_days": payload.get("mad_floor_days"),
                "purchase_count": payload.get("purchase_count"),
            },
            "decision": {"threshold_operator": ">=", "threshold_value": payload.get("z_hit"), "comparison_value": payload.get("robust_z"), "hit_reason": "采购间隔显著高于对象自身历史基准"},
        }
    if detector_id == "purchase_quantity_trend":
        return {
            "monitoring_logic": {
                "metric": "purchase_quantity",
                "current_window": payload.get("recent_window_months"),
                "baseline_window": payload.get("baseline_window_months"),
                "formula": "recent_quantity / baseline_quantity",
                "eligibility": {},
                "hit_condition": "quantity_ratio <= drop_ratio_hit",
                "method": method,
            },
            "observed_values": {"recent_quantity": payload.get("recent_quantity"), "baseline_quantity": payload.get("baseline_quantity")},
            "decision": {"threshold_operator": "<=", "threshold_value": payload.get("drop_ratio_hit"), "comparison_value": payload.get("quantity_ratio"), "hit_reason": "近期采购数量低于对象自身历史基准"},
        }
    if detector_id == "purchase_frequency_drop":
        return {
            "monitoring_logic": {
                "metric": "monthly_purchase_frequency",
                "current_window": payload.get("recent_window_months"),
                "baseline_window": payload.get("baseline_window_months"),
                "formula": "recent_frequency / baseline_frequency",
                "eligibility": {"baseline_frequency": payload.get("baseline_frequency", payload.get("base_rate")), "min_base_rate": payload.get("min_base_rate")},
                "hit_condition": "frequency_ratio <= freq_drop_ratio and baseline_frequency >= min_base_rate",
                "method": method,
            },
            "observed_values": {"recent_frequency": payload.get("recent_frequency"), "baseline_frequency": payload.get("baseline_frequency", payload.get("base_rate"))},
            "decision": {"threshold_operator": "<=", "threshold_value": payload.get("freq_drop_ratio"), "comparison_value": payload.get("frequency_ratio"), "hit_reason": "近期采购频次低于对象自身历史基准"},
        }
    return {
        "monitoring_logic": {"metric": None, "current_window": None, "baseline_window": None, "formula": None, "eligibility": {}, "hit_condition": None, "method": method},
        "observed_values": payload,
        "decision": {"threshold_operator": None, "threshold_value": None, "comparison_value": None, "hit_reason": None},
    }


def _detector_family_label(family: str | None) -> str | None:
    labels = {
        "interval": "采购间隔",
        "purchase_interval": "采购间隔",
        "quantity": "采购数量",
        "purchase_quantity": "采购数量",
        "frequency": "采购频次",
        "purchase_frequency": "采购频次",
        "assortment": "SKU 结构",
        "fulfillment": "履约交付",
        "price": "价格",
        "peer": "同群对比",
    }
    if not family:
        return None
    return labels.get(str(family), str(family))


def _merge_entity_display_lookup(frame: pd.DataFrame, repository: RiskResultRepository) -> pd.DataFrame:
    if frame.empty:
        return frame
    try:
        report_month = repository.manifest().report_month
        lookup = repository.load_entity_display_lookup(report_month=report_month)
    except (FileNotFoundError, NotImplementedError, ValueError, AttributeError, KeyError):
        return frame
    join_cols = ["tenant_id", "report_month", "manufacturer_code", "hospital_code", "drug_group"]
    out = frame.copy()
    if "report_month" not in out.columns:
        out["report_month"] = report_month
    if lookup.empty or not set(join_cols).issubset(out.columns) or not set(join_cols).issubset(lookup.columns):
        return frame
    display_cols = [
        "manufacturer_display_name",
        "hospital_display_name",
        "drug_display_name",
        "region_code",
        "region_display_name",
        "product_line_code",
        "product_line_name",
    ]
    available = [col for col in display_cols if col in lookup.columns]
    if not available:
        return frame
    lookup_slice = lookup[join_cols + available].drop_duplicates(join_cols, keep="first")
    lookup_slice = lookup_slice.rename(columns={col: f"{col}__lookup" for col in available})
    joined = out.merge(lookup_slice, on=join_cols, how="left")
    for col in available:
        lookup_col = f"{col}__lookup"
        lookup_values = joined[lookup_col].map(_text)
        current_values = joined[col].map(_text) if col in joined else pd.Series("", index=joined.index)
        joined[col] = lookup_values.where(lookup_values.str.len().gt(0), current_values)
        joined = joined.drop(columns=[lookup_col])
    return joined


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


def _deduplicate_clues(frame: pd.DataFrame) -> pd.DataFrame:
    """Keep one deterministic row per formal detector clue identity."""

    if frame.empty or "detector_clue_id" not in frame:
        return frame
    return frame.drop_duplicates(subset=["detector_clue_id"], keep="first")


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
