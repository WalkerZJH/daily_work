import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BATCH_DIR = (
    ROOT
    / "algo_main"
    / "data"
    / "entity_complete_v2_coverage_expansion"
    / "13_formal_algorithm_core_raw_to_batch"
    / "formal_result_batches"
    / "report_month=2025-12"
    / "batch_id=2025-12-monthly-risk-algorithm-formal-v2-raw"
)
PAYLOAD_DIR = BATCH_DIR / "page_payloads"
REPORT_DIR = ROOT / "algo_main" / "reports" / "entity_complete_v2_coverage_expansion" / "22_frontend_payload_delivery"
SCHEMA_PATH = ROOT / "project" / "app" / "schemas" / "frontend_pages.py"

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


def load_json(name: str) -> dict[str, Any]:
    with open(long_path(PAYLOAD_DIR / name), encoding="utf-8") as fh:
        return json.load(fh)


def exists(path: Path) -> bool:
    return os.path.exists(long_path(path))


def long_path(path: Path) -> str:
    resolved = str(path.resolve())
    if os.name == "nt" and not resolved.startswith("\\\\?\\"):
        return "\\\\?\\" + resolved
    return resolved


def iter_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_strings(item)


def load_schema_module():
    spec = importlib.util.spec_from_file_location("frontend_pages_schema_for_test", SCHEMA_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    for obj in vars(module).values():
        if isinstance(obj, type) and getattr(obj, "__module__", "") == module.__name__ and hasattr(obj, "model_rebuild"):
            obj.model_rebuild(_types_namespace=vars(module))
    return module


def test_core_frontend_payload_files_exist() -> None:
    assert exists(PAYLOAD_DIR / "frontend_workbench_payload.json")
    assert exists(PAYLOAD_DIR / "frontend_risk_entities_payload.json")
    assert exists(PAYLOAD_DIR / "frontend_oneshot_payload.json")
    assert exists(PAYLOAD_DIR / "frontend_monthly_reports_payload.json")
    assert exists(PAYLOAD_DIR / "frontend_proof_cases_payload.json")
    detail_files = [name for name in os.listdir(long_path(PAYLOAD_DIR)) if name.startswith("frontend_risk_entity_detail_")]
    assert detail_files


def test_payloads_validate_against_project_schema() -> None:
    schema = load_schema_module()
    schema.WorkbenchPayload.model_validate(load_json("frontend_workbench_payload.json"))
    schema.RiskEntitiesPayload.model_validate(load_json("frontend_risk_entities_payload.json"))
    schema.OneshotPayload.model_validate(load_json("frontend_oneshot_payload.json"))
    schema.MonthlyReportsPayload.model_validate(load_json("frontend_monthly_reports_payload.json"))
    schema.ProofCasesPayload.model_validate(load_json("frontend_proof_cases_payload.json"))
    manifest = load_json("frontend_payload_manifest.json")
    first_detail = manifest["detail_payloads"][0]["detail_payload_file"]
    schema.RiskEntityDetailPayload.model_validate(load_json(first_detail))


def test_model_core_page_payload_builder_reads_slugged_detail_payload() -> None:
    from risk_model_core.page_payload_builder import PagePayloadBuilder
    from risk_model_core.repositories import ParquetRiskResultRepository

    manifest = load_json("frontend_payload_manifest.json")
    entity_id = manifest["detail_payloads"][0]["entity_id"]
    payload = PagePayloadBuilder(ParquetRiskResultRepository(BATCH_DIR)).build_frontend_risk_entity_detail_payload(entity_id)
    assert payload["entity"]["entity_id"] == entity_id


def test_workbench_rows_are_twenty_sorted_and_formula_based() -> None:
    payload = load_json("frontend_workbench_payload.json")
    rows = payload["rows"]
    assert len(rows) == 20
    scores = [row["business_score"] for row in rows]
    assert scores == sorted(scores, reverse=True)
    for row in rows:
        assert {"manufacturer_code", "hospital_name", "drug_name", "region"}.issubset(row)
        assert 0 <= row["risk_probability"] <= 1
        assert isinstance(row["average_consumption_in_window"], int)
        assert row["business_score"] == round(row["risk_probability"] * row["average_consumption_in_window"])


def test_risk_entities_are_sorted_and_have_stable_display_fields() -> None:
    payload = load_json("frontend_risk_entities_payload.json")
    entities = payload["entities"]
    assert payload["pagination"]["total_items"] == len(entities)
    assert entities
    scores = [item["business_score"] for item in entities]
    assert scores == sorted(scores, reverse=True)
    for item in entities[:50]:
        assert item["manufacturer_code"]
        assert item["hospital_name"]
        assert item["drug_name"]
        assert item["region"]
        assert 0 <= item["risk_probability"] <= 1
        assert item["business_score"] == round(item["risk_probability"] * item["average_consumption_in_window"])


def test_detail_payloads_have_horizons_all_detectors_and_empty_shap_when_unavailable() -> None:
    manifest = load_json("frontend_payload_manifest.json")
    detail = load_json(manifest["detail_payloads"][0]["detail_payload_file"])
    assert set(detail["horizon_profiles"]) == {"H3", "H6", "H12"}
    expected_detector_ids = {
        "purchase_gap",
        "frequency_drop",
        "quantity_drop",
        "terminal_loss",
        "new_terminal",
        "delivery_time",
        "delivery_rate",
        "price_signal",
        "sku_wallet",
    }
    for profile in detail["horizon_profiles"].values():
        detector_ids = {item["detector_id"] for item in profile["detector_results"]}
        assert expected_detector_ids.issubset(detector_ids)
        assert profile["xgboost_shap"] == []
        assert profile["detector_narrative"]


def test_oneshot_and_proof_cases_respect_business_boundaries() -> None:
    oneshot = load_json("frontend_oneshot_payload.json")
    assert oneshot["summary"]["oneshot_count"] == len(oneshot["items"])
    for item in oneshot["items"]:
        assert "risk_probability" not in item
        assert 0 <= item["repurchase_propensity"] <= 1
    proof_cases = load_json("frontend_proof_cases_payload.json")
    assert proof_cases["items"] == []


def test_no_banned_text_and_reports_exist() -> None:
    for name in os.listdir(long_path(PAYLOAD_DIR)):
        if not name.startswith("frontend_") or not name.endswith("_payload.json"):
            continue
        payload = load_json(name)
        strings = "\n".join(iter_strings(payload))
        assert not [token for token in BANNED_TEXT if token in strings], name
    assert exists(REPORT_DIR / "frontend_payload_schema_validation.md")
    assert exists(REPORT_DIR / "frontend_payload_schema_validation.csv")
    assert exists(REPORT_DIR / "frontend_payload_field_mapping.md")
    assert exists(REPORT_DIR / "frontend_payload_field_mapping.csv")
