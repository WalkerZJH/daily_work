from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from risk_model_core import ParquetRiskResultRepository, RiskResultRepository  # noqa: E402


class ReportContextService:
    def __init__(self, repository: RiskResultRepository | None = None):
        self.repository = repository

    def resolve(
        self,
        *,
        report_month: str | None = None,
        run_date: str | None = None,
        horizon: str | None = None,
        manufacturer_code: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        if self.repository is None:
            return _unavailable_context(report_month, run_date, horizon)
        try:
            resolved = self.repository.resolve_report_context(
                requested_report_month=report_month,
                requested_run_date=run_date,
                requested_horizon=horizon,
            )
        except (FileNotFoundError, ValueError, KeyError, NotImplementedError, AttributeError):
            return _unavailable_context(report_month, run_date, horizon)
        resolved = self._normalize_detector_run_context(
            dict(resolved),
            requested_run_date=run_date,
        )
        return {
            **resolved,
            "requested_manufacturer_code": manufacturer_code,
            "requested_user_id": user_id,
        }

    def _normalize_detector_run_context(
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

        rows = contexts.copy()
        selected = rows
        batch_id = str(context.get("batch_id") or "")
        if batch_id and "batch_id" in selected:
            batch_rows = selected[selected["batch_id"].astype(str).eq(batch_id)]
            if not batch_rows.empty:
                selected = batch_rows
        report_month = str(context.get("effective_report_month") or "")
        if report_month and "report_month" in selected:
            month_rows = selected[selected["report_month"].astype(str).eq(report_month)]
            if not month_rows.empty:
                selected = month_rows

        detector_dates = sorted(
            {
                date
                for value in selected["detector_run_date"].dropna().tolist()
                for date in _split_context_value(value)
            },
            reverse=True,
        )
        if not detector_dates:
            return context

        requested = str(requested_run_date) if requested_run_date else None
        effective_detector_run_date = requested if requested in detector_dates else detector_dates[0]
        batch_run_date = context.get("effective_run_date")
        context["effective_batch_run_date"] = batch_run_date
        context["detector_run_date"] = effective_detector_run_date
        context["available_batch_run_dates"] = list(context.get("available_run_dates") or [])
        context["available_run_dates"] = detector_dates
        context["effective_run_date"] = effective_detector_run_date

        requested_report_month = context.get("requested_report_month")
        requested_horizon = context.get("requested_horizon")
        report_month_exact = not requested_report_month or str(requested_report_month) == str(context.get("effective_report_month"))
        run_date_exact = not requested or requested == effective_detector_run_date
        horizon_exact = not requested_horizon or str(requested_horizon) == str(context.get("effective_horizon"))
        exact = report_month_exact and run_date_exact and horizon_exact
        context["is_exact_match"] = exact
        context["fallback_used"] = not exact
        if exact:
            context["date_resolution_status"] = "exact_match"
            context["warnings"] = [
                warning
                for warning in list(context.get("warnings") or [])
                if "run_date is unavailable" not in str(warning)
            ]
        elif not report_month_exact and run_date_exact and horizon_exact:
            context["date_resolution_status"] = "fallback_to_latest_report_month"
        else:
            context["date_resolution_status"] = "fallback_to_latest_available"
        return context


def build_default_report_context_service() -> ReportContextService:
    batch_dir = os.getenv("RISK_RESULT_BATCH_DIR")
    if not batch_dir:
        return ReportContextService(None)
    path = Path(batch_dir)
    if not path.exists() or not (path / "manifest.json").exists():
        return ReportContextService(None)
    return ReportContextService(ParquetRiskResultRepository(path))


def _unavailable_context(
    report_month: str | None,
    run_date: str | None,
    horizon: str | None,
) -> dict[str, Any]:
    return {
        "ready": False,
        "requested_report_month": report_month,
        "effective_report_month": None,
        "requested_run_date": run_date,
        "effective_run_date": None,
        "requested_horizon": horizon,
        "effective_horizon": None,
        "date_resolution_status": "no_available_batch",
        "batch_id": None,
        "batch_dir": None,
        "available_report_months": [],
        "available_run_dates": [],
        "available_horizons": [],
        "is_exact_match": False,
        "fallback_used": False,
        "warnings": ["RISK_RESULT_BATCH_DIR_NOT_CONFIGURED_OR_UNREADABLE"],
        "caveats": [],
    }


def _split_context_value(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if value is None:
        return []
    text = str(value)
    if not text:
        return []
    return [part.strip() for part in text.split(";") if part.strip()]
