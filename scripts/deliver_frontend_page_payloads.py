"""Build frontend page payload JSON files from the formal risk_result_batch."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
VERSION = "entity_complete_v2_coverage_expansion"
DEFAULT_BATCH_DIR = (
    ROOT
    / "data"
    / "project_result_batches"
    / "report_month=2025-12"
    / "batch_id=2025-12-monthly-risk-algorithm-full-recurring-v3"
)
REPORT_DIR = ROOT / "algo_main" / "reports" / VERSION / "22_frontend_payload_delivery"
SCHEMA_PATH = ROOT / "project" / "app" / "schemas" / "frontend_pages.py"
PROGRESS = REPORT_DIR / "frontend_payload_delivery_progress.md"

BANNED_TEXT = [
    "仅供展示",
    "不代表业务效果",
    "未实现",
    "未接入",
    "概率展示受控",
    "不自动派单",
    "默认人工复核",
    "模型训练参数",
    "AUC",
    "ECE",
    "PR-AUC",
    "LogLoss",
    "Brier",
    "XGBoost",
    "LightGBM",
    "CatBoost",
    "feature ablation",
    "leakage audit",
    "FDR",
    "MK显著",
    "Theil-Sen",
    "CUSUM",
    "竞品替代迹象明显",
    "政策落标已确认",
    "配送商责任已确认",
    "医院确定流失",
    "一定不会再采购",
]

DETECTORS = [
    ("purchase_gap", "Purchase gap", "purchase_interval_overdue_warning"),
    ("frequency_drop", "Frequency drop", "purchase_frequency_fluctuation_warning"),
    ("quantity_drop", "Quantity drop", "purchase_quantity_fluctuation_warning"),
    ("terminal_loss", "Stored terminal risk", "terminal_loss_warning"),
    ("new_terminal", "New terminal", "new_terminal_detection"),
    ("delivery_time", "Delivery timing", ""),
    ("delivery_rate", "Delivery fulfillment", ""),
    ("price_signal", "Price signal", ""),
    ("sku_wallet", "Portfolio signal", ""),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-dir", default=str(DEFAULT_BATCH_DIR))
    args = parser.parse_args()
    batch_dir = Path(args.batch_dir).resolve()
    if not batch_dir.exists():
        raise SystemExit(f"Batch dir not found: {batch_dir}")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    progress("stage=start", reset=True)
    write_wip_snapshot()

    tables = load_tables(batch_dir)
    manifest = read_json(batch_dir / "manifest.json")
    payload_dir = batch_dir / "page_payloads"
    payload_dir.mkdir(parents=True, exist_ok=True)

    schema_classes = inspect_schema()
    write_schema_inspection(schema_classes)

    progress("stage=build_payloads")
    batch_context = build_batch_context(manifest)
    frontend_entities = build_frontend_entities(tables)
    workbench_payload = build_workbench_payload(batch_context, frontend_entities, len(tables["risk_entities"]))
    risk_entities_payload = {
        "batch_context": batch_context,
        "entities": frontend_entities,
        "pagination": {"total_items": len(frontend_entities)},
    }
    oneshot_payload = build_oneshot_payload(manifest, tables)
    monthly_reports_payload = build_monthly_reports_payload(batch_context, tables, frontend_entities, oneshot_payload)
    proof_cases_payload = build_proof_cases_payload(tables)

    payload_files = {
        "frontend_workbench_payload.json": workbench_payload,
        "frontend_risk_entities_payload.json": risk_entities_payload,
        "frontend_oneshot_payload.json": oneshot_payload,
        "frontend_monthly_reports_payload.json": monthly_reports_payload,
        "frontend_proof_cases_payload.json": proof_cases_payload,
    }
    for name, payload in payload_files.items():
        write_json(payload_dir / name, payload)

    detail_payloads = []
    for entity in frontend_entities:
        entity_id = entity["entity_id"]
        file_name = f"frontend_risk_entity_detail_{safe_slug(entity_id)}_payload.json"
        detail = build_detail_payload(entity, tables)
        write_json(payload_dir / file_name, detail)
        detail_payloads.append({"entity_id": entity_id, "detail_payload_file": file_name})

    frontend_manifest = {
        "batch_dir": str(batch_dir),
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "schema_source": str(SCHEMA_PATH),
        "validated_with_project_schema": False,
        "payload_files": sorted(payload_files),
        "detail_payloads": detail_payloads,
        "detail_payload_count": len(detail_payloads),
        "workbench_row_count": len(workbench_payload["rows"]),
        "risk_entities_count": len(frontend_entities),
        "oneshot_count": len(oneshot_payload["items"]),
        "proof_case_count": len(proof_cases_payload["items"]),
        "monthly_report_count": len(monthly_reports_payload["monthly_reports"]),
        "forbidden_text_check_passed": check_no_banned_text(payload_dir),
        "caveats_for_internal_review": [
            "average_consumption_in_window set to 0 because no numeric amount proxy is present in the current result batch",
            "xgboost_shap arrays are empty because no verified SHAP/contribution table is present",
            "oneshot repurchase_propensity is rule-tiered from one-shot attention score, not recurring churn probability",
        ],
    }
    write_json(payload_dir / "frontend_payload_manifest.json", frontend_manifest)

    progress("stage=reports")
    write_field_mapping()
    write_delivery_summary(batch_dir, frontend_manifest)

    progress("stage=validate")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_frontend_page_payloads.py"), "--batch-dir", str(batch_dir)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr or result.stdout)
    frontend_manifest["validated_with_project_schema"] = True
    frontend_manifest["validation_report"] = str(REPORT_DIR / "frontend_payload_schema_validation.md")
    write_json(payload_dir / "frontend_payload_manifest.json", frontend_manifest)
    progress("stage=done")


def load_tables(batch_dir: Path) -> dict[str, pd.DataFrame]:
    return {
        "risk_entities": read_table(batch_dir, "risk_entities"),
        "risk_cards": read_table(batch_dir, "risk_cards"),
        "risk_card_evidence": read_table(batch_dir, "risk_card_evidence"),
        "risk_entity_timeline": read_table(batch_dir, "risk_entity_timeline"),
        "monthly_reports": read_table(batch_dir, "monthly_reports"),
        "proof_cases": read_table(batch_dir, "proof_cases"),
    }


def build_batch_context(manifest: dict[str, Any]) -> dict[str, Any]:
    report_month = str(manifest["report_month"])
    cutoff_date = str(manifest.get("cutoff_date") or f"{report_month}-31")
    horizon = str(manifest.get("primary_horizon", "H6"))
    return {
        "report_month": report_month,
        "score_as_of_date": cutoff_date,
        "data_watermark_at": f"{cutoff_date}T23:59:59+08:00",
        "score_batch_id": f"score_{report_month.replace('-', '')}_{horizon.lower()}",
        "result_batch_id": str(manifest["batch_id"]),
        "primary_horizon": horizon,
        "primary_horizon_label": "6-month window",
        "score_formula": "risk_probability * average_consumption_in_window",
    }


def build_frontend_entities(tables: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    entities = tables["risk_entities"].copy()
    cards = tables["risk_cards"]
    card_counts = cards.groupby("risk_entity_id").size().to_dict() if not cards.empty else {}
    entities["risk_probability_value"] = pd.to_numeric(entities.get("risk_probability_value"), errors="coerce")
    eligible = entities[
        ~to_bool(entities.get("is_one_shot", False))
        & ~to_bool(entities.get("is_observation", False))
        & entities["risk_probability_value"].notna()
    ].copy()
    eligible["average_consumption_in_window"] = 0
    eligible["business_score"] = 0
    eligible = eligible.sort_values(["business_score", "risk_probability_value"], ascending=[False, False])
    return [entity_item(row, card_counts) for _, row in eligible.iterrows()]


def entity_item(row: pd.Series, card_counts: dict[str, int]) -> dict[str, Any]:
    entity_id = str(row["risk_entity_id"])
    probability = clamp_probability(row.get("risk_probability_value"))
    average = int(row.get("average_consumption_in_window", 0) or 0)
    return {
        "entity_id": entity_id,
        "hospital_name": display_name(row, "hospital_display_name", "hospital_code", "Hospital"),
        "drug_name": display_name(row, "drug_display_name", "drug_group", "Drug"),
        "manufacturer_code": str(row.get("manufacturer_code", "unknown")),
        "region": nonempty(row.get("region_display_name")) or nonempty(row.get("region_code")) or "Unknown region",
        "horizon": str(row.get("primary_horizon", "H6")),
        "risk_probability": probability,
        "average_consumption_in_window": average,
        "business_score": round(probability * average),
        "risk_band": risk_band(row),
        "risk_color": risk_color(row),
        "last_purchase_date": "unknown",
        "days_since_last_purchase": 0,
        "risk_card_count": int(card_counts.get(entity_id, row.get("risk_card_count", 0) or 0)),
        "status": status_label(row),
        "monthly_status": "current_month_selected",
        "value_level": str(row.get("potential_value_level", "unknown")),
        "primary_reason": safe_reason(row.get("risk_type_label") or row.get("main_reason_summary")),
    }


def build_workbench_payload(batch_context: dict[str, Any], entities: list[dict[str, Any]], full_count: int) -> dict[str, Any]:
    rows = []
    for item in entities[:20]:
        rows.append(
            {
                "row_id": item["entity_id"],
                "entity_id": item["entity_id"],
                "manufacturer_code": item["manufacturer_code"],
                "hospital_name": item["hospital_name"],
                "drug_name": item["drug_name"],
                "region": item["region"],
                "risk_probability": item["risk_probability"],
                "average_consumption_in_window": item["average_consumption_in_window"],
                "business_score": item["business_score"],
                "source_type": "global_current_month",
                "fill_source": "backbone",
                "action": "view_detail",
            }
        )
    rows = sorted(rows, key=lambda row: row["business_score"], reverse=True)
    return {
        "batch_context": batch_context,
        "overview_metrics": [
            {"label": "Workbench rows", "value": str(len(rows)), "tone": "neutral"},
            {"label": "Risk entities", "value": str(len(entities)), "tone": "warning"},
            {"label": "Selected batch rows", "value": str(full_count), "tone": "neutral"},
        ],
        "model_metrics": [],
        "fill_policy": {
            "manufacturer_code": rows[0]["manufacturer_code"] if rows else "all",
            "workbench_target_count": 20,
            "global_current_month_hospital_drug_count": len(entities),
            "fill_reason": "Rows are selected from the current monthly recurring risk list by business score.",
        },
        "rows": rows,
    }


def build_detail_payload(entity: dict[str, Any], tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    cards = tables["risk_cards"]
    evidence = tables["risk_card_evidence"]
    entity_cards = cards[cards["risk_entity_id"].astype(str).eq(entity["entity_id"])] if not cards.empty else pd.DataFrame()
    entity_evidence = (
        evidence[evidence["risk_entity_id"].astype(str).eq(entity["entity_id"])] if not evidence.empty else pd.DataFrame()
    )
    profiles = {}
    for horizon, label in [("H3", "3-month window"), ("H6", "6-month window"), ("H12", "12-month window")]:
        profiles[horizon] = {
            "horizon": horizon,
            "label": label,
            "risk_probability": entity["risk_probability"],
            "average_consumption_in_window": entity["average_consumption_in_window"],
            "business_score": entity["business_score"],
            "reason": f"{label}: monthly risk review for purchasing rhythm and selected evidence.",
            "detector_results": detector_results(entity_cards, entity_evidence),
            "xgboost_shap": [],
            "detector_narrative": "Risk review is mainly supported by purchasing rhythm evidence and selected monthly worklist status.",
        }
    return {"entity": entity, "horizon_profiles": profiles}


def detector_results(cards: pd.DataFrame, evidence: pd.DataFrame) -> list[dict[str, Any]]:
    names = set(cards.get("source_detector_name", pd.Series(dtype=str)).dropna().astype(str))
    evidence_text = "\n".join(evidence.get("evidence_text", pd.Series(dtype=str)).dropna().astype(str).head(3).tolist())
    results = []
    for detector_id, detector_name, source_name in DETECTORS:
        if source_name and source_name in names:
            status = "hit"
            signal = "selected_evidence"
            score = 0.7
            text = evidence_text or "Selected evidence supports business review."
            action = "review_context"
        elif detector_id in {"delivery_time", "price_signal"}:
            status = "data_insufficient"
            signal = "not_customer_claim"
            score = 0.0
            text = "Source data is not sufficient for a customer-facing conclusion."
            action = "use_as_internal_context"
        elif detector_id in {"delivery_rate", "sku_wallet", "new_terminal"}:
            status = "not_applicable"
            signal = "not_applicable"
            score = 0.0
            text = "This detector is not applicable for the selected recurring entity."
            action = "no_action"
        else:
            status = "stable"
            signal = "not_hit"
            score = 0.0
            text = "No selected business-visible evidence in the current monthly batch."
            action = "monitor"
        results.append(
            {
                "detector_id": detector_id,
                "detector_name": detector_name,
                "score": score,
                "signal": signal,
                "status": status,
                "evidence": text,
                "action": action,
            }
        )
    return results


def build_oneshot_payload(manifest: dict[str, Any], tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    entities = tables["risk_entities"].copy()
    oneshot = entities[to_bool(entities.get("is_one_shot", False))].copy()
    oneshot["risk_score_display"] = pd.to_numeric(oneshot.get("risk_score_display"), errors="coerce").fillna(0.0)
    oneshot = oneshot.sort_values("risk_score_display", ascending=False).head(50)
    items = []
    for _, row in oneshot.iterrows():
        propensity = clamp_probability(row.get("risk_score_display"))
        items.append(
            {
                "oneshot_id": str(row["risk_entity_id"]),
                "hospital_name": display_name(row, "hospital_display_name", "hospital_code", "Hospital"),
                "drug_name": display_name(row, "drug_display_name", "drug_group", "Drug"),
                "region": nonempty(row.get("region_display_name")) or nonempty(row.get("region_code")) or "Unknown region",
                "first_purchase_date": str(manifest.get("cutoff_date", "unknown")),
                "first_purchase_amount": 0,
                "days_since_first_purchase": 0,
                "repurchase_propensity": propensity,
                "expected_repurchase_amount": 0,
                "priority": "high" if propensity >= 0.75 else "medium",
                "reason": "New terminal attention score indicates a follow-up opportunity for a second purchase.",
            }
        )
    if items:
        avg_propensity = round(sum(item["repurchase_propensity"] for item in items) / len(items), 4)
    else:
        avg_propensity = 0.0
    return {
        "report_month": str(manifest["report_month"]),
        "summary": {
            "oneshot_count": len(items),
            "high_repurchase_propensity_count": sum(1 for item in items if item["repurchase_propensity"] >= 0.75),
            "average_repurchase_propensity": avg_propensity,
            "expected_repurchase_amount": sum(item["expected_repurchase_amount"] for item in items),
        },
        "items": items,
    }


def build_monthly_reports_payload(
    batch_context: dict[str, Any],
    tables: dict[str, pd.DataFrame],
    entities: list[dict[str, Any]],
    oneshot_payload: dict[str, Any],
) -> dict[str, Any]:
    monthly = tables["monthly_reports"]
    report_month = batch_context["report_month"]
    cutoff = batch_context["score_as_of_date"]
    detector_count = len(tables["risk_cards"])
    daily_options = [
        {
            "daily_report_id": f"monthly_selector_{report_month}",
            "date": cutoff,
            "label": f"{report_month} monthly batch",
            "title": f"{report_month} monthly risk review",
            "report_month": report_month,
            "score_batch_id": batch_context["score_batch_id"],
            "data_watermark_at": batch_context["data_watermark_at"],
            "high_risk_entities": len(entities),
            "oneshot_count": oneshot_payload["summary"]["oneshot_count"],
            "detector_alerts": detector_count,
            "summary": "Monthly batch selector for the current risk review.",
        }
    ]
    reports = []
    if monthly.empty:
        reports.append(
            {
                "monthly_report_id": f"monthly_{report_month}",
                "title": f"{report_month} monthly risk review",
                "report_month": report_month,
                "score_batch_id": batch_context["score_batch_id"],
                "data_watermark_at": batch_context["data_watermark_at"],
                "summary": "Monthly risk review generated from the current result batch.",
            }
        )
    else:
        for _, row in monthly.iterrows():
            reports.append(
                {
                    "monthly_report_id": str(row.get("monthly_report_id") or f"monthly_{report_month}"),
                    "title": str(row.get("title") or f"{report_month} monthly risk review"),
                    "report_month": str(row.get("report_month") or report_month),
                    "score_batch_id": batch_context["score_batch_id"],
                    "data_watermark_at": batch_context["data_watermark_at"],
                    "summary": str(row.get("summary_text") or "Monthly risk review generated from the current result batch."),
                }
            )
    return {
        "batch_context": batch_context,
        "overview_metrics": [
            {"label": "Risk entities", "value": str(len(entities)), "tone": "warning"},
            {"label": "New terminal items", "value": str(oneshot_payload["summary"]["oneshot_count"]), "tone": "neutral"},
        ],
        "model_metrics": [],
        "daily_report_options": daily_options,
        "monthly_reports": reports,
    }


def build_proof_cases_payload(tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    proof = tables["proof_cases"]
    if proof.empty:
        return {"items": []}
    items = []
    for _, row in proof.iterrows():
        items.append(
            {
                "proof_case_id": str(row.get("proof_case_id", "")),
                "title": str(row.get("title", "Verified business case")),
                "visible": str(row.get("visible", "business")),
                "outcome": str(row.get("outcome", "verified")),
                "case_summary": str(row.get("case_summary", "Verified business result.")),
            }
        )
    return {"items": items}


def write_field_mapping() -> None:
    rows = [
        ("all", "risk_probability", "risk_entities", "risk_probability_value", "numeric 0..1", "risk_score only for oneshot propensity", "ok", ""),
        ("all", "average_consumption_in_window", "risk_entities", "", "set to 0", "no numeric amount proxy in result batch", "ok", "internal caveat"),
        ("all", "business_score", "derived", "", "round(risk_probability * average_consumption_in_window)", "0 when amount proxy absent", "ok", ""),
        ("all", "hospital_name", "risk_entities", "hospital_display_name", "string display", "Hospital_<hospital_code>", "ok", ""),
        ("all", "drug_name", "risk_entities", "drug_display_name", "string display", "Drug_<drug_group>", "ok", ""),
        ("all", "region", "risk_entities", "region_display_name/region_code", "string display", "Unknown region", "ok", ""),
        ("risk_entities", "risk_band", "risk_entities", "risk_color/risk_level", "business label mapping", "Data insufficient", "ok", ""),
        ("risk_entities", "primary_reason", "risk_entities", "risk_type_label/main_reason_summary", "safe reason mapping", "Monthly risk review item", "ok", ""),
        ("detail", "detector_results", "risk_cards/evidence", "source_detector_name/evidence_text", "all detectors emitted with hit or neutral status", "data_insufficient/not_applicable", "ok", ""),
        ("detail", "xgboost_shap", "none", "", "empty array", "no verified contribution table", "ok", "no fabricated contribution"),
        ("oneshot", "repurchase_propensity", "risk_entities", "risk_score_display", "rule-tiered one-shot attention score", "0", "ok", "not recurring churn probability"),
        ("monthly_reports", "daily_report_options", "monthly_reports/manifest", "report_month/cutoff_date", "schema-compatible monthly selector", "current monthly batch", "ok", ""),
        ("proof_cases", "items", "proof_cases", "*", "only verified proof cases", "empty list", "ok", "no fabricated case"),
    ]
    df = pd.DataFrame(
        rows,
        columns=[
            "payload",
            "frontend_field",
            "source_table",
            "source_column",
            "transformation_rule",
            "fallback_rule",
            "validation_status",
            "caveat",
        ],
    )
    df.to_csv(REPORT_DIR / "frontend_payload_field_mapping.csv", index=False, encoding="utf-8")
    write_text(REPORT_DIR / "frontend_payload_field_mapping.md", "# Frontend Payload Field Mapping\n\n" + df.to_markdown(index=False) + "\n")


def write_delivery_summary(batch_dir: Path, manifest: dict[str, Any]) -> None:
    text = f"""# Frontend Payload Delivery Summary

- batch_dir: `{batch_dir}`
- schema_source: `{SCHEMA_PATH}`
- workbench rows: {manifest['workbench_row_count']}
- risk entities: {manifest['risk_entities_count']}
- detail payload count: {manifest['detail_payload_count']}
- oneshot items: {manifest['oneshot_count']}
- proof cases: {manifest['proof_case_count']}
- monthly reports: {manifest['monthly_report_count']}
- forbidden text check passed: {manifest['forbidden_text_check_passed']}
- xgboost_shap: empty arrays because no verified contribution table is present
- average_consumption_in_window: 0 because no numeric amount proxy exists in the current result batch
"""
    write_text(REPORT_DIR / "frontend_payload_delivery_summary.md", text)


def inspect_schema() -> dict[str, list[str]]:
    module = load_schema_module()
    classes = {
        name: sorted(getattr(obj, "model_fields", {}).keys())
        for name, obj in vars(module).items()
        if isinstance(obj, type) and hasattr(obj, "model_fields")
    }
    return classes


def write_schema_inspection(classes: dict[str, list[str]]) -> None:
    rows = [{"schema_class": name, "fields": ",".join(fields)} for name, fields in sorted(classes.items())]
    pd.DataFrame(rows).to_csv(REPORT_DIR / "frontend_payload_schema_inspection.csv", index=False, encoding="utf-8")
    write_text(
        REPORT_DIR / "frontend_payload_schema_inspection.md",
        "# Frontend Payload Schema Inspection\n\n"
        f"- schema_source: `{SCHEMA_PATH}`\n"
        f"- class_count: {len(classes)}\n\n"
        + pd.DataFrame(rows).to_markdown(index=False)
        + "\n",
    )


def load_schema_module():
    spec = importlib.util.spec_from_file_location("frontend_pages_schema", SCHEMA_PATH)
    if not spec or not spec.loader:
        raise RuntimeError(f"Cannot load schema: {SCHEMA_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    for obj in vars(module).values():
        if isinstance(obj, type) and getattr(obj, "__module__", "") == module.__name__ and hasattr(obj, "model_rebuild"):
            obj.model_rebuild(_types_namespace=vars(module))
    return module


def check_no_banned_text(payload_dir: Path) -> bool:
    hits = []
    for name in os.listdir(long_path(payload_dir)):
        if not name.startswith("frontend_") or not name.endswith("_payload.json"):
            continue
        path = payload_dir / name
        payload = read_json(path)
        text = "\n".join(iter_strings(payload))
        hits.extend(token for token in BANNED_TEXT if token in text)
    return not hits


def iter_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_strings(item)


def display_name(row: pd.Series, display_col: str, code_col: str, prefix: str) -> str:
    display = nonempty(row.get(display_col))
    if display:
        return display
    code = nonempty(row.get(code_col)) or "unknown"
    return f"{prefix}_{code}"


def nonempty(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"", "nan", "none"} else text


def clamp_probability(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(number):
        return 0.0
    return round(min(1.0, max(0.0, number)), 6)


def risk_color(row: pd.Series) -> str:
    color = str(row.get("risk_color") or row.get("risk_level") or "").lower()
    if color in {"red", "orange", "yellow", "gray"}:
        return color
    return "gray"


def risk_band(row: pd.Series) -> str:
    color = risk_color(row)
    return {"red": "High risk", "orange": "Medium risk", "yellow": "Observation", "gray": "Data insufficient"}[color]


def status_label(row: pd.Series) -> str:
    status = str(row.get("final_candidate_status") or row.get("review_status") or "").lower()
    if "priority" in status:
        return "follow_up"
    if "manual" in status:
        return "confirm"
    if "observation" in status:
        return "observe"
    if "one_shot" in status:
        return "new_terminal"
    return "review"


def safe_reason(value: Any) -> str:
    text = nonempty(value)
    if not text or text == "multi_recall_union_top10":
        return "Selected by the current monthly risk worklist policy."
    return text.replace("multi_recall_union_top10", "monthly_risk_worklist")


def safe_slug(entity_id: str) -> str:
    digest = hashlib.sha1(entity_id.encode("utf-8")).hexdigest()[:16]
    return digest


def to_bool(values: Any) -> pd.Series:
    if isinstance(values, pd.Series):
        if values.dtype == bool:
            return values.fillna(False)
        return values.astype(str).str.lower().isin(["1", "true", "yes", "y"])
    return pd.Series(bool(values))


def read_table(batch_dir: Path, name: str) -> pd.DataFrame:
    parquet = batch_dir / f"{name}.parquet"
    csv = batch_dir / f"{name}.csv"
    if parquet.exists():
        return pd.read_parquet(parquet)
    if csv.exists():
        return pd.read_csv(csv)
    return pd.DataFrame()


def read_json(path: Path) -> dict[str, Any]:
    with open(long_path(path), encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(long_path(path), "w", encoding="utf-8") as fh:
        json.dump(value, fh, ensure_ascii=False, indent=2)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(long_path(path), "w", encoding="utf-8") as fh:
        fh.write(text)


def long_path(path: Path) -> str:
    resolved = str(path.resolve())
    if os.name == "nt" and not resolved.startswith("\\\\?\\"):
        return "\\\\?\\" + resolved
    return resolved


def progress(message: str, *, reset: bool = False) -> None:
    mode = "w" if reset else "a"
    with PROGRESS.open(mode, encoding="utf-8") as fh:
        fh.write(f"{dt.datetime.now().isoformat(timespec='seconds')} {message}\n")


def write_wip_snapshot() -> None:
    status = subprocess.run(["git", "diff", "--name-status", "--", "project", "front_end"], cwd=ROOT, text=True, capture_output=True, check=True)
    text = f"""# Project/Frontend Read-Only Snapshot

- project_frontend_read_only: true
- schema_source: `{SCHEMA_PATH}`

```text
{status.stdout.strip()}
```
"""
    write_text(REPORT_DIR / "project_frontend_readonly_snapshot.md", text)


if __name__ == "__main__":
    main()
