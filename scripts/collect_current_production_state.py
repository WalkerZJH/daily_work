from __future__ import annotations

import csv
import hashlib
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq


REPO = Path(__file__).resolve().parents[1]
BATCH_ROOT = REPO / "data" / "project_result_batches"
REPORT_PATH = REPO / "reports" / "current_production_state_baseline.json"
API_BASE_URL = os.environ.get("PROJECT_API_BASE_URL", "http://127.0.0.1:18080")
LARGE_CSV_ROW_COUNT_LIMIT_BYTES = 100 * 1024 * 1024
_SHA256_CACHE: dict[Path, str] = {}

FORMAL_TABLES = [
    "risk_entities",
    "risk_entity_horizon_profiles",
    "monthly_reports",
    "proof_cases",
    "risk_cards",
    "risk_card_evidence",
    "risk_entity_timeline",
    "hospital_aggregates",
    "drug_aggregates",
    "work_order_reserved",
    "oneshot_terminals",
    "entity_display_lookup",
    "detector_catalog",
    "daily_detector_runs",
    "daily_detector_clues",
    "high_risk_detector_evidence",
    "observation_registry",
    "manufacturer_observation_registry",
]

CHECKSUM_PATTERNS = [
    "manifest.json",
    "risk_entities.*",
    "risk_entity_horizon_profiles.*",
    "monthly_reports.*",
    "daily_detector_runs.*",
    "daily_detector_clues.*",
    "high_risk_detector_evidence.*",
    "entity_display_lookup.*",
    "available_observation_contexts.*",
    "observation_registry.*",
    "manufacturer_observation_registry.*",
]


def rel(path: Path) -> str:
    return str(path.relative_to(REPO)).replace("\\", "/")


def sha256(path: Path) -> str:
    cached = _SHA256_CACHE.get(path)
    if cached:
        return cached
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    value = digest.hexdigest()
    _SHA256_CACHE[path] = value
    return value


def parquet_metadata(path: Path) -> tuple[int, list[str]]:
    parquet_file = pq.ParquetFile(path)
    return parquet_file.metadata.num_rows, parquet_file.schema.names


def csv_metadata(path: Path) -> tuple[int | None, list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            columns = next(reader)
        except StopIteration:
            return 0, []
        if path.stat().st_size > LARGE_CSV_ROW_COUNT_LIMIT_BYTES:
            return None, [str(column) for column in columns]
        return sum(1 for _ in reader), [str(column) for column in columns]


def read_table_sample(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path, columns=columns)
    if path.suffix == ".csv":
        if columns:
            return pd.read_csv(path, usecols=lambda col: col in set(columns))
        return pd.read_csv(path)
    raise ValueError(f"Unsupported table format: {path}")


def table_summary(path: Path) -> dict[str, Any]:
    if path.suffix == ".parquet":
        row_count, columns = parquet_metadata(path)
    elif path.suffix == ".csv":
        row_count, columns = csv_metadata(path)
    else:
        row_count, columns = 0, []
    summary: dict[str, Any] = {
        "path": rel(path),
        "suffix": path.suffix,
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "row_count": row_count,
        "columns": columns,
    }
    if path.suffix == ".csv" and row_count is None:
        summary["row_count_note"] = "not_counted_for_large_csv_in_baseline"
    if path.stem == "entity_display_lookup":
        summary["lookup_profile"] = lookup_profile(path, columns)
    if path.stem == "daily_detector_runs":
        summary["detector_run_profile"] = detector_run_profile(path, columns)
    return summary


def lookup_profile(path: Path, columns: list[str]) -> dict[str, Any]:
    interesting = [
        "manufacturer_code",
        "manufacturer_name",
        "manufacturer_display_name",
        "hospital_code",
        "hospital_name",
        "hospital_display_name",
        "drug_code",
        "drug_name",
        "drug_display_name",
    ]
    usecols = [column for column in interesting if column in columns]
    frame = read_table_sample(path, usecols)
    profile: dict[str, Any] = {"row_count": int(len(frame)), "columns": list(frame.columns)}
    for key in usecols:
        series = frame[key].astype("string").fillna("")
        profile[f"{key}_non_empty"] = int(series.str.len().gt(0).sum())
    pairs = [
        ("manufacturer_display_name", "manufacturer_code"),
        ("manufacturer_name", "manufacturer_code"),
        ("hospital_display_name", "hospital_code"),
        ("hospital_name", "hospital_code"),
        ("drug_display_name", "drug_code"),
        ("drug_name", "drug_code"),
    ]
    for name_col, code_col in pairs:
        if name_col not in frame.columns or code_col not in frame.columns:
            continue
        names = frame[name_col].astype("string").fillna("")
        codes = frame[code_col].astype("string").fillna("")
        denom = int(names.str.len().gt(0).sum())
        equal = int(((names == codes) & names.str.len().gt(0)).sum())
        profile[f"{name_col}_equals_{code_col}"] = equal
        profile[f"{name_col}_equals_{code_col}_ratio"] = equal / denom if denom else None
    return profile


def detector_run_profile(path: Path, columns: list[str]) -> dict[str, Any]:
    candidates = ["run_date", "detector_run_date", "observation_date"]
    date_col = next((column for column in candidates if column in columns), None)
    if not date_col:
        return {"date_column": None}
    frame = read_table_sample(path, [date_col])
    dates = sorted(frame[date_col].astype("string").dropna().unique().tolist())
    return {
        "date_column": date_col,
        "date_count": len(dates),
        "min_date": dates[0] if dates else None,
        "max_date": dates[-1] if dates else None,
    }


def manifest_declared_tables(manifest: dict[str, Any]) -> dict[str, Any]:
    declared: dict[str, Any] = {}
    for key in ["tables", "result_tables", "detector_tables", "files"]:
        value = manifest.get(key)
        if not isinstance(value, dict):
            continue
        for table, meta in value.items():
            if isinstance(meta, dict):
                path = meta.get("path") or meta.get("file") or meta.get("file_path")
                declared[str(table)] = {"raw": meta, "path": path}
            else:
                declared[str(table)] = {"raw": meta, "path": meta if isinstance(meta, str) else None}
    counts = manifest.get("result_table_row_counts")
    if isinstance(counts, dict):
        for table, count in counts.items():
            declared.setdefault(str(table), {})["manifest_row_count"] = count
    return declared


def collect_batch(batch_dir: Path) -> dict[str, Any]:
    manifest_path = batch_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    files_by_stem: dict[str, list[Path]] = {}
    for path in sorted(batch_dir.iterdir()):
        if path.is_file():
            files_by_stem.setdefault(path.stem, []).append(path)
    table_files = {
        table: [table_summary(path) for path in files_by_stem.get(table, [])]
        for table in FORMAL_TABLES
    }
    csv_parquet_pairs = [
        stem
        for stem, paths in files_by_stem.items()
        if any(path.suffix == ".csv" for path in paths)
        and any(path.suffix == ".parquet" for path in paths)
    ]
    declared = manifest_declared_tables(manifest)
    mismatches = manifest_mismatches(batch_dir, manifest, declared, files_by_stem)
    return {
        "report_month": batch_dir.parent.name.replace("report_month=", ""),
        "batch_id": batch_dir.name.replace("batch_id=", ""),
        "batch_path": rel(batch_dir),
        "manifest_path": rel(manifest_path) if manifest_path.exists() else None,
        "manifest_data_backend": manifest.get("data_backend"),
        "manifest_declared_tables": declared,
        "manifest_summary": {
            key: manifest.get(key)
            for key in [
                "batch_id",
                "result_batch_id",
                "report_month",
                "run_date",
                "report_date",
                "score_as_of_date",
                "cutoff_date",
                "model_artifact_id",
                "available_horizons",
                "primary_horizon",
                "data_backend",
            ]
        },
        "table_files": table_files,
        "csv_parquet_pairs": csv_parquet_pairs,
        "manifest_mismatches": mismatches,
        "all_files": [rel(path) for path in sorted(batch_dir.iterdir()) if path.is_file()],
    }


def manifest_mismatches(
    batch_dir: Path,
    manifest: dict[str, Any],
    declared: dict[str, Any],
    files_by_stem: dict[str, list[Path]],
) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    for table, meta in declared.items():
        path = meta.get("path")
        if path:
            actual = batch_dir / str(path)
            if not actual.exists():
                actual = batch_dir / Path(str(path)).name
            if not actual.exists():
                mismatches.append({"table": table, "issue": "declared_path_missing", "path": str(path)})
            elif actual.suffix != ".parquet" and manifest.get("data_backend") == "parquet":
                mismatches.append(
                    {"table": table, "issue": "parquet_backend_declares_non_parquet", "path": str(path)}
                )
    for table in FORMAL_TABLES:
        if table in declared and not files_by_stem.get(table):
            mismatches.append({"table": table, "issue": "declared_table_file_missing"})
    return mismatches


def registry_summary() -> dict[str, Any]:
    summary: dict[str, Any] = {"files": [], "machine_fact_source": None}
    paths = list(sorted(BATCH_ROOT.glob("*registry*"))) + list(sorted(BATCH_ROOT.glob("available_observation_contexts.*")))
    seen: set[Path] = set()
    for path in paths:
        if not path.is_file() or path in seen:
            continue
        seen.add(path)
        item = table_summary(path)
        item["date_ranges"] = registry_date_ranges(path, item["columns"])
        summary["files"].append(item)
    parquet = BATCH_ROOT / "available_observation_contexts.parquet"
    csv_path = BATCH_ROOT / "available_observation_contexts.csv"
    if parquet.exists():
        summary["machine_fact_source"] = rel(parquet)
    elif csv_path.exists():
        summary["machine_fact_source"] = rel(csv_path)
    return summary


def registry_date_ranges(path: Path, columns: list[str]) -> dict[str, Any]:
    date_cols = [column for column in columns if "date" in column.lower()]
    if not date_cols:
        return {}
    frame = read_table_sample(path, date_cols)
    ranges: dict[str, Any] = {}
    for column in date_cols:
        values = sorted(frame[column].astype("string").dropna().unique().tolist())
        ranges[column] = {
            "count": len(values),
            "min": values[0] if values else None,
            "max": values[-1] if values else None,
            "sample": values[:5] + values[-5:] if len(values) > 10 else values,
        }
    return ranges


def summarize_api(obj: Any) -> dict[str, Any]:
    if not isinstance(obj, dict):
        return {"type": type(obj).__name__, "preview": str(obj)[:500]}
    summary = {
        key: obj.get(key)
        for key in [
            "ready",
            "status",
            "context_status",
            "count",
            "total",
            "total_count",
            "empty_reason",
            "error_code",
        ]
        if key in obj
    }
    for key in ["items", "rows", "data", "manufacturers"]:
        if isinstance(obj.get(key), list):
            summary[f"{key}_len"] = len(obj[key])
    for key in [
        "query",
        "scope",
        "lookup_status",
        "detector_run_available",
        "probability_batch_available",
        "probability_report_month",
        "detector_run_date",
        "observation_date",
        "batch_root",
        "batch_dir",
    ]:
        if key in obj:
            summary[key] = obj.get(key)
    return summary


def http_get(path: str, params: dict[str, Any] | None = None, include_body: bool = False) -> dict[str, Any]:
    url = API_BASE_URL + path
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    try:
        with urllib.request.urlopen(url, timeout=8) as response:
            parsed = json.loads(response.read().decode("utf-8"))
            result: dict[str, Any] = {
                "url": url,
                "status": response.status,
                "ok": True,
                "body_summary": summarize_api(parsed),
            }
            if include_body:
                result["body"] = parsed
            return result
    except Exception as exc:
        return {"url": url, "ok": False, "error": f"{type(exc).__name__}: {exc}"}


def select_observation_dates(registry: dict[str, Any]) -> list[str]:
    dates: set[str] = set()
    for file_summary in registry.get("files", []):
        for column, info in file_summary.get("date_ranges", {}).items():
            if column in {"observation_date", "detector_run_date", "run_date"}:
                dates.update(info.get("sample") or [])
    preferred = ["2025-12-01", "2025-12-05"]
    ordered: list[str] = []
    for date in preferred + sorted(dates):
        if date and date not in ordered:
            ordered.append(date)
    return ordered[:4]


def api_runtime(registry: dict[str, Any]) -> dict[str, Any]:
    observation_dates = select_observation_dates(registry)
    runtime: dict[str, Any] = {
        "base_url": API_BASE_URL,
        "observation_dates_checked": observation_dates,
        "calls": {},
    }
    runtime["calls"]["my_manufacturers"] = http_get("/api/v1/my/manufacturers", include_body=True)
    runtime["calls"]["display_lookup_status"] = http_get("/api/v1/display-lookup/status")
    manufacturer = first_manufacturer_code(runtime["calls"]["my_manufacturers"].get("body"))
    runtime["selected_manufacturer_for_checks"] = manufacturer
    runtime["calls"]["my_manufacturers"].pop("body", None)
    for date in observation_dates[:2]:
        params: dict[str, Any] = {"observation_date": date}
        if manufacturer:
            params["manufacturer_code"] = manufacturer
        runtime["calls"][f"daily_detector_status_{date}"] = http_get("/api/v1/daily-detector/status", params)
        runtime["calls"][f"daily_detector_clues_{date}"] = http_get(
            "/api/v1/daily-detector/clues", {**params, "top_n": 5}
        )
        runtime["calls"][f"workbench_{date}"] = http_get(
            "/api/v1/workbench",
            {**params, "horizon": "H3", "top_n": 5, "sort_by": "risk_probability"},
        )
        runtime["calls"][f"oneshot_{date}"] = http_get("/api/v1/oneshot-terminals", {**params, "top_n": 5})
        runtime["calls"][f"report_context_{date}"] = http_get(
            "/api/v1/report-context", {"observation_date": date}
        )
    return runtime


def first_manufacturer_code(body: Any) -> str | None:
    if not isinstance(body, dict):
        return None
    candidates = body.get("manufacturers") or body.get("items") or body.get("data") or []
    if candidates and isinstance(candidates[0], dict):
        return candidates[0].get("manufacturer_code") or candidates[0].get("code")
    return None


def storage_formats() -> dict[str, list[str]]:
    return {
        "root_csv_files": [rel(path) for path in sorted(BATCH_ROOT.glob("*.csv"))],
        "batch_csv_files": [rel(path) for path in sorted(BATCH_ROOT.glob("report_month=*/batch_id=*/*.csv"))],
        "batch_parquet_files": [rel(path) for path in sorted(BATCH_ROOT.glob("report_month=*/batch_id=*/*.parquet"))],
    }


def checksums() -> dict[str, str]:
    output: dict[str, str] = {}
    for pattern in CHECKSUM_PATTERNS:
        matches = list(sorted(BATCH_ROOT.glob(f"report_month=*/batch_id=*/{pattern}"))) + list(
            sorted(BATCH_ROOT.glob(pattern))
        )
        for path in matches:
            if path.is_file():
                output[rel(path)] = sha256(path)
    return output


def main() -> None:
    batches = [collect_batch(path.parent) for path in sorted(BATCH_ROOT.glob("report_month=*/batch_id=*/manifest.json"))]
    registry = registry_summary()
    api = api_runtime(registry)
    formats = storage_formats()
    baseline = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_head": os.popen("git rev-parse HEAD").read().strip(),
        "batch_root": rel(BATCH_ROOT),
        "batches": batches,
        "observation_registry": registry,
        "api_runtime": api,
        "storage_formats": formats,
        "lookup_readiness": api["calls"].get("display_lookup_status", {}),
        "detector_run_coverage": {
            "from_batch_tables": [batch["table_files"].get("daily_detector_runs", []) for batch in batches]
        },
        "checksums": checksums(),
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(REPORT_PATH)
    print(
        json.dumps(
            {
                "batches": len(batches),
                "root_csv": len(formats["root_csv_files"]),
                "batch_csv": len(formats["batch_csv_files"]),
                "batch_parquet": len(formats["batch_parquet_files"]),
                "api_selected_manufacturer": api.get("selected_manufacturer_for_checks"),
                "observation_dates_checked": api.get("observation_dates_checked", [])[:2],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
