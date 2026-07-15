from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from risk_result_contracts import write_production_parquet

from .common import batch_dirs, read_manifest, read_parquet_table


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage D/E registry rebuild boundary.")
    parser.add_argument("--batch-root", default="data/project_result_batches")
    args = parser.parse_args(argv)
    root = Path(args.batch_root)
    observation_rows: list[dict[str, Any]] = []
    manufacturer_rows: list[dict[str, Any]] = []
    batches_by_month: dict[str, list[dict[str, Any]]] = {}
    for batch_dir in batch_dirs(root):
        manifest = read_manifest(batch_dir)
        report_month = str(manifest["report_month"])
        batches_by_month.setdefault(report_month, []).append(
            {
                "batch_dir": batch_dir,
                "manifest": manifest,
                "risk_entities": read_parquet_table(batch_dir, "risk_entities"),
                "lookup": read_parquet_table(batch_dir, "entity_display_lookup"),
                "detector_runs": _optional_parquet_table(batch_dir, "daily_detector_runs"),
            }
        )

    for report_month, batches in batches_by_month.items():
        monthly = max(batches, key=lambda item: item["batch_dir"].name)
        detector_sources = [item for item in batches if not item["detector_runs"].empty]
        detector = max(detector_sources, key=lambda item: item["batch_dir"].name) if detector_sources else None
        manifest = monthly["manifest"]
        batch_dir = monthly["batch_dir"]
        detector_runs = detector["detector_runs"] if detector is not None else pd.DataFrame()
        available_horizons = ";".join(str(item) for item in manifest.get("available_horizons", []))
        detector_dates = sorted(detector_runs.get("run_date", pd.Series(dtype=str)).astype(str).dropna().unique().tolist())
        if not detector_dates:
            detector_dates = [str(manifest.get("run_date") or manifest.get("report_date") or report_month)]
        manufacturers = manufacturer_catalog(monthly["risk_entities"], monthly["lookup"])
        for run_date in detector_dates:
            detector_available = detector is not None
            detector_manifest = detector["manifest"] if detector is not None else {}
            detector_batch_dir = detector["batch_dir"] if detector is not None else None
            observation_rows.append(
                {
                    "observation_date": run_date,
                    "probability_report_month": report_month,
                    "probability_batch_id": manifest.get("result_batch_id") or manifest.get("batch_id"),
                    "probability_batch_dir": str(batch_dir).replace("\\", "/"),
                    "probability_batch_available": True,
                    "detector_run_date": run_date,
                    "detector_run_id": detector_run_id(detector_runs, run_date),
                    "detector_batch_id": detector_manifest.get("result_batch_id") or detector_manifest.get("batch_id") or "",
                    "detector_batch_dir": str(detector_batch_dir).replace("\\", "/") if detector_batch_dir else "",
                    "detector_run_available": detector_available,
                    "context_status": "ready" if detector_available else "detector_run_unavailable",
                    "manual_selection_required": not detector_available,
                    "available_report_months": "",
                    "available_detector_run_dates": "",
                    "primary_horizon": manifest.get("primary_horizon"),
                    "available_horizons": available_horizons,
                    "caveat": "; ".join(str(item) for item in manifest.get("caveats", [])),
                }
            )
            for manufacturer in manufacturers:
                manufacturer_rows.append(
                    {
                        **manufacturer,
                        "observation_date": run_date,
                        "probability_report_month": report_month,
                        "probability_batch_id": manifest.get("result_batch_id") or manifest.get("batch_id"),
                        "probability_batch_available": True,
                        "detector_run_date": run_date,
                        "detector_batch_id": detector_manifest.get("result_batch_id") or detector_manifest.get("batch_id") or "",
                        "detector_batch_dir": str(detector_batch_dir).replace("\\", "/") if detector_batch_dir else "",
                        "detector_run_available": detector_available,
                        "available_horizons": available_horizons,
                        "context_status": "ready" if detector_available else "detector_run_unavailable",
                        "display_lookup_status": display_lookup_status(manufacturer),
                    }
                )
    observation = pd.DataFrame(observation_rows).drop_duplicates(
        ["observation_date", "probability_report_month", "detector_run_date"], keep="first"
    )
    manufacturer_registry = pd.DataFrame(manufacturer_rows).drop_duplicates(
        ["manufacturer_code", "observation_date", "probability_report_month", "detector_run_date"], keep="first"
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
        "observation_rows": int(len(observation)),
        "manufacturer_observation_rows": int(len(manufacturer_registry)),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    (root / "registry_rebuild_status.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def detector_run_id(detector_runs: pd.DataFrame, run_date: str) -> str:
    rows = detector_runs[detector_runs["run_date"].astype(str).eq(str(run_date))]
    if rows.empty:
        return ""
    return str(rows.iloc[0].get("detector_run_id") or "")


def _optional_parquet_table(batch_dir: Path, table: str) -> pd.DataFrame:
    path = batch_dir / f"{table}.parquet"
    return read_parquet_table(batch_dir, table) if path.exists() else pd.DataFrame()


def manufacturer_catalog(risk_entities: pd.DataFrame, lookup: pd.DataFrame) -> list[dict[str, str]]:
    codes = sorted(set(risk_entities["manufacturer_code"].astype(str).dropna().tolist()))
    display_by_code: dict[str, str] = {}
    if not lookup.empty and {"manufacturer_code", "manufacturer_display_name"}.issubset(lookup.columns):
        for _, row in lookup[["manufacturer_code", "manufacturer_display_name"]].drop_duplicates().iterrows():
            code = str(row["manufacturer_code"])
            name = str(row.get("manufacturer_display_name") or "")
            if name and name != code:
                display_by_code.setdefault(code, name)
    return [
        {
            "manufacturer_code": code,
            "manufacturer_display_name": display_by_code.get(code, ""),
        }
        for code in codes
    ]


def display_lookup_status(manufacturer: dict[str, str]) -> str:
    name = manufacturer.get("manufacturer_display_name") or ""
    code = manufacturer.get("manufacturer_code") or ""
    if name and name != code:
        return "ready"
    return "conditional"


def fill_available_fields(observation: pd.DataFrame) -> None:
    if observation.empty:
        return
    months = ";".join(sorted(observation["probability_report_month"].astype(str).unique().tolist()))
    dates = ";".join(sorted(observation["detector_run_date"].astype(str).unique().tolist()))
    observation["available_report_months"] = months
    observation["available_detector_run_dates"] = dates


if __name__ == "__main__":
    raise SystemExit(main())
