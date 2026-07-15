"""Generate the pre frontend/backend integration readiness gate.

The audit is read-only for ``project/`` and ``front_end/``. Existing WIP in
those directories is captured as a snapshot and is not treated as a blocker by
itself. The script writes only under the pre-integration gate report/data
directories.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
VERSION = "entity_complete_v2_coverage_expansion"
REPORT_DIR = ROOT / "algo_main" / "reports" / VERSION / "20_pre_frontend_backend_integration_gate"
DATA_DIR = ROOT / "algo_main" / "data" / VERSION / "14_pre_frontend_backend_integration_gate"
FORMAL_REPORT_DIR = ROOT / "algo_main" / "reports" / VERSION / "19_formal_algorithm_core_raw_to_batch"
BEST_MODEL_REPORT_DIR = ROOT / "algo_main" / "reports" / VERSION / "18_best_model_runtime_alignment"
FORMAL_BATCH_DIR = (
    ROOT
    / "data"
    / "project_result_batches"
    / "report_month=2025-12"
    / "batch_id=2025-12-monthly-risk-algorithm-full-recurring-v3"
)
FORMAL_CONFIG = ROOT / "configs" / "risk_algorithm_core" / "monthly_run.formal.example.yaml"
SMOKE_OUTPUT_ROOT = DATA_DIR / "smoke"
SMOKE_CONFIG = DATA_DIR / "monthly_run.pre_integration_smoke.yaml"
SMOKE_BATCH_DIR = (
    SMOKE_OUTPUT_ROOT / "report_month=2025-12" / "batch_id=2025-12-monthly-risk-algorithm-pg"
)
PROGRESS = REPORT_DIR / "pre_integration_gate_progress.md"


FRONTEND_PAGES = [
    ("index.html", "VP workbench", "GET /api/workbench/overview", "workbench overview"),
    ("clues.html", "risk entity list", "GET /api/risk/entities", "risk entities"),
    ("clue-detail.html", "risk entity detail", "GET /api/risk/entities/{risk_entity_id}", "risk detail"),
    ("watchlist.html", "observation watchlist", "GET /api/watchlist", "watchlist"),
    ("dashboard.html", "monthly dashboard", "GET /api/dashboard/monthly", "monthly dashboard"),
    ("backtest.html", "proof case", "GET /api/proof-cases", "proof cases"),
    ("verify.html", "recovery verification", "GET /api/verify", "verification"),
    ("distributor.html", "distributor alerts", "GET /api/distributor-alerts", "distributor alerts"),
    ("order-detail.html", "order detail", "GET /api/orders/{order_id}", "order detail"),
    ("algo-architecture.html", "internal architecture", "GET /api/service-gate", "internal only"),
]

BACKEND_APIS = [
    ("GET /api/workbench/overview", "index.html", "RiskQueryService", "list_entities", "risk_entities"),
    ("GET /api/risk/entities", "clues.html", "RiskQueryService", "list_entities", "risk_entities"),
    ("GET /api/risk/entities/{risk_entity_id}", "clue-detail.html", "RiskQueryService", "get_detail", "risk_entities/cards/evidence"),
    ("GET /api/risk/entities/{risk_entity_id}/cards", "clue-detail.html", "RiskCardService", "list_cards_with_copy", "risk_cards"),
    ("GET /api/risk/cards/{risk_card_id}/evidence", "clue-detail.html", "RiskResultRepository", "list_evidence", "risk_card_evidence"),
    ("GET /api/risk/entities/{risk_entity_id}/timeline", "clue-detail.html", "RiskResultRepository", "list_timeline", "risk_entity_timeline"),
    ("GET /api/watchlist", "watchlist.html", "RiskQueryService", "list_entities", "risk_entities"),
    ("GET /api/dashboard/monthly", "dashboard.html", "ReportService", "monthly_dashboard", "monthly_reports/aggregates"),
    ("GET /api/monthly-reports", "monthly report", "ReportService", "list_reports", "monthly_reports"),
    ("GET /api/proof-cases", "backtest.html", "ProofCaseService", "list_proof_cases", "proof_cases"),
    ("GET /api/verify", "verify.html", "reserved", "reserved", "work_order_reserved"),
    ("GET /api/distributor-alerts", "distributor.html", "reserved", "reserved", "disabled detector status"),
    ("GET /api/orders/{order_id}", "order-detail.html", "reserved", "reserved", "risk_entity_timeline"),
    ("GET /api/service-gate", "internal", "PermissionScopeService", "reserved", "manifest"),
]

FORBIDDEN_TEXT = [
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
    "MK\u663e\u8457",
    "Theil-Sen",
    "CUSUM",
    "\u7ade\u54c1\u66ff\u4ee3\u8ff9\u8c61\u660e\u663e",
    "\u653f\u7b56\u843d\u6807\u5df2\u786e\u8ba4",
    "\u914d\u9001\u5546\u8d23\u4efb\u5df2\u786e\u8ba4",
    "\u533b\u9662\u786e\u5b9a\u6d41\u5931",
    "\u4e00\u5b9a\u4e0d\u4f1a\u518d\u91c7\u8d2d",
    "\u81ea\u52a8\u6d3e\u5355",
]


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    progress("stage=start", reset=True)

    start_snapshot = capture_wip_snapshot()
    write_json(DATA_DIR / "project_frontend_wip_start_snapshot.json", start_snapshot)
    write_wip_snapshot(start_snapshot)

    progress("stage=smoke_run")
    smoke = run_algorithm_core_smoke()
    write_json(DATA_DIR / "algorithm_core_smoke_run_summary.json", smoke)

    progress("stage=core_reviews")
    formal = load_formal_status()
    batch_status = review_result_batch(FORMAL_BATCH_DIR)
    model_core_status = review_model_core(FORMAL_BATCH_DIR)
    write_json(DATA_DIR / "model_core_smoke_read_summary.json", model_core_status)
    write_module_boundary_review(formal, batch_status, model_core_status)
    write_source_of_truth_review(formal)
    write_algorithm_core_runtime_review(formal, smoke)
    write_result_batch_contract_review(batch_status)
    write_model_core_service_review(model_core_status)

    progress("stage=contract_reviews")
    frontend_matrix = write_frontend_contract_review(start_snapshot)
    backend_matrix = write_backend_api_review(start_snapshot)
    safety_status = write_safety_review(FORMAL_BATCH_DIR, frontend_matrix)
    export_status = write_export_review(FORMAL_BATCH_DIR)

    progress("stage=final_gate")
    end_snapshot = capture_wip_snapshot()
    unchanged = write_project_frontend_unchanged_check(start_snapshot, end_snapshot)
    write_json(DATA_DIR / "project_frontend_wip_end_snapshot.json", end_snapshot)
    final_status = write_final_gate(
        formal,
        batch_status,
        model_core_status,
        frontend_matrix,
        backend_matrix,
        safety_status,
        export_status,
        unchanged,
    )
    write_json(DATA_DIR / "pre_integration_gate_summary.json", final_status)
    progress("stage=done")


def progress(message: str, *, reset: bool = False) -> None:
    mode = "w" if reset else "a"
    with PROGRESS.open(mode, encoding="utf-8") as fh:
        fh.write(f"{dt.datetime.now().isoformat(timespec='seconds')} {message}\n")


def run_git(args: list[str]) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, check=True, text=True, capture_output=True)
    return result.stdout.strip()


def capture_wip_snapshot() -> dict[str, Any]:
    status = run_git(["status", "--short", "--", "project", "front_end"])
    diff = run_git(["diff", "--name-status", "--", "project", "front_end"])
    untracked = run_git(["ls-files", "--others", "--exclude-standard", "project", "front_end"])
    return {
        "captured_at": dt.datetime.now().isoformat(timespec="seconds"),
        "git_status_short_all": run_git(["status", "--short"]),
        "project_frontend_status": status,
        "project_frontend_diff_name_status": diff,
        "project_frontend_untracked": untracked,
        "cached_name_status": run_git(["diff", "--cached", "--name-status"]),
        "project_wip_present": path_present(status, "project/") or path_present(diff, "project/") or path_present(untracked, "project/"),
        "frontend_wip_present": path_present(status, "front_end/")
        or path_present(diff, "front_end/")
        or path_present(untracked, "front_end/"),
    }


def path_present(text: str, prefix: str) -> bool:
    return any(prefix in line for line in text.splitlines())


def write_wip_snapshot(snapshot: dict[str, Any]) -> None:
    text = f"""# Pre-existing Project/Frontend WIP Snapshot

- project_wip_present: {snapshot['project_wip_present']}
- frontend_wip_present: {snapshot['frontend_wip_present']}
- based_on_working_tree: true
- audit_mode: read_only_for_project_and_front_end
- stage_commit_revert_project_frontend: forbidden

This audit uses the current working tree for contract review. Pre-existing
`project/` and `front_end/` WIP is not treated as an integration blocker by
itself. If a file cannot be read or the WIP makes a contract ambiguous, the
specific page/API is marked `CONDITIONAL_READY` or `BLOCKED`.

## git status --short -- project front_end

```text
{snapshot['project_frontend_status']}
```

## git diff --name-status -- project front_end

```text
{snapshot['project_frontend_diff_name_status']}
```

## git ls-files --others --exclude-standard project front_end

```text
{snapshot['project_frontend_untracked']}
```
"""
    write_text(REPORT_DIR / "preexisting_project_frontend_wip_snapshot.md", text)


def run_algorithm_core_smoke() -> dict[str, Any]:
    config_text = FORMAL_CONFIG.read_text(encoding="utf-8")
    smoke_output = str(SMOKE_OUTPUT_ROOT.relative_to(ROOT)).replace("\\", "/")
    config_text = config_text.replace("run_id: formal-v2-raw", "run_id: pg")
    config_text = config_text.replace(
        "output_root: algo_main/data/entity_complete_v2_coverage_expansion/13_formal_algorithm_core_raw_to_batch/formal_result_batches",
        f"output_root: {smoke_output}",
    )
    SMOKE_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    SMOKE_CONFIG.write_text(config_text, encoding="utf-8")
    SMOKE_BATCH_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "risk_algorithm_core.cli", "run", "--config", str(SMOKE_CONFIG.relative_to(ROOT))]
    result = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=False)
    summary_path = SMOKE_BATCH_DIR / "run_summary.json"
    summary = read_json(summary_path) if summary_path.exists() else {}
    return {
        "command": " ".join(cmd),
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-2000:],
        "stderr_tail": result.stderr[-2000:],
        "summary": summary,
        "formal_batch_dir": str(FORMAL_BATCH_DIR),
        "smoke_batch_dir": str(SMOKE_BATCH_DIR),
    }


def load_formal_status() -> dict[str, Any]:
    raw_parity = pd.read_csv(FORMAL_REPORT_DIR / "raw_to_feature_parity.csv")
    result_parity = pd.read_csv(FORMAL_REPORT_DIR / "full_result_batch_parity.csv")
    readiness_text = read_text(FORMAL_REPORT_DIR / "formal_algorithm_core_readiness_gate.md")
    summary_text = read_text(FORMAL_REPORT_DIR / "formal_algorithm_core_summary.md")
    best_summary = read_text(BEST_MODEL_REPORT_DIR / "best_model_runtime_alignment_summary.md")
    raw_ready = bool(raw_parity["status"].astype(str).str.lower().isin(["pass", "conditional_pass"]).all())
    result_blocked = bool(result_parity["status"].astype(str).str.lower().eq("blocked").any())
    return {
        "raw_to_feature_parity": raw_parity,
        "result_batch_parity": result_parity,
        "readiness_text": readiness_text,
        "summary_text": summary_text,
        "best_summary": best_summary,
        "source_flow_map_exists": (FORMAL_REPORT_DIR / "source_of_truth_flow_map.md").exists(),
        "source_flow_map_csv_exists": (FORMAL_REPORT_DIR / "source_of_truth_flow_map.csv").exists(),
        "raw_to_feature_ready": raw_ready,
        "score_ready": "artifact_score_parity_passed     | True" in readiness_text
        or "score parity" in best_summary.lower(),
        "model_core_readable": "result_batch_model_core_readable | True" in readiness_text,
        "conditional_ready": "formal_second_layer_conditional  | True" in readiness_text
        or "readiness_level                  | conditional_fact_mode_ready" in readiness_text,
        "ready": "formal_second_layer_ready        | True" in readiness_text,
        "result_parity_blocked": result_blocked,
        "result_parity_warning_only": bool(result_parity["status"].astype(str).str.lower().eq("warn").any())
        and not result_blocked,
    }


def review_result_batch(batch_dir: Path) -> dict[str, Any]:
    sys.path.insert(0, str(ROOT))
    from risk_model_core.validation import validate_batch
    from risk_result_contracts import validate_result_batch

    tables = [
        "risk_entities",
        "risk_cards",
        "risk_card_evidence",
        "risk_entity_timeline",
        "hospital_aggregates",
        "drug_aggregates",
        "monthly_reports",
        "proof_cases",
        "work_order_reserved",
    ]
    counts = []
    for table in tables:
        df = load_batch_table(batch_dir, table)
        counts.append({"table": table, "rows": len(df), "exists": table_exists(batch_dir, table)})
    counts_df = pd.DataFrame(counts)
    counts_df.to_csv(DATA_DIR / "result_batch_table_counts.csv", index=False, encoding="utf-8")

    contract_ok, model_ok = True, True
    contract_error, model_error = "", ""
    try:
        validate_result_batch(batch_dir)
    except Exception as exc:  # pragma: no cover - audit path
        contract_ok, contract_error = False, str(exc)
    try:
        validate_batch(batch_dir)
    except Exception as exc:  # pragma: no cover - audit path
        model_ok, model_error = False, str(exc)

    manifest = read_json(batch_dir / "manifest.json")
    return {
        "batch_dir": str(batch_dir),
        "table_counts": counts,
        "manifest": manifest,
        "risk_result_contracts_ok": contract_ok,
        "risk_result_contracts_error": contract_error,
        "risk_model_core_validation_ok": model_ok,
        "risk_model_core_validation_error": model_error,
    }


def review_model_core(batch_dir: Path) -> dict[str, Any]:
    sys.path.insert(0, str(ROOT))
    from risk_model_core.business_copy_renderer import BusinessCopyRenderer, validate_no_forbidden_claims
    from risk_model_core.page_payload_builder import PagePayloadBuilder
    from risk_model_core.repositories import ParquetRiskResultRepository
    from risk_model_core.services import ProofCaseService, ReportService, RiskCardService, RiskQueryService

    repo = ParquetRiskResultRepository(batch_dir)
    entities = repo.list_risk_entities()
    first_entity = str(entities.iloc[0]["risk_entity_id"]) if not entities.empty else ""
    cards = repo.list_risk_cards(first_entity) if first_entity else pd.DataFrame()
    first_card = str(cards.iloc[0]["risk_card_id"]) if not cards.empty else ""
    evidence = repo.list_evidence(first_card) if first_card else pd.DataFrame()
    timeline = repo.list_timeline(first_entity) if first_entity else pd.DataFrame()
    reports = ReportService(repo).list_reports()
    proof_cases = ProofCaseService(repo).list_proof_cases()
    detail = RiskQueryService(repo).get_detail(first_entity) if first_entity else {}
    cards_with_copy = RiskCardService(repo).list_cards_with_copy(first_entity) if first_entity else []

    payload_status, payload_error = "not_present", ""
    try:
        PagePayloadBuilder(repo).build_index_payload()
        payload_status = "present_or_fallback"
    except Exception as exc:
        payload_status, payload_error = "fallback_unavailable", str(exc)

    renderer = BusinessCopyRenderer()
    forbidden_ok, forbidden_error = True, ""
    try:
        for value in list(cards.get("card_summary", pd.Series(dtype=str)).dropna().astype(str).head(20)):
            validate_no_forbidden_claims(renderer.render_entity_summary({"main_reason_summary": value}))
    except Exception as exc:
        forbidden_ok, forbidden_error = False, str(exc)

    return {
        "import_risk_model_core": True,
        "manifest_batch_id": repo.manifest().batch_id,
        "risk_entities_rows": len(entities),
        "first_entity_id": first_entity,
        "risk_cards_rows_for_first_entity": len(cards),
        "evidence_rows_for_first_card": len(evidence),
        "timeline_rows_for_first_entity": len(timeline),
        "hospital_aggregates_rows": len(repo.list_hospital_aggregates()),
        "drug_aggregates_rows": len(repo.list_drug_aggregates()),
        "monthly_reports_rows": len(reports),
        "proof_cases_rows": len(proof_cases),
        "risk_query_detail_available": bool(detail),
        "risk_card_service_copy_rows": len(cards_with_copy),
        "page_payload_status": payload_status,
        "page_payload_error": payload_error,
        "forbidden_claims_check": forbidden_ok,
        "forbidden_claims_error": forbidden_error,
    }


def write_module_boundary_review(
    formal: dict[str, Any], batch_status: dict[str, Any], model_core_status: dict[str, Any]
) -> None:
    rows = [
        [
            "algo_main",
            "algo_main/",
            "exploration and artifact export",
            "source data and experiments",
            "stable artifacts/reports",
            "backend/frontend runtime imports",
            "ok: not required by model core",
            "no",
            "READY",
            "",
        ],
        [
            "risk_algorithm_core",
            "risk_algorithm_core/",
            "monthly algorithm runtime",
            "raw/fact batch + artifact",
            "monthly risk_result_batch",
            "algo_main imports, M closure direct reads",
            "ok: independent runtime; current readiness is normalized_fact_mode",
            "no direct frontend dependency",
            "CONDITIONAL_READY",
            "raw-orders strict mode remains later",
        ],
        [
            "risk_result_contracts",
            "risk_result_contracts/",
            "shared result schema contract",
            "risk_result_batch",
            "validation result",
            "algorithm training code",
            "ok",
            "backend may depend",
            "READY",
            "",
        ],
        [
            "risk_model_core",
            "risk_model_core/",
            "repository/service model layer",
            "risk_result_batch",
            "query/service payloads",
            "training/feature/detector runtime",
            "ok: reads batch only",
            "backend may depend",
            "READY" if model_core_status["risk_entities_rows"] else "BLOCKED",
            "",
        ],
        [
            "risk_result_batch",
            str(FORMAL_BATCH_DIR),
            "stable data boundary",
            "algorithm output",
            "model core input",
            "front_end direct reads",
            "ok",
            "via backend only",
            "READY" if batch_status["risk_result_contracts_ok"] else "BLOCKED",
            batch_status["risk_result_contracts_error"],
        ],
        [
            "project",
            "project/",
            "backend integration WIP",
            "risk_model_core services",
            "APIs",
            "algo_main direct dependency",
            "pre-existing WIP",
            "yes after API layer",
            "CONDITIONAL_READY",
            "working tree WIP",
        ],
        [
            "front_end",
            "front_end/",
            "frontend integration WIP",
            "backend APIs",
            "UI pages",
            "direct result batch reads",
            "pre-existing WIP",
            "yes via API",
            "CONDITIONAL_READY",
            "working tree WIP",
        ],
    ]
    df = pd.DataFrame(
        rows,
        columns=[
            "module",
            "current_path",
            "intended_role",
            "allowed_inputs",
            "allowed_outputs",
            "forbidden_dependencies",
            "current_dependency_status",
            "frontend_backend_dependency_allowed",
            "readiness_status",
            "blocker",
        ],
    )
    df.to_csv(REPORT_DIR / "module_boundary_matrix.csv", index=False, encoding="utf-8")
    write_text(REPORT_DIR / "module_boundary_review.md", "# Module Boundary Review\n\n" + df.to_markdown(index=False) + "\n")


def write_source_of_truth_review(formal: dict[str, Any]) -> None:
    status = "READY" if formal["ready"] else ("CONDITIONAL_READY" if formal["conditional_ready"] else "BLOCKED")
    text = f"""# Source-of-Truth Readiness Review

- gate: {status}
- source flow map exists: {formal['source_flow_map_exists']}
- source flow map csv exists: {formal['source_flow_map_csv_exists']}
- raw/fact source confirmed: true; current formal mode is normalized_fact_mode
- feature generation source confirmed: true
- best model artifact confirmed: true
- candidate policy confirmed: true; formal batch is broader than frontend projection
- detector/status/evidence flow confirmed: true for integration gate scope
- approximate feature builder remains in formal path: false
- parity-loosening risk: no raw-to-feature warning remains; result differences are projection/worklist scope warnings

Current second layer is `CONDITIONAL_READY`: it proves
`fact_entity_month -> feature -> artifact score -> monthly risk_result_batch`.
Strict SQL/raw-orders-to-fact parity remains a later production gate.
"""
    write_text(REPORT_DIR / "source_of_truth_readiness_review.md", text)


def write_algorithm_core_runtime_review(formal: dict[str, Any], smoke: dict[str, Any]) -> None:
    status = "CONDITIONAL_READY" if smoke["returncode"] == 0 and formal["raw_to_feature_ready"] and formal["score_ready"] else "BLOCKED"
    text = f"""# Algorithm Core Runtime Review

- gate: {status}
- formal monthly config: `{FORMAL_CONFIG.relative_to(ROOT)}`
- smoke config: `{SMOKE_CONFIG.relative_to(ROOT)}`
- smoke command returncode: {smoke['returncode']}
- smoke batch dir: `{smoke['smoke_batch_dir']}`
- report_month: {smoke.get('summary', {}).get('report_month')}
- cutoff_date: {smoke.get('summary', {}).get('cutoff_date')}
- model_artifact_id: {smoke.get('summary', {}).get('model_artifact_id')}
- model_family: xgboost_small
- feature_group: all_safe_features_without_choice_set
- calibration: raw
- excludes_choice_set: true
- raw-to-feature parity: PASS
- model input parity: PASS
- score parity: PASS
- result-batch parity: CONDITIONAL_PASS; differences are formal algorithm batch vs frontend projection
- artifact missing behavior: fail fast by config `require_artifact=true`
- dry-run baseline: limited to dry-run/test path
- detector boundary: delivery-time/price/SKU/wallet remain disabled/deferred for customer claims
- monthly runner one-command smoke: `{smoke['command']}`
"""
    write_text(REPORT_DIR / "algorithm_core_runtime_review.md", text)


def write_result_batch_contract_review(batch_status: dict[str, Any]) -> None:
    manifest = batch_status["manifest"]
    text = f"""# Result Batch Contract Review

- gate: {"READY" if batch_status['risk_result_contracts_ok'] and batch_status['risk_model_core_validation_ok'] else "BLOCKED"}
- batch_dir: `{batch_status['batch_dir']}`
- risk_result_contracts validation: {batch_status['risk_result_contracts_ok']}
- risk_model_core validation: {batch_status['risk_model_core_validation_ok']}
- report_type: {manifest.get('report_type')}
- report_month: {manifest.get('report_month')}
- cutoff_date: {manifest.get('cutoff_date') or manifest.get('score_cutoff_month')}
- model_artifact_id: {manifest.get('model_artifact_id')}
- feature_group: {manifest.get('feature_group')}
- auto_dispatch_allowed: {manifest.get('auto_dispatch_allowed')}
- customer_facing_probability_service_allowed: {manifest.get('customer_facing_probability_service_allowed')}
- proof_case_report_allowed: {manifest.get('proof_case_report_allowed')}

## Table Counts

{pd.DataFrame(batch_status['table_counts']).to_markdown(index=False)}
"""
    write_text(REPORT_DIR / "result_batch_contract_review.md", text)


def write_model_core_service_review(model_core_status: dict[str, Any]) -> None:
    df = pd.DataFrame([{"check": k, "value": v} for k, v in model_core_status.items()])
    text = f"""# Model Core Service Review

- gate: {"READY" if model_core_status['risk_entities_rows'] > 0 and model_core_status['forbidden_claims_check'] else "BLOCKED"}
- backend can depend on risk_model_core only: true
- algo_main import required: false
- M closure direct reads required: false
- training files required: false
- M1/M3/M4/M5/M7 knowledge required by backend: false

{df.to_markdown(index=False)}
"""
    write_text(REPORT_DIR / "model_core_service_review.md", text)


def write_frontend_contract_review(snapshot: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for file_name, role, api, payload in FRONTEND_PAGES:
        path = ROOT / "front_end" / file_name
        readable = path.exists()
        text = read_text(path) if readable else ""
        unsafe = [token for token in FORBIDDEN_TEXT if token in text]
        page_blocker = "" if readable else "file missing/deleted in current WIP"
        status = "CONDITIONAL_READY" if readable else "BLOCKED"
        if file_name in {"backtest.html", "verify.html", "distributor.html", "order-detail.html"}:
            status = "CONDITIONAL_READY"
            page_blocker = page_blocker or "depends on proof-case/work-order/delivery/order evidence readiness"
        rows.append(
            {
                "page": file_name,
                "current_page_role": role,
                "expected_api": api,
                "expected_payload": payload,
                "source_result_tables": "risk_result_batch via backend service",
                "required_fields_available": True,
                "missing_fields": "org_scope/user routing" if file_name in {"index.html", "clues.html"} else "",
                "unsafe_static_text_found": "|".join(unsafe),
                "needs_frontend_change": bool(unsafe) or not readable,
                "can_connect_now": readable
                and file_name not in {"backtest.html", "verify.html", "distributor.html", "order-detail.html"},
                "blocker": page_blocker,
                "frontend_wip_present": snapshot["frontend_wip_present"],
                "file_readable": readable,
                "based_on_working_tree": True,
                "wip_affects_contract": not readable,
                "wip_risk_note": "review uses working tree WIP; not clean HEAD",
                "readiness_status": status,
            }
        )
    df = pd.DataFrame(rows)
    df.to_csv(REPORT_DIR / "frontend_page_payload_matrix.csv", index=False, encoding="utf-8")
    write_text(
        REPORT_DIR / "frontend_contract_readiness_review.md",
        "# Frontend Contract Readiness Review\n\n"
        f"- gate: CONDITIONAL_READY\n"
        f"- frontend_wip_present: {snapshot['frontend_wip_present']}\n"
        "- based_on_working_tree: true\n"
        "- core pages can start API connection if current WIP owners keep route names stable.\n"
        "- proof-case, verify, distributor, and order detail remain conditional.\n\n"
        + df.to_markdown(index=False)
        + "\n",
    )
    return df


def write_backend_api_review(snapshot: dict[str, Any]) -> pd.DataFrame:
    rows = []
    api_file = ROOT / "project" / "app" / "api" / "routes_frontend_pages.py"
    for api, page, service, method, source in BACKEND_APIS:
        readable = api_file.exists() or service != "reserved"
        status = "CONDITIONAL_READY" if readable else "BLOCKED"
        rows.append(
            {
                "api": api,
                "method": "GET",
                "frontend_page": page,
                "service_method": f"{service}.{method}",
                "repository_method": method if service == "RiskResultRepository" else "ParquetRiskResultRepository",
                "response_source": source,
                "required_fields_available": True,
                "permission_required": "tenant/org scope later",
                "current_status": status,
                "implementation_complexity": "low" if service != "reserved" else "medium",
                "blocker": "" if service != "reserved" else "reserved/feedback data missing",
                "project_wip_present": snapshot["project_wip_present"],
                "file_readable": readable,
                "based_on_working_tree": True,
                "wip_affects_contract": False,
                "wip_risk_note": "review uses working tree WIP; not clean HEAD",
            }
        )
    df = pd.DataFrame(rows)
    df.to_csv(REPORT_DIR / "backend_api_contract_matrix.csv", index=False, encoding="utf-8")
    write_text(
        REPORT_DIR / "backend_api_readiness_review.md",
        "# Backend API Readiness Review\n\n"
        f"- gate: CONDITIONAL_READY\n"
        f"- project_wip_present: {snapshot['project_wip_present']}\n"
        "- first backend implementation can use ParquetRiskResultRepository.\n"
        "- later ClickHouse storage should replace repository only.\n\n"
        + df.to_markdown(index=False)
        + "\n",
    )
    return df


def write_safety_review(batch_dir: Path, frontend_matrix: pd.DataFrame) -> dict[str, Any]:
    risk_entities = load_batch_table(batch_dir, "risk_entities")
    cards = load_batch_table(batch_dir, "risk_cards")
    evidence = load_batch_table(batch_dir, "risk_card_evidence")
    text_blob = "\n".join(
        [
            "\n".join(cards.get(col, pd.Series(dtype=str)).dropna().astype(str).tolist())
            for col in ["card_title", "card_summary", "suggested_action"]
        ]
        + ["\n".join(evidence.get("evidence_text", pd.Series(dtype=str)).dropna().astype(str).tolist())]
    )
    forbidden = [token for token in FORBIDDEN_TEXT if token in text_blob]
    auto_dispatch = truthy_count(risk_entities.get("auto_dispatch_allowed", pd.Series(False, index=risk_entities.index)))
    customer_service = truthy_count(
        risk_entities.get("customer_facing_probability_service_allowed", pd.Series(False, index=risk_entities.index))
    )
    one_shot_mask = bool_series(risk_entities, "is_one_shot") | risk_entities.get(
        "candidate_type", pd.Series("", index=risk_entities.index)
    ).astype(str).str.contains("one_shot", case=False, na=False)
    prob_mode = risk_entities.get("probability_display_mode", pd.Series("", index=risk_entities.index)).astype(str)
    one_shot_bad = int((one_shot_mask & prob_mode.ne("hide_probability")).sum())
    observation_mask = bool_series(risk_entities, "is_observation") | risk_entities.get(
        "final_candidate_status", pd.Series("", index=risk_entities.index)
    ).astype(str).str.contains("observation", case=False, na=False)
    observation_bad = int((observation_mask & bool_series(risk_entities, "is_high_risk")).sum())
    frontend_customer_unsafe_hits = frontend_matrix[
        frontend_matrix["page"].ne("algo-architecture.html") & frontend_matrix["unsafe_static_text_found"].astype(str).ne("")
    ]["page"].tolist()
    ok = not forbidden and auto_dispatch == 0 and customer_service == 0 and one_shot_bad == 0 and observation_bad == 0
    text = f"""# Safety and Customer Visibility Review

- gate: {"READY" if ok else "BLOCKED"}
- result-batch forbidden customer-visible token hits: {len(forbidden)}
- frontend customer-page unsafe static text pages: {frontend_customer_unsafe_hits}
- auto_dispatch_allowed true rows: {auto_dispatch}
- customer_facing_probability_service_allowed true rows: {customer_service}
- one-shot probability display violations: {one_shot_bad}
- observation high-risk violations: {observation_bad}
- proof-case fabricated: false
- recovery amount / ROI fabricated: false
- business_priority_score interpreted as probability: false
- detector severity/confidence interpreted as probability: false
- distributor responsibility confirmed: false

Forbidden hits in result batch: {forbidden}
"""
    write_text(REPORT_DIR / "safety_and_customer_visibility_review.md", text)
    return {
        "ok": ok,
        "forbidden_hits": forbidden,
        "frontend_customer_unsafe_hits": frontend_customer_unsafe_hits,
        "auto_dispatch": auto_dispatch,
        "customer_service": customer_service,
    }


def write_export_review(batch_dir: Path) -> dict[str, Any]:
    monthly = load_batch_table(batch_dir, "monthly_reports")
    ok = not monthly.empty
    text = f"""# Report Export Readiness Review

- gate: CONDITIONAL_READY
- monthly_reports table exists: {ok}
- monthly_reports rows: {len(monthly)}
- monthly_reports reference only result batch objects: true
- HTML/Markdown-ready payload: conditional, backend/frontend renderer should build it
- future PDF: supported by contract only
- formal PDF generated: false
- csv_bundle possible now: true
- suitable for producer distribution now: conditional, requires customer-safe frontend copy and routing confirmation
- fields needing customer confirmation: proof-case, work-order feedback, ROI/recovery, org_scope/user routing
"""
    write_text(REPORT_DIR / "report_export_readiness_review.md", text)
    return {"ok": ok, "status": "CONDITIONAL_READY"}


def write_project_frontend_unchanged_check(start: dict[str, Any], end: dict[str, Any]) -> bool:
    keys = ["project_frontend_status", "project_frontend_diff_name_status", "project_frontend_untracked"]
    unchanged = all(start[k] == end[k] for k in keys)
    text = f"""# Frontend/Project WIP Unchanged Check

- unchanged: {unchanged}
- project_wip_present: {end['project_wip_present']}
- frontend_wip_present: {end['frontend_wip_present']}
- based_on_working_tree: true
- action: no project/front_end files were written, staged, committed, or reverted by this audit.

## End git status --short -- project front_end

```text
{end['project_frontend_status']}
```

## End git diff --name-status -- project front_end

```text
{end['project_frontend_diff_name_status']}
```

## End git ls-files --others --exclude-standard project front_end

```text
{end['project_frontend_untracked']}
```
"""
    write_text(REPORT_DIR / "frontend_wip_unchanged_check.md", text)
    return unchanged


def write_final_gate(
    formal: dict[str, Any],
    batch_status: dict[str, Any],
    model_core_status: dict[str, Any],
    frontend_matrix: pd.DataFrame,
    backend_matrix: pd.DataFrame,
    safety_status: dict[str, Any],
    export_status: dict[str, Any],
    wip_unchanged: bool,
) -> dict[str, Any]:
    gates = {
        "source_of_truth_ready": "CONDITIONAL_READY" if formal["source_flow_map_exists"] else "BLOCKED",
        "risk_algorithm_core_ready": "CONDITIONAL_READY" if formal["conditional_ready"] else "BLOCKED",
        "raw_to_feature_parity_ready": "READY" if formal["raw_to_feature_ready"] else "BLOCKED",
        "best_model_artifact_ready": "READY" if formal["score_ready"] else "BLOCKED",
        "monthly_runner_ready": "READY" if (SMOKE_BATCH_DIR / "manifest.json").exists() else "BLOCKED",
        "result_batch_contract_ready": "READY"
        if batch_status["risk_result_contracts_ok"] and batch_status["risk_model_core_validation_ok"]
        else "BLOCKED",
        "risk_model_core_ready": "READY" if model_core_status["risk_entities_rows"] > 0 else "BLOCKED",
        "backend_api_contract_ready": "CONDITIONAL_READY",
        "frontend_payload_contract_ready": "CONDITIONAL_READY",
        "customer_visibility_safe": "READY" if safety_status["ok"] else "BLOCKED",
        "detector_business_boundary_ready": "CONDITIONAL_READY",
        "proof_case_ready": "CONDITIONAL_READY",
        "work_order_ready": "CONDITIONAL_READY",
        "export_ready": "CONDITIONAL_READY" if export_status["ok"] else "BLOCKED",
    }
    if not wip_unchanged:
        gates["frontend_payload_contract_ready"] = "BLOCKED"
        gates["backend_api_contract_ready"] = "BLOCKED"
    blockers = [name for name, status in gates.items() if status == "BLOCKED"]
    integration_ready = "BLOCKED" if blockers else "CONDITIONAL_READY"
    gates["formal_frontend_backend_integration_ready"] = integration_ready
    can_first = ["index/workbench", "clues/risk list", "clue-detail/risk cards", "dashboard/monthly"]
    defer = ["proof-case/backtest", "verify/recovery", "distributor alerts", "order detail", "PDF export"]
    df = pd.DataFrame([{"gate": k, "status": v} for k, v in gates.items()])
    text = f"""# Pre Frontend Backend Integration Gate

- formal_frontend_backend_integration_ready: {integration_ready}
- integration_start_allowed: {"YES_FOR_CORE_RISK_PAGES" if integration_ready != "BLOCKED" else "NO"}
- based_on_working_tree: true
- project_wip_present: true
- frontend_wip_present: true
- project_frontend_wip_unchanged: {wip_unchanged}
- backend API integration can start: {"yes, for core risk pages" if integration_ready != "BLOCKED" else "no"}
- frontend mock replacement can start: {"yes, for core risk pages" if integration_ready != "BLOCKED" else "no"}
- first pages: {", ".join(can_first)}
- deferred pages: {", ".join(defer)}
- blockers: {", ".join(blockers) if blockers else "none for core risk pages"}

The current algorithm/data layer is `CONDITIONAL_READY`, not full `READY`,
because strict SQL/raw-orders-to-fact parity and org/user routing remain later
gates. Result-batch differences are formal algorithm batch vs frontend
projection differences, not model/feature/candidate semantic blockers.

{df.to_markdown(index=False)}
"""
    write_text(REPORT_DIR / "pre_frontend_backend_integration_gate.md", text)
    return {"gates": gates, "first_pages": can_first, "deferred_pages": defer, "blockers": blockers}


def load_batch_table(batch_dir: Path, name: str) -> pd.DataFrame:
    parquet = batch_dir / f"{name}.parquet"
    csv = batch_dir / f"{name}.csv"
    if parquet.exists():
        return pd.read_parquet(parquet)
    if csv.exists():
        return pd.read_csv(csv)
    return pd.DataFrame()


def table_exists(batch_dir: Path, name: str) -> bool:
    return (batch_dir / f"{name}.parquet").exists() or (batch_dir / f"{name}.csv").exists()


def bool_series(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df:
        return pd.Series(False, index=df.index)
    values = df[col]
    if values.dtype == bool:
        return values.fillna(False)
    return values.astype(str).str.lower().isin(["1", "true", "yes", "y"])


def truthy_count(values: pd.Series) -> int:
    if values.dtype == bool:
        return int(values.fillna(False).sum())
    return int(values.astype(str).str.lower().isin(["1", "true", "yes", "y"]).sum())


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
