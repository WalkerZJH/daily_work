"""Pipeline for MVC model package extraction and frontend payload generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import re

import pandas as pd

from .batch_manifest import ResultBatchManifest
from .business_copy_renderer import BusinessCopyRenderer
from .export_manifest import build_export_manifest
from .importers import MClosurePaths, MClosureResultImporter
from .page_payload_builder import PagePayloadBuilder
from .repositories import ParquetRiskResultRepository
from .scope_config import FrontendScopeConfig
from .selectors import select_frontend_worklist_candidates
from .transformers import infer_report_month, transform_m_closure_to_result_tables, write_sample_csvs
from .visibility import internal_full_dump_manifest


VERSION = "entity_complete_v2_coverage_expansion"
DATA_ROOT = Path(f"data/{VERSION}")
REPORT_ROOT = Path(f"reports/{VERSION}")
M_DATA_DIR = DATA_ROOT / "09_m_module_closure"
MVC_DATA_DIR = DATA_ROOT / "10_mvc_model_package"
MVC_REPORT_DIR = REPORT_ROOT / "13_mvc_model_extraction"
PROGRESS_PATH = MVC_REPORT_DIR / "mvc_model_extraction_progress.md"
FRONTEND_DATA_DIR = DATA_ROOT / "10_frontend_worklist_model_package"
FRONTEND_REPORT_DIR = REPORT_ROOT / "14_frontend_worklist_model_package"
FRONTEND_PROGRESS_PATH = FRONTEND_REPORT_DIR / "frontend_worklist_package_progress.md"

FRONTEND_FILES = [
    "front_end/layout/layout.js",
    "front_end/src/layout/navigation.js",
    "front_end/index.html",
    "front_end/clues.html",
    "front_end/clue-detail.html",
    "front_end/watchlist.html",
    "front_end/dashboard.html",
    "front_end/backtest.html",
    "front_end/verify.html",
    "front_end/distributor.html",
    "front_end/order-detail.html",
    "front_end/vite.config.js",
]
DESIGN_FILE = "daily_work/notes/new_ver/前后端设计草案/终端风险线索系统前后端模块设计书_v0_2.md"
TEXT_SAFETY_PATTERNS = ["竞品替代迹象明显", "竞品替代", "非集采落标", "集采落标", "配送商责任", "FDR", "MK显著", "MK检验", "Theil-Sen", "CUSUM", "L3", "AUC", "ECE", "XGBoost", "确认流失", "确定流失", "自动派单", "已挽回", "兑现率", "ROI"]


def run_mvc_model_package(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    workspace = workspace_root(root)
    ensure_dirs(root)
    progress(root, "stage=start", reset=True)
    ensure_done(root)

    progress(root, "stage=detector_audit")
    detector = detector_readiness_matrix()
    write_csv(root / MVC_REPORT_DIR / "detector_frontend_readiness_matrix.csv", detector)
    (root / MVC_REPORT_DIR / "detector_completion_for_frontend.md").write_text(render_detector_report(detector), encoding="utf-8")

    progress(root, "stage=frontend_text_audit")
    unsafe = frontend_text_findings(workspace)
    write_csv(root / MVC_REPORT_DIR / "frontend_text_replacement_suggestions.csv", unsafe)
    (root / MVC_REPORT_DIR / "frontend_text_safety_audit.md").write_text(render_frontend_text_audit(unsafe), encoding="utf-8")

    progress(root, "stage=internal_scope_audit")
    internal_counts = audit_internal_full_package(root)
    write_internal_full_dump_marker(root, internal_counts)

    progress(root, "stage=import_frontend_worklist")
    importer = MClosureResultImporter(
        MClosurePaths(
            data_dir=root / M_DATA_DIR,
            gate_path=root / DATA_ROOT / "08_service_gate/probability_availability_gate.csv",
            report_dir=root / REPORT_ROOT / "11_m_module_closure",
        )
    )
    inputs = importer.load_frontend_worklist()
    config = FrontendScopeConfig()
    frontend_scope = select_frontend_worklist_candidates(inputs, config)
    selected_candidate_ids = set(frontend_scope["candidate_id"].dropna().astype(str))
    report_month = infer_report_month(inputs["m5"])
    batch_id = f"{report_month}-frontend-worklist-v1"
    batch_dir = root / FRONTEND_DATA_DIR / "risk_result_batches" / f"batch_id={batch_id}"

    frontend_progress(root, "stage=transform_frontend_worklist_tables", reset=True)
    tables = transform_m_closure_to_result_tables(
        inputs,
        selected_candidate_ids=selected_candidate_ids,
        max_cards_per_entity=config.max_cards_per_entity,
        max_business_visible_evidence_per_card=config.max_business_visible_evidence_per_card,
    )
    manifest = build_manifest(batch_id, report_month, tables)
    manifest.update(
        {
            "package_scope": "frontend_worklist",
            "source_internal_package": str(root / MVC_DATA_DIR),
            "source_m1_worklist_rows": int(len(inputs["worklist"])),
            "risk_entities_rows": int(len(tables["risk_entities"])),
            "risk_cards_rows": int(len(tables["risk_cards"])),
            "evidence_rows": int(len(tables["risk_card_evidence"])),
            "max_topN_per_manufacturer": config.frontend_max_topn_per_manufacturer,
            "default_topN_per_manufacturer": config.frontend_default_topn_per_manufacturer,
            "is_bounded": True,
            "full_status_rows_available": bool(internal_counts.get("risk_entities", 0)),
            "full_status_visibility": "internal_only",
            "not_for_customer_probability_service": True,
            "auto_dispatch_allowed": False,
        }
    )
    repo = ParquetRiskResultRepository(batch_dir)
    for name, table in tables.items():
        repo.save_table(name, table)
    write_sample_csvs(batch_dir, tables)
    repo.save_json("manifest.json", manifest)

    frontend_progress(root, "stage=page_payloads")
    builder = PagePayloadBuilder()
    payloads = builder.build_all(tables, manifest)
    builder.write_payloads(batch_dir / "page_payloads", payloads)

    frontend_progress(root, "stage=export_manifest")
    export_manifest = build_export_manifest(batch_id, batch_dir)
    (root / FRONTEND_DATA_DIR / "export_manifest.json").write_text(json.dumps(export_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / MVC_REPORT_DIR / "report_export_contract.md").write_text(render_export_contract(export_manifest), encoding="utf-8")

    frontend_progress(root, "stage=scope_reports")
    write_frontend_scope_reports(root, internal_counts, tables, inputs, config)

    frontend_progress(root, "stage=contracts")
    api = api_contract()
    mapping = field_mapping()
    write_csv(root / MVC_REPORT_DIR / "frontend_page_api_contract.csv", api)
    write_csv(root / MVC_REPORT_DIR / "algorithm_to_frontend_field_mapping.csv", mapping)
    (root / MVC_REPORT_DIR / "mvc_model_package_design.md").write_text(render_model_design(api, mapping, workspace / DESIGN_FILE), encoding="utf-8")

    frontend_progress(root, "stage=summary")
    (root / FRONTEND_REPORT_DIR / "frontend_worklist_scope_summary.md").write_text(render_frontend_worklist_summary(batch_dir, tables, inputs, internal_counts), encoding="utf-8")
    (root / MVC_REPORT_DIR / "mvc_model_package_summary.md").write_text(render_summary(batch_dir, tables, unsafe), encoding="utf-8")

    frontend_progress(root, "stage=done")
    progress(root, "stage=done")
    return {
        "batch_id": batch_id,
        "batch_dir": str(batch_dir),
        "counts": {k: len(v) for k, v in tables.items()},
        "internal_counts": internal_counts,
        "unsafe_frontend_text_count": len(unsafe),
    }


def ensure_dirs(root: Path) -> None:
    (root / MVC_REPORT_DIR).mkdir(parents=True, exist_ok=True)
    (root / MVC_DATA_DIR).mkdir(parents=True, exist_ok=True)
    (root / FRONTEND_REPORT_DIR).mkdir(parents=True, exist_ok=True)
    (root / FRONTEND_DATA_DIR).mkdir(parents=True, exist_ok=True)


def progress(root: Path, message: str, *, reset: bool = False) -> None:
    path = root / PROGRESS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    line = f"{pd.Timestamp.now().isoformat()} {message}\n"
    if reset:
        path.write_text(line, encoding="utf-8")
    else:
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
    print(message, flush=True)


def frontend_progress(root: Path, message: str, *, reset: bool = False) -> None:
    path = root / FRONTEND_PROGRESS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    line = f"{pd.Timestamp.now().isoformat()} {message}\n"
    if reset:
        path.write_text(line, encoding="utf-8")
    else:
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
    print(message, flush=True)


def ensure_done(root: Path) -> None:
    checks = [
        root / REPORT_ROOT / "coverage_expansion_progress.md",
        root / REPORT_ROOT / "11_m_module_closure/m_module_closure_progress.md",
    ]
    for path in checks:
        text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
        if "stage=done" not in text:
            raise RuntimeError(f"Required progress file is not done: {path}")


def audit_internal_full_package(root: Path) -> dict[str, int]:
    batch_root = root / MVC_DATA_DIR / "risk_result_batches"
    batch_dirs = sorted(batch_root.glob("batch_id=*")) if batch_root.exists() else []
    counts = {"risk_entities": 0, "risk_cards": 0, "risk_card_evidence": 0}
    if batch_dirs:
        batch_dir = batch_dirs[-1]
        counts = {
            "risk_entities": parquet_row_count(batch_dir / "risk_entities.parquet"),
            "risk_cards": parquet_row_count(batch_dir / "risk_cards.parquet"),
            "risk_card_evidence": parquet_row_count(batch_dir / "risk_card_evidence.parquet"),
        }
    (root / MVC_REPORT_DIR / "mvc_package_scope_audit.md").write_text(render_internal_scope_audit(counts), encoding="utf-8")
    return counts


def write_internal_full_dump_marker(root: Path, counts: dict[str, int]) -> None:
    marker = internal_full_dump_manifest()
    marker.update(
        {
            "risk_entities_rows": counts.get("risk_entities", 0),
            "risk_cards_rows": counts.get("risk_cards", 0),
            "evidence_rows": counts.get("risk_card_evidence", 0),
        }
    )
    (root / MVC_DATA_DIR / "internal_full_status_manifest.json").write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")


def parquet_row_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        import pyarrow.parquet as pq

        return int(pq.ParquetFile(path).metadata.num_rows)
    except Exception:
        return int(len(pd.read_parquet(path)))


def render_internal_scope_audit(counts: dict[str, int]) -> str:
    exceeds = counts.get("risk_entities", 0) > 30_000 or counts.get("risk_cards", 0) > 150_000
    return f"""# MVC Package Scope Audit

The existing `10_mvc_model_package` output is retained as an internal/debug artifact only.

- current RiskEntity rows: {counts.get("risk_entities", 0)}
- current RiskCard rows: {counts.get("risk_cards", 0)}
- current Evidence rows: {counts.get("risk_card_evidence", 0)}
- likely source tables: full M5 candidate_status_decision plus broad M4/M7 row-level outputs.
- exceeds frontend worklist scale: {str(exceeds).lower()}
- visibility: internal_only
- not_for_frontend_default: true

Frontend pages must use `10_frontend_worklist_model_package`, not the broad internal dump.
"""


def write_frontend_scope_reports(
    root: Path,
    internal_counts: dict[str, int],
    tables: dict[str, pd.DataFrame],
    inputs: dict[str, pd.DataFrame],
    config: FrontendScopeConfig,
) -> None:
    comparison = pd.DataFrame(
        [
            {
                "package_name": "internal_full_status_package",
                "scope": "full_status_internal_debug",
                "risk_entity_rows": internal_counts.get("risk_entities", 0),
                "risk_card_rows": internal_counts.get("risk_cards", 0),
                "evidence_rows": internal_counts.get("risk_card_evidence", 0),
                "intended_consumer": "algorithm_audit",
                "frontend_default_allowed": False,
                "analyst_allowed": True,
                "customer_visible_allowed": False,
                "caveat": "not a frontend default data source",
            },
            {
                "package_name": "frontend_worklist_package",
                "scope": "m1_manufacturer_worklist_bounded",
                "risk_entity_rows": len(tables["risk_entities"]),
                "risk_card_rows": len(tables["risk_cards"]),
                "evidence_rows": len(tables["risk_card_evidence"]),
                "intended_consumer": "frontend_worklist_and_analyst_view",
                "frontend_default_allowed": True,
                "analyst_allowed": True,
                "customer_visible_allowed": False,
                "caveat": "customer-facing probability service remains disabled",
            },
        ]
    )
    write_csv(root / FRONTEND_REPORT_DIR / "frontend_vs_internal_package_comparison.csv", comparison)


def render_frontend_worklist_summary(batch_dir: Path, tables: dict[str, pd.DataFrame], inputs: dict[str, pd.DataFrame], internal_counts: dict[str, int]) -> str:
    cards_per_entity = tables["risk_cards"].groupby("risk_entity_id").size().max() if len(tables["risk_cards"]) else 0
    evidence_per_card = tables["risk_card_evidence"].groupby("risk_card_id").size().max() if len(tables["risk_card_evidence"]) else 0
    return f"""# Frontend Worklist Scope Summary

- frontend batch directory: {batch_dir}
- source worklist rows: {len(inputs.get("worklist", pd.DataFrame()))}
- frontend RiskEntity rows: {len(tables["risk_entities"])}
- frontend RiskCard rows: {len(tables["risk_cards"])}
- frontend Evidence rows: {len(tables["risk_card_evidence"])}
- old internal RiskEntity rows: {internal_counts.get("risk_entities", 0)}
- old internal RiskCard rows: {internal_counts.get("risk_cards", 0)}
- old internal Evidence rows: {internal_counts.get("risk_card_evidence", 0)}
- uses M1 manufacturer_worklist_candidates as main scope: true
- detector evidence generation: aggregated by selected candidate, not row-level full dump
- max cards per entity observed: {int(cards_per_entity) if pd.notna(cards_per_entity) else 0}
- max business-visible evidence per card observed: {int(evidence_per_card) if pd.notna(evidence_per_card) else 0}
- index payload TopN: 8
- frontend default allowed: true
- internal full dump frontend default allowed: false
- auto_dispatch_allowed: false
"""


def build_manifest(batch_id: str, report_month: str, tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    entities = tables["risk_entities"]
    horizons = sorted(set(entities["primary_horizon"].dropna().astype(str)))
    manifest = ResultBatchManifest(
        batch_id=batch_id,
        report_type="monthly",
        report_month=report_month,
        report_date=pd.Timestamp.today().date().isoformat(),
        score_cutoff_month=report_month,
        primary_horizon="H12" if "H12" in horizons else (horizons[-1] if horizons else ""),
        available_horizons=horizons,
        schema_version="mvc_model_package_v1",
        data_backend="parquet",
        generated_at=pd.Timestamp.now().isoformat(),
        source_m_closure_batch="entity_complete_v2_m_module_closure",
        allowed_usage=["business_review_monthly_report", "analyst_view", "internal_diagnostic"],
        forbidden_usage=["auto_dispatch", "formal_customer_probability_service", "definitive_churn_claim"],
        customer_facing_probability_service_allowed=False,
        auto_dispatch_allowed=False,
        proof_case_report_allowed=False,
        export_ready=True,
        export_formats_supported=["html", "markdown", "csv_bundle", "future_pdf", "future_xlsx"],
        caveats=["selected subset coverage, not full SQL universe", "probability display must follow gate", "one-shot is separate from recurring churn", "business priority is not probability"],
    )
    return manifest.to_dict()


def detector_readiness_matrix() -> pd.DataFrame:
    rows = [
        ("interval", "terminal_loss_warning", "implemented_rule", "business_visible", True, False, False, "recent purchase absence evidence", "not probability", "definitive churn claim", "近期未观察到采购记录，需确认是否仍在正常采购周期内。"),
        ("interval", "purchase_interval_overdue_warning", "implemented_rule", "business_visible", True, False, False, "interval evidence available", "not probability", "definitive churn claim", "采购间隔偏离历史常规节奏，建议人工复核。"),
        ("frequency", "purchase_frequency_fluctuation_warning", "implemented_rule", "business_visible", True, True, False, "frequency drop evidence available", "not probability", "causal claim", "近期采购频次低于过往水平，建议继续跟踪。"),
        ("quantity", "purchase_quantity_fluctuation_warning", "partial_if_fields_reliable", "manager_visible", True, False, False, "quantity fields need reliability guardrail", "low confidence", "causal claim", "近期采购数量变化较大，需结合业务背景复核。"),
        ("new_terminal", "new_terminal_detection", "fact_available", "business_visible", True, False, False, "new purchase relationship fact", "not one-shot repeat probability", "recurring churn claim", "新进终端事实记录，仅作为关注对象。"),
        ("price", "low_price_purchase_warning", "interface_only", "disabled", False, False, False, "price comparability not validated", "do not display", "price caused churn", "暂不展示。"),
        ("price", "order_price_spread_warning", "interface_only", "disabled", False, False, False, "price comparability not validated", "do not display", "price caused churn", "暂不展示。"),
        ("delivery", "delayed_response_warning", "deferred", "disabled", False, False, False, "delivery_time/arrival_time missingness too high", "delivery time analysis skipped", "distributor responsibility", "配送响应证据不足，暂不启用。"),
        ("delivery", "rejection_response_warning", "deferred", "disabled", False, False, False, "response fields insufficient", "do not display", "distributor responsibility", "暂不展示。"),
        ("delivery", "low_delivery_rate_warning", "weak_interface_only", "disabled", False, False, False, "can only be weak evidence if fields pass quality guardrail", "do not attribute responsibility", "distributor responsibility", "配送相关证据未达到正式预警条件。"),
        ("portfolio", "sku_narrowing_warning", "deferred", "disabled", False, False, False, "requires product-line/portfolio mapping", "do not display", "competitor replacement", "暂不展示。"),
        ("portfolio", "wallet_share_decline_warning", "deferred", "disabled", False, False, False, "requires product-line/portfolio mapping", "do not display", "market share claim", "暂不展示。"),
        ("amount", "purchase_amount_trend_warning", "deferred", "disabled", False, False, False, "amount semantics are sensitive/relative", "do not display", "amount caused churn", "暂不展示。"),
    ]
    return pd.DataFrame(rows, columns=["detector_family", "detector_name", "implementation_status", "frontend_status", "can_show_on_clue_detail", "can_show_on_dashboard", "can_show_on_distributor_page", "reason", "caveat", "forbidden_claims", "recommended_display_text"])


def render_detector_report(matrix: pd.DataFrame) -> str:
    return f"""# Detector Completion for Frontend

- detector completion: not complete.
- current reliable frontend evidence is limited to selected rule-based detectors.
- delivery time detector skipped: true, because delivery/arrival/response time fields are not reliable enough for response-time analysis.
- distributor page status: disabled/reserved; do not claim distributor responsibility.
- detector severity/confidence are evidence descriptors, not probabilities.

{matrix.to_markdown(index=False)}
"""


def frontend_text_findings(workspace: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for rel in FRONTEND_FILES:
        path = workspace / rel
        if not path.exists():
            continue
        text = read_text(path)
        for line_no, line in enumerate(text.splitlines(), start=1):
            for pattern in TEXT_SAFETY_PATTERNS:
                if pattern in line:
                    rows.append({"page": path.name, "path": rel, "line": line_no, "current_text": trim_html(line), "risk_type": pattern, "suggested_replacement": replacement_for(pattern), "reason": "customer-facing pages need safe business wording", "must_replace_before_customer_demo": True})
    return pd.DataFrame(rows)


def render_frontend_text_audit(findings: pd.DataFrame) -> str:
    return f"""# Frontend Text Safety Audit

- read-only frontend audit findings: {len(findings)}
- action: replacement suggestions generated only; no front_end files modified.
- payloads generated by mvc_model_package are scanned separately and exclude forbidden claims/internal model terms.
"""


def replacement_for(pattern: str) -> str:
    if "竞品" in pattern:
        return "建议业务人员核查是否存在采购计划、院内需求或替代风险变化。"
    if "配送" in pattern:
        return "配送相关证据未达到正式结论条件，建议进一步核查。"
    if pattern in {"FDR", "MK显著", "MK检验", "Theil-Sen", "CUSUM", "L3", "AUC", "ECE", "XGBoost"}:
        return "使用采购节奏、频次或历史不足等业务可理解描述。"
    if "挽回" in pattern or "兑现率" in pattern or "ROI" in pattern or "已挽回" in pattern:
        return "当前未接入真实工单反馈，暂不展示兑现相关指标。"
    if "流失" in pattern:
        return "当前仅作为风险复核线索，不代表最终业务结论。"
    return "使用安全、可复核的业务描述。"


def api_contract() -> pd.DataFrame:
    endpoints = [
        ("index.html", "GET /api/workbench/overview", "index_payload.json", ["hero", "top_clues"]),
        ("clues.html", "GET /api/risk/entities", "risk_entities.parquet", ["risk_entity_id", "hospital_display_name", "risk_level", "palive_display"]),
        ("clue-detail.html", "GET /api/risk/entities/{risk_entity_id}", "risk_entities.parquet", ["risk_entity_id", "main_reason_summary"]),
        ("clue-detail.html", "GET /api/risk/entities/{risk_entity_id}/cards", "risk_cards.parquet", ["risk_card_id", "card_title"]),
        ("clue-detail.html", "GET /api/risk/cards/{risk_card_id}/evidence", "risk_card_evidence.parquet", ["evidence_id", "evidence_text"]),
        ("watchlist.html", "GET /api/watchlist", "watchlist_payload.json", ["items"]),
        ("dashboard.html", "GET /api/dashboard/monthly", "dashboard_payload.json", ["kpi_cards"]),
        ("backtest.html", "GET /api/proof-cases", "proof_cases.parquet", ["proof_case_report_allowed"]),
        ("verify.html", "GET /api/verify", "verify_payload.json", ["verification_enabled"]),
        ("distributor.html", "GET /api/distributor-alerts", "distributor_payload.json", ["delivery_detector_enabled"]),
        ("order-detail.html", "GET /api/orders/{order_id}", "order_detail_sample_payload.json", ["items"]),
        ("daily-reports", "GET /api/daily-reports", "daily_reports.parquet", ["daily_report_id", "report_type"]),
    ]
    rows = []
    for page, api_name, source, fields in endpoints:
        for field in fields:
            rows.append({"page": page, "api_name": api_name, "field_name": field, "type": "string/json", "required": True, "source_table": source, "source_column": field, "customer_visible": page not in {"algo-config.html", "algo-health.html"}, "analyst_visible": True, "internal_only": False, "caveat": "probability gate applies" if "palive" in field else "", "forbidden_interpretation": "not a definitive churn or causal claim"})
    return pd.DataFrame(rows)


def field_mapping() -> pd.DataFrame:
    rows = [
        ("clues.html", "table", "医院名称", "M1/M5", "risk_entities", "hospital_code", "display code fallback", "hospital_display_name", "no master data name table", False, "hospital_code"),
        ("clues.html", "table", "产品线", "M1/M5", "risk_entities", "drug_group", "drug_group used as product-line compatible field", "product_line_display_name", "drug_group_source=drug_code", False, "drug_group"),
        ("clues.html", "table", "P(alive)", "gate", "risk_entities", "churn_probability_H", "1 - churn probability only when gate allows exact display", "palive_display", "UI compatibility field only", False, "不展示"),
        ("clue-detail.html", "evidence", "证据链", "M4/M7", "risk_card_evidence", "evidence_text", "business copy renderer", "business_visible only", "no causal conclusion", False, "无可展示证据"),
        ("watchlist.html", "table", "观察天数", "M6", "risk_entity_timeline", "month", "not available in current artifact", "null", "M6 interface-only", True, "unavailable"),
        ("dashboard.html", "KPI", "兑现率", "feedback", "dashboard_payload", "verification_rate", "feedback not connected", "待接入工单反馈", "do not fabricate recovery", True, "待接入工单反馈"),
    ]
    return pd.DataFrame(rows, columns=["frontend_page", "frontend_component_or_area", "frontend_field", "source_m_module", "source_table", "source_column", "transformation_rule", "display_rule", "caveat", "missing_flag", "fallback_display"])


def render_export_contract(export_manifest: dict[str, Any]) -> str:
    return f"""# Report Export Contract

- current output: structured result batch and HTML/Markdown-ready payloads.
- formal PDF generated: false.
- PDF/XLSX export belongs to backend/frontend distribution layer, not algorithm training layer.
- export status: {export_manifest["export_status"]}

```json
{json.dumps(export_manifest, ensure_ascii=False, indent=2)}
```
"""


def render_model_design(api: pd.DataFrame, mapping: pd.DataFrame, design_path: Path) -> str:
    return f"""# MVC Model Package Design

- `algo_main` remains an algorithm exploration and batch-production workspace.
- `mvc_model_package` is the candidate domain/model layer for later migration to backend `project/app/domain` or `project/app/models`.
- Current package does not train, tune, extract SQL, or clean data.
- Current package reads M-closure outputs and emits RiskEntity/RiskCard/Evidence/DailyReport result batches.
- Frontend should consume API/repository outputs, not raw M closure tables.
- ClickHouse can replace `ParquetRiskResultRepository` through the repository interface.
- design file read-only: {design_path if design_path.exists() else "missing"}

## API Contract
{api.to_markdown(index=False)}

## Field Mapping
{mapping.to_markdown(index=False)}
"""


def render_summary(batch_dir: Path, tables: dict[str, pd.DataFrame], unsafe: pd.DataFrame) -> str:
    return f"""# MVC Model Package Summary

- batch directory: {batch_dir}
- risk_entities rows: {len(tables["risk_entities"])}
- risk_cards rows: {len(tables["risk_cards"])}
- risk_card_evidence rows: {len(tables["risk_card_evidence"])}
- daily_reports rows: {len(tables["daily_reports"])}
- proof_case_report_allowed: false
- customer_facing_probability_service: false
- auto_dispatch_allowed: false
- frontend text findings: {len(unsafe)}
- formal PDF generated: false
"""


def workspace_root(root: Path) -> Path:
    if (root / "front_end").exists():
        return root
    if root.name == "algo_main" and (root.parent / "front_end").exists():
        return root.parent
    return root


def read_text(path: Path) -> str:
    for enc in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def trim_html(line: str) -> str:
    text = re.sub(r"<[^>]+>", " ", line)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:300]


def write_csv(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")
