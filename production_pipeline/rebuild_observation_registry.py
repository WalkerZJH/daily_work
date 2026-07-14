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
    for batch_dir in batch_dirs(root):
        manifest = read_manifest(batch_dir)
        report_month = str(manifest["report_month"])
        detector_runs = read_parquet_table(batch_dir, "daily_detector_runs")
        risk_entities = read_parquet_table(batch_dir, "risk_entities")
        lookup = read_parquet_table(batch_dir, "entity_display_lookup")
        available_horizons = ";".join(str(item) for item in manifest.get("available_horizons", []))
        detector_dates = sorted(detector_runs["run_date"].astype(str).dropna().unique().tolist())
        manufacturers = manufacturer_catalog(risk_entities, lookup)
        for run_date in detector_dates:
            observation_rows.append(
                {
                    "observation_date": run_date,
                    "probability_report_month": report_month,
                    "probability_batch_id": manifest.get("result_batch_id") or manifest.get("batch_id"),
                    "probability_batch_dir": str(batch_dir).replace("\\", "/"),
                    "probability_batch_available": True,
                    "detector_run_date": run_date,
                    "detector_run_id": detector_run_id(detector_runs, run_date),
                    "detector_run_available": True,
                    "context_status": "ready",
                    "manual_selection_required": False,
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
                        "detector_run_available": True,
                        "available_horizons": available_horizons,
                        "context_status": "ready",
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
