"""Generate Project-consumable formal result batches for 2025-09..2025-12.

The script is model-side batch production. It may read algo_main source
artifacts, but it publishes only standard result-batch outputs under
data/project_result_batches for Project API consumption.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import calendar
import json
import shutil
import sys

import pandas as pd
import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from algo_main.scripts.export_current_v2_raw_input_batch_for_algorithm_core import (  # noqa: E402
    RAW_BATCH_DIR,
    build_raw_source_inventory,
    choose_orders_source,
    export_raw_batch,
)
from risk_algorithm_core.config import load_run_config  # noqa: E402
from risk_algorithm_core.monthly_runner import MonthlyRiskRunner  # noqa: E402
from risk_model_core.repositories import ParquetRiskResultRepository  # noqa: E402


TARGET_MONTHS = ["2025-09", "2025-10", "2025-11", "2025-12"]
OUTPUT_ROOT = ROOT / "data" / "project_result_batches"
FORMAL_CONFIG = ROOT / "configs" / "risk_algorithm_core" / "monthly_run.formal.example.yaml"
PARQUET_TABLES = [
    "daily_detector_clues",
    "daily_detector_runs",
    "entity_display_lookup",
    "risk_entities",
    "risk_entity_horizon_profiles",
]
STRING = pa.string()
CSV_COLUMN_TYPES = {
    "daily_detector_clues": {
        "detector_clue_id": STRING,
        "detector_run_id": STRING,
        "run_date": STRING,
        "tenant_id": STRING,
        "manufacturer_code": STRING,
        "hospital_code": STRING,
        "drug_group": STRING,
        "detector_id": STRING,
        "detector_family": STRING,
        "detector_score": pa.float64(),
        "detector_level": STRING,
        "confidence": pa.float64(),
        "hit_flag": pa.bool_(),
        "root_cause_label": STRING,
        "evidence_text": STRING,
        "evidence_payload": STRING,
        "is_monthly_high_risk_entity": pa.bool_(),
        "risk_entity_id": STRING,
        "monthly_risk_probability": pa.float64(),
        "monthly_loss_value": pa.float64(),
        "display_rank": pa.int64(),
        "caveat": STRING,
        "created_at": STRING,
    }
}


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    ensure_raw_batch()
    summaries = [run_month(month) for month in TARGET_MONTHS]
    registry = build_observation_registry([Path(item["batch_dir"]) for item in summaries])
    registry.to_csv(OUTPUT_ROOT / "available_observation_contexts.csv", index=False, encoding="utf-8")
    try:
        registry.to_parquet(OUTPUT_ROOT / "available_observation_contexts.parquet", index=False)
    except Exception:
        pass
    write_verification(summaries, registry)
    print("project_result_batches: ok")
    print("output_root:", OUTPUT_ROOT)
    print("observation_context_rows:", len(registry))


def ensure_raw_batch() -> None:
    inventory = build_raw_source_inventory()
    source = choose_orders_source(inventory)
    if source is None:
        raise FileNotFoundError("No current v2 raw/order source is available.")
    export_raw_batch(source)
    if not (RAW_BATCH_DIR / "manufacturer_master.parquet").exists():
        raise FileNotFoundError("manufacturer_master.parquet was not generated.")


def run_month(month: str) -> dict:
    cfg = load_run_config(FORMAL_CONFIG)
    detector_run_dates = next_month_dates(month)
    target = OUTPUT_ROOT / f"report_month={month}" / f"batch_id={month}-monthly-risk-algorithm-formal-v2-raw"
    if target.exists():
        shutil.rmtree(target)
    month_cfg = replace(
        cfg,
        report_month=month,
        run_date=detector_run_dates[0],
        output_root=str(OUTPUT_ROOT),
        detectors={**cfg.detectors, "run_dates": detector_run_dates},
    )
    summary = MonthlyRiskRunner(month_cfg).run(use_rule_baseline=False)
    batch_dir = Path(summary["batch_dir"])
    convert_hot_tables_to_parquet(batch_dir)
    repo = ParquetRiskResultRepository(batch_dir)
    runs = repo.list_daily_detector_runs()
    if set(runs["run_date"].astype(str)) != set(detector_run_dates):
        raise AssertionError(f"daily detector run_date coverage mismatch for {month}")
    return summary


def convert_hot_tables_to_parquet(batch_dir: Path) -> None:
    for table_name in PARQUET_TABLES:
        csv_path = batch_dir / f"{table_name}.csv"
        parquet_path = batch_dir / f"{table_name}.parquet"
        if not csv_path.exists():
            continue
        convert_options = pacsv.ConvertOptions(
            column_types=CSV_COLUMN_TYPES.get(table_name, {}),
            strings_can_be_null=True,
        )
        reader = pacsv.open_csv(
            csv_path,
            read_options=pacsv.ReadOptions(block_size=1 << 24),
            convert_options=convert_options,
        )
        writer = None
        try:
            for record_batch in reader:
                if writer is None:
                    writer = pq.ParquetWriter(parquet_path, record_batch.schema, compression="snappy")
                writer.write_batch(record_batch)
        finally:
            if writer is not None:
                writer.close()


def next_month_dates(month: str) -> list[str]:
    year, mon = [int(part) for part in month.split("-")]
    if mon == 12:
        year, mon = year + 1, 1
    else:
        mon += 1
    days = calendar.monthrange(year, mon)[1]
    return [f"{year:04d}-{mon:02d}-{day:02d}" for day in range(1, days + 1)]


def build_observation_registry(batch_dirs: list[Path]) -> pd.DataFrame:
    report_months = [path.parent.name.split("=", 1)[1] for path in batch_dirs]
    available_report_months = ";".join(report_months)
    all_run_dates: list[str] = []
    rows: list[dict[str, object]] = []
    for batch_dir in batch_dirs:
        repo = ParquetRiskResultRepository(batch_dir)
        manifest = repo.manifest()
        runs = repo.list_daily_detector_runs().sort_values("run_date", kind="mergesort")
        all_run_dates.extend(runs["run_date"].dropna().astype(str).tolist())
        batch_caveats = list(manifest.caveats or [])
        for _, run in runs.iterrows():
            run_date = str(run["run_date"])
            rows.append(
                {
                    "observation_date": run_date,
                    "probability_report_month": manifest.report_month,
                    "probability_batch_id": manifest.batch_id,
                    "probability_batch_dir": str(batch_dir.relative_to(ROOT)).replace("\\", "/"),
                    "probability_batch_available": True,
                    "detector_run_date": run_date,
                    "detector_run_id": str(run.get("detector_run_id") or ""),
                    "detector_run_available": True,
                    "context_status": "ready",
                    "manual_selection_required": False,
                    "available_report_months": available_report_months,
                    "available_detector_run_dates": "",
                    "primary_horizon": manifest.primary_horizon,
                    "available_horizons": ";".join(manifest.available_horizons),
                    "caveat": "; ".join([*batch_caveats, "project_result_batch_published_outside_algo_main"]),
                }
            )
    available_detector_run_dates = ";".join(sorted(set(all_run_dates)))
    for row in rows:
        row["available_detector_run_dates"] = available_detector_run_dates
    return pd.DataFrame(rows).sort_values(["observation_date", "probability_report_month"]).reset_index(drop=True)


def write_verification(summaries: list[dict], registry: pd.DataFrame) -> None:
    rows = []
    for summary in summaries:
        batch_dir = Path(summary["batch_dir"])
        repo = ParquetRiskResultRepository(batch_dir)
        lookup = repo.load_entity_display_lookup()
        runs = repo.list_daily_detector_runs()
        clues = repo.list_daily_detector_clues()
        rows.append(
            {
                "report_month": repo.manifest().report_month,
                "batch_dir": str(batch_dir.relative_to(ROOT)).replace("\\", "/"),
                "risk_entities": int(len(repo.list_risk_entities())),
                "daily_detector_runs": int(len(runs)),
                "daily_detector_clues": int(len(clues)),
                "display_lookup_rows": int(len(lookup)),
                "manufacturer_real_name_rows": int(_non_code_count(lookup, "manufacturer_code", "manufacturer_display_name")),
                "hospital_real_name_rows": int(_non_code_count(lookup, "hospital_code", "hospital_display_name")),
                "drug_real_name_rows": int(_non_code_count(lookup, "drug_code", "drug_display_name")),
            }
        )
    payload = {
        "output_root": str(OUTPUT_ROOT.relative_to(ROOT)).replace("\\", "/"),
        "target_months": TARGET_MONTHS,
        "observation_context_rows": int(len(registry)),
        "months": rows,
    }
    (OUTPUT_ROOT / "generation_verification.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _non_code_count(frame: pd.DataFrame, code_col: str, display_col: str) -> int:
    if frame.empty or code_col not in frame or display_col not in frame:
        return 0
    code = frame[code_col].fillna("").astype(str).str.strip()
    display = frame[display_col].fillna("").astype(str).str.strip()
    return int(((display != "") & (display != code)).sum())


if __name__ == "__main__":
    main()
