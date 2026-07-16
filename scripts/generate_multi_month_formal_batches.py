from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from risk_algorithm_core.artifact_loader import load_current_model_artifact
from risk_algorithm_core.candidate_selector import BoundedCandidateSelector
from risk_algorithm_core.config import MonthlyRiskRunConfig, load_run_config
from risk_algorithm_core.detector_quality_gate import DetectorQualityGate
from risk_algorithm_core.detectors import DisabledDetectorNoteBuilder
from risk_algorithm_core.entity_builder import build_monthly_entities
from risk_algorithm_core.entity_display_lookup import build_entity_display_lookup
from risk_algorithm_core.evidence_builder import build_risk_card_evidence, build_risk_cards
from risk_algorithm_core.feature_engineering import engineer_features, engineer_features_from_facts
from risk_algorithm_core.monthly_runner import MonthlyRiskRunner, _empty_detector_outputs
from risk_algorithm_core.normalization import normalize_raw_tables
from risk_algorithm_core.production_feature_builder import build_model_feature_frame
from risk_algorithm_core.raw_input import read_raw_input_batch
from risk_algorithm_core.result_assembler import assemble_result_batch
from risk_algorithm_core.scorer import ArtifactRiskScorer
from risk_algorithm_core.status_decider import StatusDecider
from risk_model_core.validation import validate_batch as validate_model_core_batch
from risk_result_contracts import validate_result_batch, write_production_parquet


TARGET_COMPLETE_MONTHS = ["2025-09", "2025-10", "2025-11", "2025-12"]
OUTPUT_ROOT = Path("data/project_result_batches")
REPORT_ROOT = Path("reports/full_recurring_formal_batches")
DEFAULT_CONFIG = Path("configs/risk_algorithm_core/monthly_run.formal.example.yaml")
DEFAULT_RUN_ID = "full-recurring-v3"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--output-root", default=str(OUTPUT_ROOT))
    parser.add_argument("--report-root", default=str(REPORT_ROOT))
    parser.add_argument("--months", nargs="*", default=TARGET_COMPLETE_MONTHS)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--without-detector-evidence", action="store_true")
    parser.add_argument("--clean-output", action="store_true")
    args = parser.parse_args(argv)

    output_root = Path(args.output_root)
    report_root = Path(args.report_root)
    if args.clean_output and output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)

    base_cfg = load_run_config(args.config)
    monthly_profiles: list[dict[str, Any]] = []
    detector_profiles: list[dict[str, Any]] = []
    end_to_end_profiles: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []

    for month in args.months:
        cfg = config_for_month(base_cfg, month, output_root, args.run_id)
        result = run_profiled_month(
            cfg,
            default_observation_date(month),
            include_detector_evidence=not args.without_detector_evidence,
        )
        monthly_profiles.append(result["monthly_profile"])
        detector_profiles.append(result["detector_profile"])
        end_to_end_profiles.append(result["end_to_end_profile"])
        contexts.append(result["observation_context"])
        summaries.append(result["summary"])

    contexts.extend(extra_validation_contexts(contexts))
    write_registry(output_root, contexts)
    write_profiles(output_root, monthly_profiles, detector_profiles, end_to_end_profiles)
    scaling = build_runtime_scaling_estimate(monthly_profiles, detector_profiles, end_to_end_profiles)
    write_production_parquet(pd.DataFrame(scaling), output_root / "runtime_scaling_estimate.parquet")
    write_reports(report_root, output_root, summaries, contexts, monthly_profiles, detector_profiles, end_to_end_profiles, scaling)
    print(json.dumps({"output_root": str(output_root), "months": args.months, "summaries": summaries}, ensure_ascii=False, indent=2))
    return 0


def config_for_month(base_cfg: MonthlyRiskRunConfig, month: str, output_root: Path, run_id: str) -> MonthlyRiskRunConfig:
    export = dict(base_cfg.export)
    export["write_parquet"] = True
    return replace(
        base_cfg,
        report_month=month,
        run_date=default_observation_date(month),
        output_root=str(output_root),
        run_id=run_id,
        export=export,
    )


def run_profiled_month(
    cfg: MonthlyRiskRunConfig,
    observation_date: str,
    *,
    include_detector_evidence: bool = True,
) -> dict[str, Any]:
    e2e_start = time.perf_counter()
    report_month = cfg.resolved_report_month
    cutoff_date = cfg.resolved_cutoff_date
    runner = MonthlyRiskRunner(cfg)

    raw_start = time.perf_counter()
    raw_batch = read_raw_input_batch(cfg.raw_batch_dir, cfg.schema_mapping_path)
    raw_seconds = elapsed(raw_start)

    norm_start = time.perf_counter()
    normalized, normalize_report = normalize_raw_tables(raw_batch.tables, cutoff_date)
    normalization_seconds = elapsed(norm_start)

    feature_start = time.perf_counter()
    entity_base = build_monthly_entities(
        normalized["orders"],
        normalized["drug_master"],
        normalized["hospital_master"],
        normalized["product_line_mapping"],
        report_month,
        cutoff_date,
        cfg.available_horizons,
    )
    if not normalized.get("fact_entity_month", pd.DataFrame()).empty:
        features, feature_report = engineer_features_from_facts(entity_base, normalized["fact_entity_month"], cutoff_date)
    else:
        features, feature_report = engineer_features(entity_base, normalized["orders"], cutoff_date)
    feature_seconds = elapsed(feature_start)

    scoring_start = time.perf_counter()
    artifact = load_current_model_artifact(cfg.artifact_dir, cfg.require_artifact)
    aligned = build_model_feature_frame(features, artifact)
    model_features = aligned.model_feature_frame
    feature_parity_report = aligned.parity_report
    scorer = ArtifactRiskScorer(artifact)
    score_frame = scorer.score(model_features)
    scoring_seconds = elapsed(scoring_start)

    candidate_start = time.perf_counter()
    selected, selection_report = BoundedCandidateSelector(cfg.worklist).select(score_frame, features)
    candidate_seconds = elapsed(candidate_start)

    ranking_start = time.perf_counter()
    gate = DetectorQualityGate(cfg.detectors)
    gate_decisions = gate.evaluate(features, normalized)
    detector_outputs = runner._run_detectors(selected, features, gate_decisions) if include_detector_evidence else _empty_detector_outputs()
    disabled_notes = DisabledDetectorNoteBuilder().build(gate_decisions)
    status = StatusDecider().decide(selected, features, detector_outputs)
    risk_cards = build_risk_cards(status, detector_outputs)
    risk_evidence = build_risk_card_evidence(risk_cards, detector_outputs)
    ranking_seconds = elapsed(ranking_start)

    write_start = time.perf_counter()
    batch_dir = assemble_result_batch(
        cfg.output_root,
        cfg.run_id,
        report_month,
        cutoff_date,
        raw_batch.manifest.raw_batch_id,
        artifact.manifest.artifact_id,
        cfg.primary_horizon,
        cfg.available_horizons,
        status,
        risk_cards,
        risk_evidence,
        features,
        cfg.worklist,
        score_frame=score_frame,
        normalized_tables=normalized,
        artifact_metadata=artifact.manifest.raw,
        include_detector_evidence=include_detector_evidence,
        write_parquet=True,
    )
    result_write_seconds = elapsed(write_start)

    risk_entities = read_table(batch_dir, "risk_entities")
    display_start = time.perf_counter()
    _ = build_entity_display_lookup(risk_entities, normalized, report_month, raw_batch.manifest.raw_batch_id)
    display_seconds = elapsed(display_start)

    # Daily Detector output is independently materialized from raw purchase
    # facts. The monthly generator never invokes or writes it.
    detector_tables: dict[str, pd.DataFrame] = {}
    detector_compute_seconds = 0.0
    detector_write_seconds = 0.0
    detector_total_seconds = 0.0

    validation_start = time.perf_counter()
    update_manifest_and_context(
        batch_dir=batch_dir,
        observation_date=observation_date,
        runtime_profile_summary={
            "monthly_probability_total_seconds": scoring_seconds + candidate_seconds + ranking_seconds + result_write_seconds,
            "detector_total_seconds": detector_total_seconds,
            "end_to_end_seconds": elapsed(e2e_start),
        },
    )
    validate_result_batch(batch_dir)
    validate_model_core_batch(batch_dir)
    validation_seconds = elapsed(validation_start)
    end_to_end_seconds = elapsed(e2e_start)

    write_run_reports(
        batch_dir,
        {
            "report_month": report_month,
            "cutoff_date": cutoff_date,
            "raw_batch_id": raw_batch.manifest.raw_batch_id,
            "entity_rows": int(len(entity_base)),
            "feature_rows": int(len(features)),
            "score_rows": int(len(score_frame)),
            "selected_candidate_rows": int(len(selected)),
            "detector_output_rows": int(len(detector_outputs)),
            "risk_card_rows": int(len(risk_cards)),
            "evidence_rows": int(len(risk_evidence)),
            "batch_dir": str(batch_dir),
            "model_artifact_id": artifact.manifest.artifact_id,
            "dry_run_rule_baseline": False,
        },
        normalize_report,
        feature_report,
        feature_parity_report,
        selection_report,
        gate_decisions,
        disabled_notes,
    )

    monthly_profile = {
        "report_month": report_month,
        "feature_row_count": int(len(features)),
        "risk_entity_count": int(len(risk_entities)),
        "scoring_seconds": round(scoring_seconds, 6),
        "candidate_selection_seconds": round(candidate_seconds, 6),
        "ranking_seconds": round(ranking_seconds, 6),
        "result_table_write_seconds": round(result_write_seconds, 6),
        "monthly_probability_total_seconds": round(scoring_seconds + candidate_seconds + ranking_seconds + result_write_seconds, 6),
    }
    detector_profile = {
        "observation_date": observation_date,
        "probability_report_month": report_month,
        "scanned_entity_count": int(detector_tables["daily_detector_runs"].iloc[0]["scanned_entity_count"]) if detector_tables else 0,
        "enabled_detector_count": len(str(detector_tables["daily_detector_runs"].iloc[0]["enabled_detectors"]).split(",")) if detector_tables else 0,
        "detector_clue_count": int(len(detector_tables["daily_detector_clues"])) if detector_tables else 0,
        "detector_compute_seconds": round(detector_compute_seconds, 6),
        "detector_table_write_seconds": round(detector_write_seconds, 6),
        "detector_total_seconds": round(detector_total_seconds, 6),
    }
    end_to_end_profile = {
        "report_month": report_month,
        "observation_date": observation_date,
        "raw_row_count": int(len(normalized["orders"])),
        "entity_count": int(len(entity_base)),
        "feature_row_count": int(len(features)),
        "clickhouse_read_seconds": round(raw_seconds, 6),
        "raw_normalization_seconds": round(normalization_seconds, 6),
        "feature_build_seconds": round(feature_seconds, 6),
        "monthly_probability_total_seconds": monthly_profile["monthly_probability_total_seconds"],
        "display_lookup_seconds": round(display_seconds, 6),
        "detector_total_seconds": detector_profile["detector_total_seconds"],
        "validation_seconds": round(validation_seconds, 6),
        "end_to_end_seconds": round(end_to_end_seconds, 6),
        "peak_memory_mb": "",
        "cpu_count": os.cpu_count() or "",
        "machine_note": "Windows local development machine; source_type=parquet_raw_input_batch",
    }
    context = observation_context_for_batch(batch_dir, observation_date)
    summary = {
        "report_month": report_month,
        "batch_dir": str(batch_dir),
        "risk_entities": int(len(risk_entities)),
        "detector_runs": int(len(detector_tables["daily_detector_runs"])) if detector_tables else 0,
        "detector_clues": int(len(detector_tables["daily_detector_clues"])) if detector_tables else 0,
        "high_risk_detector_evidence": int(len(detector_tables["high_risk_detector_evidence"])) if detector_tables else 0,
        "end_to_end_seconds": end_to_end_profile["end_to_end_seconds"],
    }
    return {
        "monthly_profile": monthly_profile,
        "detector_profile": detector_profile,
        "end_to_end_profile": end_to_end_profile,
        "observation_context": context,
        "summary": summary,
    }


def default_observation_date(report_month: str) -> str:
    year, month = [int(part) for part in report_month.split("-")]
    if month == 12:
        return f"{year + 1}-01-01"
    return f"{year}-{month + 1:02d}-01"


def previous_complete_month(observation_date: str) -> str:
    current = dt.date.fromisoformat(observation_date).replace(day=1)
    previous = current - dt.timedelta(days=1)
    return previous.strftime("%Y-%m")


def read_table(batch_dir: Path, name: str) -> pd.DataFrame:
    parquet = batch_dir / f"{name}.parquet"
    if parquet.exists():
        return pd.read_parquet(parquet)
    raise FileNotFoundError(f"Missing production Parquet table: {parquet}")


def update_manifest_and_context(batch_dir: Path, observation_date: str, runtime_profile_summary: dict[str, Any]) -> None:
    manifest_path = batch_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    risk_entities = read_table(batch_dir, "risk_entities")
    detector_tables_available = bool(manifest.get("detector_tables"))
    manifest["result_batch_id"] = manifest.get("result_batch_id") or manifest.get("batch_id")
    manifest["run_date"] = observation_date
    manifest["report_date"] = observation_date
    manifest["score_as_of_date"] = manifest.get("score_as_of_date") or manifest.get("cutoff_date")
    manifest["raw_orders_mode_ready"] = False
    manifest["fact_mode_ready"] = True
    manifest["conditional_fact_mode_ready"] = True
    manifest["readiness_level"] = "conditional_fact_mode_ready"
    manifest["runtime_profile_summary"] = runtime_profile_summary
    manifest["deprecated_frontend_fields"] = {
        "business_score": "not emitted by model-core customer payloads; downstream display must use horizon profile involved_amount and probability fields",
        "fill_policy": "removed from model-core payloads; user-scope selection is a backend responsibility",
    }
    manifest["detector_tables"] = (
        {
            "detector_catalog": "detector_catalog.parquet",
            "daily_detector_runs": "daily_detector_runs.parquet",
            "daily_detector_clues": "daily_detector_clues.parquet",
            "high_risk_detector_evidence": "high_risk_detector_evidence.parquet",
        }
        if detector_tables_available
        else {}
    )
    manifest["detector_score_probability_interpretation"] = "detector_score_is_not_probability"
    recurring = risk_entities.get("candidate_type", pd.Series("recurring", index=risk_entities.index)).astype(str).eq("recurring")
    manifest["candidate_pool_policy"] = "full_recurring_universe"
    manifest["full_recurring_count"] = int(recurring.sum())
    manifest["persisted_recurring_count"] = int(recurring.sum())
    manifest["detector_default_scope"] = "recurring_candidates" if detector_tables_available else "independent_detector_batch"
    manifest["result_table_row_counts"] = table_counts(batch_dir)
    caveats = list(manifest.get("caveats") or [])
    caveat = "multi_month_context_ready; default_observation_date is not a fabricated detector clue"
    if caveat not in caveats:
        caveats.append(caveat)
    manifest["caveats"] = caveats
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    context = report_context_for_manifest(batch_dir, manifest)
    (batch_dir / "report_context.json").write_text(json.dumps(context, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def table_counts(batch_dir: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in batch_dir.glob("*.parquet"):
        name = path.stem
        try:
            counts[name] = int(pq.ParquetFile(path).metadata.num_rows)
        except Exception:
            continue
    return counts


def report_context_for_manifest(batch_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    detector_tables_available = bool(manifest.get("detector_tables"))
    daily_runs = read_table(batch_dir, "daily_detector_runs") if detector_tables_available else pd.DataFrame()
    detector_run_dates = sorted({str(value) for value in daily_runs.get("run_date", pd.Series(dtype=str)).dropna()})
    return {
        "batch_id": manifest.get("batch_id"),
        "batch_dir": str(batch_dir).replace("\\", "/"),
        "report_month": manifest.get("report_month"),
        "report_date": manifest.get("report_date"),
        "run_date": manifest.get("run_date"),
        "score_as_of_date": manifest.get("score_as_of_date") or manifest.get("cutoff_date"),
        "cutoff_date": manifest.get("cutoff_date"),
        "default_observation_date": manifest.get("run_date"),
        "detector_run_dates": detector_run_dates,
        "available_horizons": manifest.get("available_horizons", []),
        "primary_horizon": manifest.get("primary_horizon"),
        "detector_config_version": manifest.get("detector_config_version"),
        "risk_entity_count": table_counts(batch_dir).get("risk_entities", 0),
        "daily_detector_clue_count": table_counts(batch_dir).get("daily_detector_clues", 0),
        "high_risk_detector_evidence_count": table_counts(batch_dir).get("high_risk_detector_evidence", 0),
        "monthly_candidate_batch_available": True,
        "detector_tables_available": detector_tables_available,
        "fact_mode_ready": manifest.get("fact_mode_ready", False),
        "raw_orders_mode_ready": manifest.get("raw_orders_mode_ready", False),
        "conditional_fact_mode_ready": manifest.get("conditional_fact_mode_ready", False),
        "ready_for_frontend_date_resolution": True,
        "caveats": manifest.get("caveats", []),
    }


def observation_context_for_batch(batch_dir: Path, observation_date: str) -> dict[str, Any]:
    context = json.loads((batch_dir / "report_context.json").read_text(encoding="utf-8"))
    daily_runs = read_table(batch_dir, "daily_detector_runs") if context.get("detector_tables_available") else pd.DataFrame()
    detector_run_id = ""
    detector_available = False
    if not daily_runs.empty and "run_date" in daily_runs:
        matched = daily_runs[daily_runs["run_date"].astype(str).eq(observation_date)]
        if not matched.empty:
            detector_available = True
            detector_run_id = str(matched.iloc[0].get("detector_run_id", ""))
    return {
        "observation_date": observation_date,
        "probability_report_month": context["report_month"],
        "probability_batch_id": context["batch_id"],
        "probability_batch_dir": str(batch_dir).replace("\\", "/"),
        "probability_batch_available": True,
        "detector_run_date": observation_date,
        "detector_run_id": detector_run_id,
        "detector_run_available": detector_available,
        "context_status": "ready" if detector_available else "detector_run_unavailable",
        "manual_selection_required": not detector_available,
        "available_report_months": "",
        "available_detector_run_dates": "",
        "primary_horizon": context["primary_horizon"],
        "available_horizons": ";".join(context["available_horizons"]),
        "caveat": "; ".join(context["caveats"]),
    }


def extra_validation_contexts(contexts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_month = {row["probability_report_month"]: row for row in contexts}
    available_months = sorted(by_month)
    available_detector_dates = sorted(row["detector_run_date"] for row in contexts if row["detector_run_available"])
    rows: list[dict[str, Any]] = []
    for observation_date in ["2025-12-05"]:
        probability_month = previous_complete_month(observation_date)
        source = by_month.get(probability_month)
        if source:
            row = dict(source)
            row.update(
                {
                    "observation_date": observation_date,
                    "detector_run_date": observation_date,
                    "detector_run_id": "",
                    "detector_run_available": False,
                    "context_status": "detector_run_unavailable",
                    "manual_selection_required": True,
                }
            )
        else:
            row = unavailable_context(observation_date, probability_month)
        rows.append(row)
    for row in contexts + rows:
        row["available_report_months"] = ";".join(available_months)
        row["available_detector_run_dates"] = ";".join(available_detector_dates)
    return rows


def unavailable_context(observation_date: str, probability_month: str) -> dict[str, Any]:
    return {
        "observation_date": observation_date,
        "probability_report_month": probability_month,
        "probability_batch_id": "",
        "probability_batch_dir": "",
        "probability_batch_available": False,
        "detector_run_date": observation_date,
        "detector_run_id": "",
        "detector_run_available": False,
        "context_status": "probability_month_unavailable",
        "manual_selection_required": True,
        "available_report_months": "",
        "available_detector_run_dates": "",
        "primary_horizon": "H6",
        "available_horizons": "H3;H6;H12",
        "caveat": "probability month unavailable",
    }


def write_registry(output_root: Path, contexts: list[dict[str, Any]]) -> None:
    ordered = sorted(contexts, key=lambda row: row["observation_date"])
    frame = pd.DataFrame(ordered)
    write_production_parquet(frame, output_root / "available_observation_contexts.parquet")
    (output_root / "available_observation_contexts.json").write_text(
        json.dumps({"contexts": ordered}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_profiles(
    output_root: Path,
    monthly_profiles: list[dict[str, Any]],
    detector_profiles: list[dict[str, Any]],
    end_to_end_profiles: list[dict[str, Any]],
) -> None:
    write_production_parquet(pd.DataFrame(monthly_profiles), output_root / "monthly_probability_runtime_profile.parquet")
    write_production_parquet(pd.DataFrame(detector_profiles), output_root / "daily_detector_runtime_profile.parquet")
    write_production_parquet(pd.DataFrame(end_to_end_profiles), output_root / "end_to_end_runtime_profile.parquet")


def build_runtime_scaling_estimate(
    monthly_profiles: list[dict[str, Any]],
    detector_profiles: list[dict[str, Any]],
    end_to_end_profiles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    e2e = pd.DataFrame(end_to_end_profiles)
    monthly = pd.DataFrame(monthly_profiles)
    detector = pd.DataFrame(detector_profiles)
    current_raw = max(float(e2e["raw_row_count"].max()), 1.0)
    current_entities = max(float(e2e["entity_count"].max()), 1.0)
    current_features = max(float(e2e["feature_row_count"].max()), 1.0)
    full_rows = float(os.environ.get("RISK_FULL_DATASET_ROW_COUNT") or current_raw)
    row_multiplier = max(full_rows / current_raw, 1.0)
    entity_multiplier = 1.0
    feature_multiplier = 1.0
    scaling_caveat = (
        "Full dataset row count came from RISK_FULL_DATASET_ROW_COUNT; detector estimate applies selected monthly scope only."
        if full_rows > current_raw
        else "Set RISK_FULL_DATASET_ROW_COUNT for full ClickHouse-count scaling; detector estimate applies selected monthly scope only."
    )
    rows = []
    stage_specs = [
        ("clickhouse_read", float(e2e["clickhouse_read_seconds"].mean()), row_multiplier, "linear_raw_rows"),
        ("feature_build", float(e2e["feature_build_seconds"].mean()), row_multiplier, "roughly_linear_raw_rows_with_groupby_caveat"),
        ("monthly_probability", float(monthly["monthly_probability_total_seconds"].mean()), feature_multiplier, "linear_feature_rows"),
        ("detector", float(detector["detector_total_seconds"].mean()), entity_multiplier, "selected_scope_not_raw_rows"),
        ("validation", float(e2e["validation_seconds"].mean()), entity_multiplier, "result_table_size"),
        ("end_to_end", float(e2e["end_to_end_seconds"].mean()), row_multiplier, "dominant_raw_and_feature_stages"),
    ]
    for stage, observed, multiplier, assumption in stage_specs:
        mid = observed * multiplier
        rows.append(
            {
                "stage": stage,
                "current_run_seconds": round(observed, 6),
                "current_run_raw_rows": int(current_raw),
                "current_run_entity_count": int(current_entities),
                "current_run_feature_rows": int(current_features),
                "sql_clickhouse_full_row_count": int(full_rows),
                "full_dataset_row_multiplier": round(row_multiplier, 6),
                "full_dataset_entity_multiplier": round(entity_multiplier, 6),
                "stage_specific_scaling_assumption": assumption,
                "estimated_full_dataset_seconds_low": round(mid * 0.75, 6),
                "estimated_full_dataset_seconds_mid": round(mid, 6),
                "estimated_full_dataset_seconds_high": round(mid * 1.5, 6),
                "confidence_level": "medium" if full_rows > current_raw else "low",
                "caveat": scaling_caveat,
            }
        )
    return rows


def write_reports(
    report_root: Path,
    output_root: Path,
    summaries: list[dict[str, Any]],
    contexts: list[dict[str, Any]],
    monthly_profiles: list[dict[str, Any]],
    detector_profiles: list[dict[str, Any]],
    end_to_end_profiles: list[dict[str, Any]],
    scaling: list[dict[str, Any]],
) -> None:
    report_root.mkdir(parents=True, exist_ok=True)
    write_markdown_table(report_root / "multi_month_formal_batch_summary.md", "Multi Month Formal Batch Summary", summaries)
    write_markdown_table(report_root / "observation_context_resolution_summary.md", "Observation Context Resolution Summary", contexts)
    write_markdown_table(report_root / "runtime_profile_summary.md", "Runtime Profile Summary", end_to_end_profiles)
    write_markdown_table(report_root / "runtime_scaling_estimate.md", "Runtime Scaling Estimate", scaling)
    (report_root / "remaining_limitations.md").write_text(
        "\n".join(
            [
                "# Remaining Limitations",
                "",
                "- Generated observation contexts cover four default dates plus the 2025-12-05 validation sample, not a full 90-day detector history.",
                "- Full dataset scaling uses observed local batch timing. Set RISK_FULL_DATASET_ROW_COUNT to refine full ClickHouse row-count scaling.",
                "- raw_orders_mode_ready remains false; current readiness remains conditional fact mode.",
                "- No detector clues were fabricated for unavailable observation dates.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (report_root / "generation_manifest.json").write_text(
        json.dumps({"output_root": str(output_root), "summaries": summaries}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_markdown_table(path: Path, title: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text(f"# {title}\n\nNo rows.\n", encoding="utf-8")
        return
    columns = list(rows[0].keys())
    lines = [f"# {title}", "", "| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(column, "")) for column in columns) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_run_reports(
    batch_dir: Path,
    summary: dict[str, Any],
    normalize_report: pd.DataFrame,
    feature_report: pd.DataFrame,
    feature_parity_report: pd.DataFrame,
    selection_report: pd.DataFrame,
    gate_decisions: pd.DataFrame,
    disabled_notes: pd.DataFrame,
) -> None:
    (batch_dir / "run_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")
    write_production_parquet(normalize_report, batch_dir / "normalization_report.parquet")
    write_production_parquet(feature_report, batch_dir / "feature_quality_report.parquet")
    write_production_parquet(feature_parity_report, batch_dir / "feature_parity_runtime_report.parquet")
    write_production_parquet(selection_report, batch_dir / "selection_report.parquet")
    write_production_parquet(gate_decisions, batch_dir / "detector_quality_gate.parquet")
    write_production_parquet(disabled_notes, batch_dir / "disabled_detector_notes.parquet")


def elapsed(start: float) -> float:
    return time.perf_counter() - start


if __name__ == "__main__":
    raise SystemExit(main())
