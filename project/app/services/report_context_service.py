from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from risk_model_core import ParquetRiskResultRepository, RiskResultRepository, open_detector_result_repository  # noqa: E402
from app.services.result_batch_discovery import latest_monthly_batch


class ReportContextService:
    def __init__(
        self,
        repository: RiskResultRepository | None = None,
        *,
        batch_root: str | Path | None = None,
        legacy_single_batch: bool = False,
    ):
        self.repository = repository
        self.batch_root = Path(batch_root) if batch_root else None
        self.legacy_single_batch = legacy_single_batch

    def resolve(
        self,
        *,
        observation_date: str | None = None,
        report_month: str | None = None,
        run_date: str | None = None,
        horizon: str | None = None,
        manufacturer_code: str | None = None,
        user_id: str | None = None,
        manual_report_month: bool = False,
    ) -> dict[str, Any]:
        requested_observation_date = observation_date or run_date
        if self.repository is None:
            return _unavailable_context(
                observation_date=requested_observation_date,
                report_month=report_month,
                run_date=run_date,
                horizon=horizon,
            )
        if self.batch_root is not None:
            return self._resolve_observation_context(
                observation_date=requested_observation_date,
                report_month=report_month,
                run_date=run_date,
                horizon=horizon,
                manufacturer_code=manufacturer_code,
                user_id=user_id,
                manual_report_month=manual_report_month,
            )
        return self._resolve_legacy_single_batch_context(
            observation_date=requested_observation_date,
            report_month=report_month,
            run_date=run_date,
            horizon=horizon,
            manufacturer_code=manufacturer_code,
            user_id=user_id,
        )

    def probability_repository(self, context: dict[str, Any]) -> RiskResultRepository | None:
        if not context.get("probability_batch_available"):
            return None
        if self.batch_root is None:
            return self.repository
        path_text = context.get("probability_batch_dir") or context.get("batch_dir")
        if not path_text:
            return self.repository
        path = _resolve_batch_path(path_text)
        if not path.exists():
            return None
        return ParquetRiskResultRepository(path)

    def detector_repository(self, context: dict[str, Any]) -> RiskResultRepository | None:
        if not context.get("detector_run_available"):
            return None
        if self.batch_root is None:
            return self.repository
        path_text = context.get("detector_batch_dir") or context.get("probability_batch_dir")
        if not path_text:
            return None
        path = _resolve_batch_path(path_text)
        return (
            open_detector_result_repository(
                path,
                display_lookup_repository=self.probability_repository(context),
            )
            if path.exists()
            else None
        )

    def _resolve_observation_context(
        self,
        *,
        observation_date: str | None,
        report_month: str | None,
        run_date: str | None,
        horizon: str | None,
        manufacturer_code: str | None,
        user_id: str | None,
        manual_report_month: bool,
    ) -> dict[str, Any]:
        try:
            resolved = self.repository.resolve_observation_context(
                observation_date=observation_date,
                requested_report_month=report_month,
                requested_detector_run_date=None,
                requested_horizon=horizon,
                batch_root=self.batch_root,
                manual_report_month=manual_report_month,
            )
        except (FileNotFoundError, ValueError, KeyError, NotImplementedError, AttributeError):
            return _unavailable_context(
                observation_date=observation_date,
                report_month=report_month,
                run_date=run_date,
                horizon=horizon,
            )
        context = _normalize_observation_context(
            dict(resolved),
            requested_observation_date=observation_date,
            requested_report_month=report_month,
            requested_run_date=run_date,
            requested_horizon=horizon,
            manufacturer_code=manufacturer_code,
            user_id=user_id,
            context_mode="observation_root",
            manual_report_month=manual_report_month,
        )
        return context

    def _resolve_legacy_single_batch_context(
        self,
        *,
        observation_date: str | None,
        report_month: str | None,
        run_date: str | None,
        horizon: str | None,
        manufacturer_code: str | None,
        user_id: str | None,
    ) -> dict[str, Any]:
        try:
            resolved = self.repository.resolve_report_context(
                requested_report_month=report_month,
                requested_run_date=run_date or observation_date,
                requested_horizon=horizon,
            )
        except (FileNotFoundError, ValueError, KeyError, NotImplementedError, AttributeError):
            return _unavailable_context(
                observation_date=observation_date,
                report_month=report_month,
                run_date=run_date,
                horizon=horizon,
            )
        context = self._normalize_legacy_report_context(
            dict(resolved),
            observation_date=observation_date or run_date,
            report_month=report_month,
            run_date=run_date,
            horizon=horizon,
            manufacturer_code=manufacturer_code,
            user_id=user_id,
        )
        context["legacy_single_batch_limited"] = True
        context["warnings"] = [
            *list(context.get("warnings") or []),
            "RISK_RESULT_BATCH_ROOT_NOT_CONFIGURED; using legacy single batch context.",
        ]
        return context

    def _normalize_legacy_report_context(
        self,
        context: dict[str, Any],
        *,
        observation_date: str | None,
        report_month: str | None,
        run_date: str | None,
        horizon: str | None,
        manufacturer_code: str | None,
        user_id: str | None,
    ) -> dict[str, Any]:
        context = self._normalize_legacy_detector_run_context(
            context,
            requested_run_date=run_date or observation_date,
        )
        effective_report_month = _none_if_blank(context.get("effective_report_month"))
        effective_run_date = _none_if_blank(context.get("effective_run_date"))
        status = _none_if_blank(context.get("date_resolution_status")) or "legacy_single_batch"
        context.update(
            {
                "ready": bool(context.get("ready", True)),
                "partial_ready": False,
                "observation_date": observation_date or effective_run_date,
                "probability_report_month": effective_report_month,
                "probability_batch_id": context.get("batch_id"),
                "probability_batch_dir": context.get("batch_dir"),
                "probability_batch_available": bool(context.get("ready", True)),
                "detector_run_date": effective_run_date,
                "detector_run_id": None,
                "detector_run_available": bool(effective_run_date),
                "context_status": status,
                "context_mode": "legacy_single_batch_limited",
                "manual_selection_required": bool(context.get("fallback_used")),
                "available_detector_run_dates": list(context.get("available_run_dates") or []),
                "requested_observation_date": observation_date,
                "requested_report_month": report_month,
                "requested_run_date": run_date,
                "requested_horizon": horizon,
                "requested_manufacturer_code": manufacturer_code,
                "requested_user_id": user_id,
            }
        )
        context["available_report_months"] = _split_context_value(context.get("available_report_months"))
        context["available_detector_run_dates"] = _split_context_value(context.get("available_detector_run_dates"))
        context["warnings"] = [str(item) for item in list(context.get("warnings") or []) if str(item)]
        context["caveats"] = _split_context_value(context.get("caveats") or context.get("caveat"))
        return context

    def _normalize_legacy_detector_run_context(
        self,
        context: dict[str, Any],
        *,
        requested_run_date: str | None,
    ) -> dict[str, Any]:
        try:
            contexts = self.repository.list_available_report_contexts() if self.repository is not None else None
        except (FileNotFoundError, ValueError, KeyError, NotImplementedError, AttributeError):
            return context
        if contexts is None or contexts.empty or "detector_run_date" not in contexts:
            return context

        detector_dates = sorted(
            {
                date
                for value in contexts["detector_run_date"].dropna().tolist()
                for date in _split_context_value(value)
            },
            reverse=True,
        )
        if not detector_dates:
            return context
        requested = str(requested_run_date) if requested_run_date else None
        context["available_batch_run_dates"] = list(context.get("available_run_dates") or [])
        context["available_run_dates"] = detector_dates
        context["effective_batch_run_date"] = context.get("effective_run_date")
        context["effective_run_date"] = requested if requested in detector_dates else detector_dates[0]
        if requested and requested in detector_dates:
            context["fallback_used"] = False
            if context.get("date_resolution_status") == "fallback_to_latest_available":
                context["date_resolution_status"] = "exact_match"
        elif requested:
            context["fallback_used"] = True
            context["date_resolution_status"] = "fallback_to_latest_available"
        return context


def build_default_report_context_service() -> ReportContextService:
    batch_root = os.getenv("RISK_RESULT_BATCH_ROOT")
    if batch_root:
        root = Path(batch_root)
        batch_dir = _default_batch_dir_from_root(root)
        if root.exists() and batch_dir is not None and (batch_dir / "manifest.json").exists():
            return ReportContextService(
                ParquetRiskResultRepository(batch_dir),
                batch_root=root,
            )
        return ReportContextService(None)

    batch_dir = os.getenv("RISK_RESULT_BATCH_DIR")
    if not batch_dir:
        return ReportContextService(None)
    path = Path(batch_dir)
    if not path.exists() or not (path / "manifest.json").exists():
        return ReportContextService(None)
    return ReportContextService(
        ParquetRiskResultRepository(path),
        legacy_single_batch=True,
    )


def _normalize_observation_context(
    context: dict[str, Any],
    *,
    requested_observation_date: str | None,
    requested_report_month: str | None,
    requested_run_date: str | None,
    requested_horizon: str | None,
    manufacturer_code: str | None,
    user_id: str | None,
    context_mode: str,
    manual_report_month: bool = False,
) -> dict[str, Any]:
    probability_report_month = _none_if_blank(context.get("probability_report_month"))
    expected_probability_report_month = _none_if_blank(
        context.get("expected_probability_report_month")
    ) or probability_report_month
    effective_probability_report_month = _none_if_blank(
        context.get("effective_probability_report_month")
    ) or (probability_report_month if context.get("probability_batch_available") else None)
    detector_run_date = _none_if_blank(context.get("detector_run_date"))
    observation_date = _none_if_blank(context.get("observation_date")) or requested_observation_date
    effective_observation_date = _none_if_blank(context.get("effective_observation_date")) or observation_date
    status = _none_if_blank(context.get("context_status")) or (
        "ready" if context.get("ready") else "manual_selection_required"
    )
    context.update(
        {
            "ready": bool(context.get("ready")),
            "partial_ready": bool(context.get("probability_batch_available")) and not bool(context.get("detector_run_available")),
            "observation_date": observation_date,
            "effective_observation_date": effective_observation_date,
            "probability_report_month": probability_report_month,
            "expected_probability_report_month": expected_probability_report_month,
            "effective_probability_report_month": effective_probability_report_month,
            "detector_run_date": detector_run_date,
            "detector_batch_id": _none_if_blank(context.get("detector_batch_id")),
            "detector_batch_dir": _none_if_blank(context.get("detector_batch_dir")),
            "context_status": status,
            "context_mode": context_mode,
            "manual_report_month": bool(context.get("manual_report_month", manual_report_month)),
            "requested_observation_date": requested_observation_date,
            "requested_report_month": requested_report_month,
            "requested_run_date": requested_run_date,
            "requested_horizon": requested_horizon,
            "effective_report_month": effective_probability_report_month,
            "effective_run_date": detector_run_date,
            "date_resolution_status": status,
            "fallback_used": False,
            "is_exact_match": status == "ready",
            "requested_manufacturer_code": manufacturer_code,
            "requested_user_id": user_id,
        }
    )
    if "effective_horizon" not in context:
        context["effective_horizon"] = requested_horizon or "H6"
    context["available_report_months"] = _split_context_value(context.get("available_report_months"))
    context["available_detector_run_dates"] = _split_context_value(context.get("available_detector_run_dates"))
    if "available_run_dates" not in context:
        context["available_run_dates"] = list(context["available_detector_run_dates"])
    context["warnings"] = [str(item) for item in list(context.get("warnings") or []) if str(item)]
    context["caveats"] = _split_context_value(context.get("caveats") or context.get("caveat"))
    return context


def _unavailable_context(
    *,
    observation_date: str | None,
    report_month: str | None,
    run_date: str | None,
    horizon: str | None,
) -> dict[str, Any]:
    return {
        "ready": False,
        "partial_ready": False,
        "observation_date": observation_date,
        "probability_report_month": report_month,
        "probability_batch_id": None,
        "probability_batch_dir": None,
        "probability_batch_available": False,
        "detector_run_date": observation_date or run_date,
        "detector_run_id": None,
        "detector_batch_id": None,
        "detector_batch_dir": None,
        "detector_run_available": False,
        "context_status": "no_available_context",
        "context_mode": "unavailable",
        "manual_selection_required": True,
        "available_report_months": [],
        "available_detector_run_dates": [],
        "requested_observation_date": observation_date,
        "requested_report_month": report_month,
        "requested_run_date": run_date,
        "requested_horizon": horizon,
        "effective_report_month": None,
        "effective_run_date": observation_date or run_date,
        "effective_horizon": None,
        "date_resolution_status": "no_available_context",
        "fallback_used": False,
        "is_exact_match": False,
        "warnings": ["RISK_RESULT_BATCH_ROOT_OR_DIR_NOT_CONFIGURED_OR_UNREADABLE"],
        "caveats": [],
    }


def _default_batch_dir_from_root(root: Path) -> Path | None:
    return latest_monthly_batch(root)


def _resolve_batch_path(path_text: Any) -> Path:
    path = Path(str(path_text))
    if path.is_absolute():
        return path
    root_candidate = REPO_ROOT / path
    return root_candidate if root_candidate.exists() else path


def _split_context_value(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if value is None:
        return []
    text = str(value)
    if not text or text.lower() == "nan":
        return []
    return [part.strip() for part in text.split(";") if part.strip() and part.strip().lower() != "nan"]


def _none_if_blank(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    if not text or text.lower() == "nan":
        return None
    return text
