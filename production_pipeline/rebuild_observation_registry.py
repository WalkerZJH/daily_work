from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from pyarrow.lib import ArrowInvalid

from risk_result_contracts import write_production_parquet

from .common import detector_batch_dirs, monthly_batch_dirs, read_manifest


OBSERVATION_COLUMNS = [
    "observation_date", "probability_report_month", "probability_batch_id", "probability_batch_dir",
    "probability_batch_available", "detector_run_date", "detector_run_id", "detector_batch_id",
    "detector_batch_dir", "detector_run_available", "context_status", "manual_selection_required",
    "available_report_months", "available_detector_run_dates", "primary_horizon", "available_horizons", "caveat",
]
MANUFACTURER_COLUMNS = [
    "manufacturer_code", "manufacturer_display_name", "observation_date", "probability_report_month",
    "probability_batch_id", "probability_batch_available", "detector_run_date", "detector_batch_id",
    "detector_batch_dir", "detector_run_available", "available_horizons", "context_status", "display_lookup_status",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rebuild the date-exact monthly/Detector observation registry.")
    parser.add_argument("--batch-root", default="data/project_result_batches")
    args = parser.parse_args(argv)
    root = Path(args.batch_root)
    monthly_by_month = _discover_monthly_batches(root)
    detector_by_date = _discover_detector_batches(root)
    observation_rows: list[dict[str, Any]] = []
    manufacturer_rows: list[dict[str, Any]] = []

    # Detector availability is keyed only by its exact observation date.  A
    # matching monthly batch is optional and is selected only for the calendar
    # month that date requires; no other date or month may substitute for it.
    for observation_date, detector in sorted(detector_by_date.items()):
        probability_month = _expected_probability_report_month(observation_date)
        monthly = monthly_by_month.get(probability_month)
        observation_rows.append(_context_row(observation_date, probability_month, monthly, detector))
        for manufacturer in _merge_catalogs(
            _monthly_manufacturers(monthly) if monthly else [],
            _detector_manufacturers(detector),
        ):
            manufacturer_rows.append(
                _manufacturer_row(manufacturer, observation_date, probability_month, monthly, detector)
            )

    # Preserve an exact context for a monthly batch's declared observation date
    # when no independent Detector has been published for that date yet.
    for probability_month, monthly in sorted(monthly_by_month.items()):
        observation_date = _monthly_declared_observation_date(monthly)
        if not observation_date or observation_date in detector_by_date:
            continue
        expected_month = _expected_probability_report_month(observation_date)
        if expected_month != probability_month:
            continue
        observation_rows.append(_context_row(observation_date, probability_month, monthly, None))
        for manufacturer in _monthly_manufacturers(monthly):
            manufacturer_rows.append(
                _manufacturer_row(manufacturer, observation_date, probability_month, monthly, None)
            )

    observation = _frame(observation_rows, OBSERVATION_COLUMNS).drop_duplicates(
        ["observation_date", "probability_report_month", "detector_run_date"], keep="last"
    )
    manufacturer_registry = _frame(manufacturer_rows, MANUFACTURER_COLUMNS).drop_duplicates(
        ["manufacturer_code", "observation_date", "probability_report_month", "detector_run_date"], keep="last"
    )
    fill_available_fields(observation)
    root.mkdir(parents=True, exist_ok=True)
    write_production_parquet(observation, root / "available_observation_contexts.parquet")
    write_production_parquet(observation, root / "observation_registry.parquet")
    write_production_parquet(manufacturer_registry, root / "manufacturer_observation_registry.parquet")
    (root / "available_observation_contexts.json").write_text(
        json.dumps({"contexts": observation.to_dict(orient="records")}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    payload = {
        "stage": "observation_registry",
        "status": "ok",
        "batch_root": str(root).replace("\\", "/"),
        "monthly_batch_count": len(monthly_by_month),
        "detector_run_count": len(detector_by_date),
        "observation_rows": int(len(observation)),
        "manufacturer_observation_rows": int(len(manufacturer_registry)),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    (root / "registry_rebuild_status.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _discover_monthly_batches(root: Path) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for batch_dir in monthly_batch_dirs(root):
        manifest = read_manifest(batch_dir)
        report_month = str(manifest.get("report_month") or "")
        if manifest.get("report_type") != "monthly" or not report_month or not (batch_dir / "risk_entities.parquet").is_file():
            continue
        item = {"batch_dir": batch_dir, "manifest": manifest}
        if report_month not in selected or batch_dir.name > selected[report_month]["batch_dir"].name:
            selected[report_month] = item
    return selected


def _discover_detector_batches(root: Path) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for batch_dir in detector_batch_dirs(root):
        manifest = read_manifest(batch_dir)
        declared = manifest.get("detector_tables")
        if not isinstance(declared, dict) or not _detector_tables_exist(batch_dir, declared):
            continue
        runs = _read_columns(batch_dir / declared["daily_detector_runs"], ["detector_run_id", "run_date"])
        if runs.empty:
            continue
        for run_date, rows in runs.groupby(runs["run_date"].astype(str), sort=False):
            item = {
                "batch_dir": batch_dir,
                "manifest": manifest,
                "detector_run_id": str(rows.iloc[0].get("detector_run_id") or ""),
            }
            if run_date not in selected or batch_dir.name > selected[run_date]["batch_dir"].name:
                selected[run_date] = item
    return selected


def _detector_tables_exist(batch_dir: Path, declared: dict[str, Any]) -> bool:
    required = ("detector_catalog", "daily_detector_runs", "daily_detector_clues", "high_risk_detector_evidence")
    return all(isinstance(declared.get(name), str) and (batch_dir / declared[name]).is_file() for name in required)


def _context_row(
    observation_date: str,
    probability_month: str,
    monthly: dict[str, Any] | None,
    detector: dict[str, Any] | None,
) -> dict[str, Any]:
    monthly_manifest = monthly["manifest"] if monthly else {}
    detector_manifest = detector["manifest"] if detector else {}
    probability_available = monthly is not None
    detector_available = detector is not None
    return {
        "observation_date": observation_date,
        "probability_report_month": probability_month,
        "probability_batch_id": _batch_id(monthly_manifest) if monthly else "",
        "probability_batch_dir": _batch_path(monthly) if monthly else "",
        "probability_batch_available": probability_available,
        "detector_run_date": observation_date,
        "detector_run_id": detector.get("detector_run_id", "") if detector else "",
        "detector_batch_id": _batch_id(detector_manifest) if detector else "",
        "detector_batch_dir": _batch_path(detector) if detector else "",
        "detector_run_available": detector_available,
        "context_status": "ready" if probability_available and detector_available else (
            "detector_run_unavailable" if probability_available else "EXPECTED_MONTH_BATCH_UNAVAILABLE"
        ),
        "manual_selection_required": not (probability_available and detector_available),
        "available_report_months": "",
        "available_detector_run_dates": "",
        "primary_horizon": monthly_manifest.get("primary_horizon", ""),
        "available_horizons": ";".join(str(item) for item in monthly_manifest.get("available_horizons", [])),
        "caveat": "; ".join(
            str(item) for item in [*monthly_manifest.get("caveats", []), *detector_manifest.get("caveats", [])]
        ),
    }


def _manufacturer_row(
    manufacturer: dict[str, str],
    observation_date: str,
    probability_month: str,
    monthly: dict[str, Any] | None,
    detector: dict[str, Any] | None,
) -> dict[str, Any]:
    context = _context_row(observation_date, probability_month, monthly, detector)
    return {
        **manufacturer,
        **{key: context[key] for key in MANUFACTURER_COLUMNS if key in context},
        "display_lookup_status": display_lookup_status(manufacturer),
    }


def _monthly_manufacturers(monthly: dict[str, Any]) -> list[dict[str, str]]:
    batch_dir = monthly["batch_dir"]
    risk_entities = _read_columns(batch_dir / "risk_entities.parquet", ["manufacturer_code"])
    lookup = _read_columns(batch_dir / "entity_display_lookup.parquet", ["manufacturer_code", "manufacturer_display_name"])
    display_by_code = {
        str(row["manufacturer_code"]): str(row["manufacturer_display_name"])
        for _, row in lookup.dropna(subset=["manufacturer_code"]).drop_duplicates("manufacturer_code").iterrows()
        if str(row.get("manufacturer_display_name") or "")
    }
    return [
        {"manufacturer_code": code, "manufacturer_display_name": display_by_code.get(code, "")}
        for code in sorted(set(risk_entities.get("manufacturer_code", pd.Series(dtype=str)).dropna().astype(str)))
    ]


def _detector_manufacturers(detector: dict[str, Any]) -> list[dict[str, str]]:
    declared = detector["manifest"]["detector_tables"]
    clues = _read_columns(detector["batch_dir"] / declared["daily_detector_clues"], ["manufacturer_code"])
    return [
        {"manufacturer_code": code, "manufacturer_display_name": ""}
        for code in sorted(set(clues.get("manufacturer_code", pd.Series(dtype=str)).dropna().astype(str)))
    ]


def _merge_catalogs(*catalogs: list[dict[str, str]]) -> list[dict[str, str]]:
    merged: dict[str, dict[str, str]] = {}
    for catalog in catalogs:
        for item in catalog:
            code = str(item.get("manufacturer_code") or "")
            if not code:
                continue
            existing = merged.setdefault(code, {"manufacturer_code": code, "manufacturer_display_name": ""})
            if item.get("manufacturer_display_name"):
                existing["manufacturer_display_name"] = str(item["manufacturer_display_name"])
    return [merged[code] for code in sorted(merged)]


def _read_columns(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame(columns=columns)
    try:
        return pd.read_parquet(path, columns=columns)
    except (ArrowInvalid, KeyError, ValueError):
        # A legacy table can be structurally valid yet not contain an optional
        # registry projection such as manufacturer_code. Treat it as absent;
        # do not widen the read to a full-table scan.
        return pd.DataFrame(columns=columns)


def _batch_id(manifest: dict[str, Any]) -> str:
    return str(manifest.get("result_batch_id") or manifest.get("batch_id") or "")


def _batch_path(item: dict[str, Any]) -> str:
    return str(item["batch_dir"]).replace("\\", "/")


def _monthly_declared_observation_date(monthly: dict[str, Any]) -> str:
    manifest = monthly["manifest"]
    value = manifest.get("observation_date") or manifest.get("run_date") or manifest.get("report_date")
    try:
        return pd.Timestamp(value).date().isoformat() if value else ""
    except (TypeError, ValueError):
        return ""


def _expected_probability_report_month(observation_date: str) -> str:
    current = pd.Timestamp(observation_date).date().replace(day=1)
    return (current - pd.Timedelta(days=1)).strftime("%Y-%m")


def display_lookup_status(manufacturer: dict[str, str]) -> str:
    return "ready" if manufacturer.get("manufacturer_display_name") else "conditional"


def _frame(rows: list[dict[str, Any]], columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=columns)


def fill_available_fields(observation: pd.DataFrame) -> None:
    if observation.empty:
        return
    monthly = observation.loc[observation["probability_batch_available"].astype(bool), "probability_report_month"]
    detector = observation.loc[observation["detector_run_available"].astype(bool), "detector_run_date"]
    observation["available_report_months"] = ";".join(sorted(monthly.astype(str).unique().tolist()))
    observation["available_detector_run_dates"] = ";".join(sorted(detector.astype(str).unique().tolist()))


if __name__ == "__main__":
    raise SystemExit(main())
