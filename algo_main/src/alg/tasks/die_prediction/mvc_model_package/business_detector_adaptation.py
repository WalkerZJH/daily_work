"""Business detector adaptation pipeline for bounded frontend worklists."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json

import pandas as pd

from .business_copy_renderer import BusinessCopyRenderer
from .detector_quality_gate import build_detector_business_readiness_matrix, build_detector_quality_gate
from .export_manifest import build_export_manifest
from .importers import MClosurePaths, MClosureResultImporter
from .page_payload_builder import PagePayloadBuilder
from .pipeline import DATA_ROOT, M_DATA_DIR, REPORT_ROOT, build_manifest, ensure_done
from .repositories import ParquetRiskResultRepository
from .scope_config import FrontendScopeConfig
from .selectors import select_frontend_worklist_candidates
from .transformers import infer_report_month, transform_m_closure_to_result_tables, write_sample_csvs


ADAPT_DATA_DIR = DATA_ROOT / "11_business_detector_adaptation"
ADAPT_REPORT_DIR = REPORT_ROOT / "15_business_detector_adaptation"
ADAPT_PROGRESS_PATH = ADAPT_REPORT_DIR / "business_detector_adaptation_progress.md"


def run_business_detector_adaptation(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    ensure_output_dirs(root)
    progress(root, "stage=start", reset=True)
    ensure_done(root)
    ensure_frontend_worklist_done(root)

    progress(root, "stage=load_frontend_scope")
    importer = MClosureResultImporter(
        MClosurePaths(
            data_dir=root / M_DATA_DIR,
            gate_path=root / DATA_ROOT / "08_service_gate/probability_availability_gate.csv",
            report_dir=root / REPORT_ROOT / "11_m_module_closure",
        )
    )
    inputs = importer.load_frontend_worklist()
    available_fields = available_field_names(inputs)

    progress(root, "stage=detector_readiness")
    readiness = build_detector_business_readiness_matrix(available_fields=available_fields)
    gate = build_detector_quality_gate(readiness)
    write_csv(root / ADAPT_REPORT_DIR / "detector_business_readiness_matrix.csv", readiness)
    write_csv(root / ADAPT_DATA_DIR / "detector_quality_gate.csv", gate)
    (root / ADAPT_REPORT_DIR / "detector_business_readiness_summary.md").write_text(render_readiness_summary(readiness), encoding="utf-8")

    progress(root, "stage=transform_business_detector_batch")
    config = FrontendScopeConfig()
    frontend_scope = select_frontend_worklist_candidates(inputs, config)
    selected_ids = set(frontend_scope["candidate_id"].dropna().astype(str))
    tables = transform_m_closure_to_result_tables(
        inputs,
        selected_candidate_ids=selected_ids,
        max_cards_per_entity=config.max_cards_per_entity,
        max_business_visible_evidence_per_card=config.max_business_visible_evidence_per_card,
        detector_quality_gate=gate,
    )
    disabled_notes = build_disabled_detector_notes(gate)
    report_month = infer_report_month(inputs["m5"])
    batch_id = f"{report_month}-business-detector-v1"
    batch_dir = root / ADAPT_DATA_DIR / "risk_result_batches" / f"batch_id={batch_id}"
    manifest = build_manifest(batch_id, report_month, tables)
    manifest.update(
        {
            "package_scope": "business_detector_frontend_worklist",
            "source_frontend_worklist_batch": str(root / DATA_ROOT / "10_frontend_worklist_model_package"),
            "detector_quality_gate_path": str(root / ADAPT_DATA_DIR / "detector_quality_gate.csv"),
            "customer_facing_probability_service_allowed": False,
            "auto_dispatch_allowed": False,
            "proof_case_report_allowed": False,
        }
    )

    repo = ParquetRiskResultRepository(batch_dir)
    for name, table in tables.items():
        repo.save_table(name, table)
    repo.save_table("disabled_detector_notes", disabled_notes)
    write_sample_csvs(batch_dir, tables)
    repo.save_json("manifest.json", manifest)
    gate.to_csv(batch_dir / "detector_quality_gate.csv", index=False, encoding="utf-8")

    progress(root, "stage=page_payloads")
    payloads = PagePayloadBuilder().build_all(tables, manifest)
    payloads = patch_business_detector_payloads(payloads, gate)
    PagePayloadBuilder().write_payloads(batch_dir / "page_payloads", payloads)

    progress(root, "stage=reports")
    write_adaptation_reports(root, tables, gate, disabled_notes, batch_dir)

    progress(root, "stage=done")
    return {
        "batch_id": batch_id,
        "batch_dir": str(batch_dir),
        "counts": {name: len(table) for name, table in tables.items()},
        "detector_gate_rows": len(gate),
        "disabled_detector_notes": len(disabled_notes),
    }


def ensure_output_dirs(root: Path) -> None:
    (root / ADAPT_DATA_DIR).mkdir(parents=True, exist_ok=True)
    (root / ADAPT_REPORT_DIR).mkdir(parents=True, exist_ok=True)


def ensure_frontend_worklist_done(root: Path) -> None:
    path = root / REPORT_ROOT / "14_frontend_worklist_model_package/frontend_worklist_package_progress.md"
    text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    if "stage=done" not in text:
        raise RuntimeError(f"Required frontend worklist progress is not done: {path}")


def progress(root: Path, message: str, *, reset: bool = False) -> None:
    path = root / ADAPT_PROGRESS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    line = f"{pd.Timestamp.now().isoformat()} {message}\n"
    if reset:
        path.write_text(line, encoding="utf-8")
    else:
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
    print(message, flush=True)


def available_field_names(inputs: dict[str, pd.DataFrame]) -> set[str]:
    fields: set[str] = set()
    for df in inputs.values():
        if isinstance(df, pd.DataFrame):
            fields.update(map(str, df.columns))
    return fields


def build_disabled_detector_notes(gate: pd.DataFrame) -> pd.DataFrame:
    renderer = BusinessCopyRenderer()
    disabled = gate[~gate["enable_frontend_display"].astype(bool)].copy()
    rows = []
    for _, row in disabled.iterrows():
        note = renderer.render_disabled_detector_note(str(row["detector_name"]))
        rows.append(
            {
                "detector_name": row["detector_name"],
                "gate_status": row["gate_status"],
                "disabled_reason_text": note["disabled_reason_text"],
                "visibility_level": "internal_only",
                "enable_frontend_display": bool(row["enable_frontend_display"]),
                "enable_customer_copy": bool(row["enable_customer_copy"]),
                "reason_code": row["reason_code"],
            }
        )
    return pd.DataFrame(rows)


def patch_business_detector_payloads(payloads: dict[str, Any], gate: pd.DataFrame) -> dict[str, Any]:
    clues = payloads.get("clues_payload", {})
    for item in clues.get("items", []):
        item["risk_type_label"] = item.get("root_cause_label")
        item["evidence_type_label"] = item.get("root_cause_label")
    distributor = payloads.get("distributor_payload", {})
    distributor.update(
        {
            "delivery_detector_enabled": False,
            "detector_status": "disabled_missing_data",
            "reason": "delivery_time / arrival_time missingness is too high for response-time analysis",
            "alerts": [],
        }
    )
    payloads["distributor_payload"] = distributor
    payloads["detector_quality_gate"] = {
        "enabled_rule_v1": gate[gate["gate_status"].eq("enabled")]["detector_name"].tolist(),
        "weak_enabled_review_required": gate[gate["gate_status"].eq("weak_enabled_review_required")]["detector_name"].tolist(),
        "disabled": gate[gate["gate_status"].eq("disabled")]["detector_name"].tolist(),
        "customer_facing_probability_service_allowed": False,
        "auto_dispatch_allowed": False,
    }
    return payloads


def write_adaptation_reports(root: Path, tables: dict[str, pd.DataFrame], gate: pd.DataFrame, disabled_notes: pd.DataFrame, batch_dir: Path) -> None:
    (root / ADAPT_REPORT_DIR / "one_shot_frontend_adaptation.md").write_text(render_one_shot_report(tables["risk_entities"]), encoding="utf-8")
    (root / ADAPT_REPORT_DIR / "demand_shape_frontend_adaptation.md").write_text(render_demand_shape_report(tables["risk_entities"]), encoding="utf-8")
    gaps = business_required_inputs()
    write_csv(root / ADAPT_REPORT_DIR / "business_required_inputs.csv", gaps)
    (root / ADAPT_REPORT_DIR / "business_adaptation_gap_list.md").write_text(render_gap_list(gaps), encoding="utf-8")
    export_manifest = build_export_manifest(f"{infer_report_month(tables['risk_entities'])}-business-detector-v1", batch_dir)
    (root / ADAPT_DATA_DIR / "report_export_manifest.json").write_text(json.dumps(export_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / ADAPT_REPORT_DIR / "export_readiness_for_reports.md").write_text(render_export_readiness(export_manifest), encoding="utf-8")
    (root / ADAPT_REPORT_DIR / "business_detector_adaptation_summary.md").write_text(render_adaptation_summary(tables, gate, disabled_notes, batch_dir), encoding="utf-8")


def render_readiness_summary(readiness: pd.DataFrame) -> str:
    enabled = readiness[readiness["implementation_status"].eq("enabled_rule_v1")]["detector_name"].tolist()
    weak = readiness[readiness["implementation_status"].eq("weak_enabled_review_required")]["detector_name"].tolist()
    interface = readiness[readiness["implementation_status"].isin(["interface_only", "internal_only"])]["detector_name"].tolist()
    deferred = readiness[readiness["implementation_status"].str.startswith("deferred")]["detector_name"].tolist()
    return f"""# Detector Business Readiness Summary

detector 没有全部完成。当前可用于业务展示的是规则型证据，不是完整根因归因，也不是概率。

- enabled_rule_v1: {enabled}
- weak_enabled_review_required: {weak}
- interface_only / internal_only: {interface}
- deferred: {deferred}

配送时间类 detector 暂不做：`delivery_time` / `arrival_time` 缺失率和回填稳定性不足，不能支持配送时效分析，也不能形成配送商责任结论。

price / sku / wallet share 暂不强做：价格缺少可比价口径，SKU/portfolio 缺少稳定产品线映射，choice-set 不是完整市场上下文。

前端展示 disabled detector 时，应显示“暂未启用 / 数据质量不足 / 需补充业务映射”，不得显示确定性归因。
"""


def render_one_shot_report(entities: pd.DataFrame) -> str:
    count = int(entities["is_one_shot"].sum()) if "is_one_shot" in entities else 0
    return f"""# One-shot Frontend Adaptation

- one-shot rows in business detector package: {count}
- display section: 新进终端关注。
- recurring churn probability display: forbidden.
- suggested action: 判断是否需要促进第二次采购。
- probability_display_level: hidden/not_available unless an independent repeat model is built and validated.
"""


def render_demand_shape_report(entities: pd.DataFrame) -> str:
    count = int(entities["is_observation"].sum()) if "is_observation" in entities else 0
    return f"""# Demand-shape Frontend Adaptation

- observation rows in business detector package: {count}
- intermittent / lumpy default: observation.
- H3 strong alert: disabled by default for low-frequency shapes.
- display: 观察对象，不代表高风险。
- caveat: 低频采购关系不适合短期强判断，需要持续观察。
"""


def business_required_inputs() -> pd.DataFrame:
    rows = [
        ("product_line_mapping", "SKU/portfolio detector and product-line display", "missing_or_partial", "drug_group currently falls back to drug_code", "business", "data", True, "是否可以提供生产商产品线/组合映射？"),
        ("comparable_price_scope", "price detectors", "missing", "no validated comparable-price group", "business", "data", True, "价格比较应按什么同品/同规格/同区域口径？"),
        ("delivery_arrival_time_rule", "delivery response detectors", "missing", "delivery_time / arrival_time missingness too high", "operations", "data", True, "配送/到货时间字段是否可回填且可靠？"),
        ("sales_owner_mapping", "worklist routing", "missing", "no region manager / salesperson relationship", "sales", "backend", True, "每个医院或区域应路由给谁？"),
        ("display_capacity", "monthly worklist", "needs_decision", "default/max display count needs business approval", "business", "product", False, "每企业默认展示 20、最大 50 是否合适？"),
        ("one_shot_section", "new terminal attention", "needs_decision", "one-shot is separate from recurring risk", "business", "product", False, "是否需要将新进终端关注做成独立栏目？"),
        ("observation_section", "watchlist", "needs_decision", "observation is not high risk", "business", "product", False, "是否需要观察清单及升级规则？"),
        ("risk_thresholds", "risk level display", "needs_decision", "thresholds are currently product policy", "business", "algorithm", True, "红/橙/黄阈值和展示口径是否接受？"),
        ("feedback_fields", "proof-case and verification", "missing", "no customer-confirmed feedback loop", "business", "backend", True, "业务复核需要回填哪些字段？"),
        ("relative_value_display", "value at risk display", "needs_decision", "amount fields are sensitive/relative", "business", "product", False, "是否只展示相对潜在影响等级？"),
        ("probability_display_policy", "customer-facing probability", "blocked", "service gate currently false", "business", "algorithm", True, "客户侧是否只展示风险等级，不展示精确概率？"),
    ]
    return pd.DataFrame(rows, columns=["input_name", "required_for", "current_status", "missing_reason", "business_owner", "technical_owner", "blocking_customer_facing", "suggested_question_to_business"])


def render_gap_list(gaps: pd.DataFrame) -> str:
    lines = ["# Business Adaptation Gap List", ""]
    for _, row in gaps.iterrows():
        lines.append(f"- {row['input_name']}: {row['current_status']}；{row['suggested_question_to_business']}")
    return "\n".join(lines) + "\n"


def render_export_readiness(export_manifest: dict[str, Any]) -> str:
    return f"""# Export Readiness for Reports

- formal PDF generated: false.
- current output: HTML/Markdown-ready payload plus parquet/csv bundle.
- PDF should be rendered by backend or frontend distribution layer.
- export formats supported: html, markdown, csv_bundle, future_pdf, future_xlsx.

```json
{json.dumps(export_manifest, ensure_ascii=False, indent=2)}
```
"""


def render_adaptation_summary(tables: dict[str, pd.DataFrame], gate: pd.DataFrame, disabled_notes: pd.DataFrame, batch_dir: Path) -> str:
    return f"""# Business Detector Adaptation Summary

- batch directory: {batch_dir}
- risk_entities rows: {len(tables['risk_entities'])}
- risk_cards rows: {len(tables['risk_cards'])}
- risk_card_evidence rows: {len(tables['risk_card_evidence'])}
- detector quality gate rows: {len(gate)}
- disabled detector notes rows: {len(disabled_notes)}
- auto_dispatch_allowed: false
- customer-facing probability service: false
- proof_case_report: false
"""


def write_csv(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")

