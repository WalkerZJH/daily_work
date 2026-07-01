"""Dry-run repository cleanup audit helpers for alive prediction work."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
import re
import shutil
from typing import Iterable

import pandas as pd


SCAN_DIRS = ["scripts", "src/alg", "notebooks", "reports", "docs", "configs", "data"]
CURRENT_ENTRYPOINTS = {
    "scripts/rebuild_alive_prediction_model_selection_notebook.py",
    "scripts/run_alive_prediction_demand_shape_label_review.py",
    "scripts/run_alive_prediction_calibration_v2.py",
    "scripts/run_alive_prediction_feature_stability_v1.py",
    "scripts/run_alive_prediction_temporal_drift_diagnostics.py",
    "scripts/materialize_alive_prediction_artifacts.py",
    "notebooks/02_alive_prediction_model_selection_story.ipynb",
}
HISTORICAL_STAGE_MARKERS = {
    "run_alive_prediction_calibration_v1.py": "historical_calibration_v1",
    "run_alive_prediction_calibration_review.py": "historical_calibration_review",
    "run_alive_prediction_rolling_origin_v1.py": "historical_rolling_origin",
    "run_alive_prediction_probability_consolidation.py": "historical_probability_consolidation",
    "run_alive_prediction_probability_stabilization.py": "historical_probability_stabilization",
    "run_alive_prediction_feature_stability_v1.py": "current_supporting_feature_stability",
    "run_alive_prediction_calibration_v2.py": "current_probability_candidate_decision",
    "run_alive_prediction_demand_shape_label_review.py": "current_demand_shape_review",
}
DUPLICATE_PATTERNS = {
    "duplicate_ece_calculation": [r"\bece_score\b", r"expected calibration error", r"\bcalibration_bins?\b"],
    "duplicate_topk_metric": [r"precision_at_top", r"lift_at_top", r"ndcg_at_top", r"TOP_PCTS"],
    "duplicate_calibration_metric": [r"Platt", r"isotonic", r"fit_calibrator", r"calibration_method"],
    "duplicate_report_writer": [r"dataframe_to_markdown", r"markdown_table", r"write_text"],
    "duplicate_path_constants": [r"OUTPUT_DIR", r"reports/alive_prediction", r"ROOT ="],
    "duplicate_feature_set_definition": [r"feature_sets", r"base_recency_frequency_only", r"frequency_decay_v1"],
    "duplicate_split_definition": [r"fold_1", r"fold_2", r"train_start", r"test_start", r"purge"],
}
CANONICAL_LOCATIONS = {
    "duplicate_ece_calculation": "src/alg/metrics/",
    "duplicate_topk_metric": "src/alg/metrics/",
    "duplicate_calibration_metric": "src/alg/metrics/calibration.py or src/alg/validation/",
    "duplicate_report_writer": "src/alg/evaluation/",
    "duplicate_path_constants": "src/alg/artifacts/paths.py or src/alg/utils/",
    "duplicate_feature_set_definition": "src/alg/features/",
    "duplicate_split_definition": "src/alg/validation/",
}


@dataclass(frozen=True)
class FileInventory:
    path: str
    file_size: int
    modified_time: str


def relative_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def iter_files(root: Path, rel_dirs: Iterable[str] = SCAN_DIRS) -> Iterable[Path]:
    for rel in rel_dirs:
        base = root / rel
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file():
                yield path


def inventory_row(root: Path, path: Path) -> FileInventory:
    stat = path.stat()
    return FileInventory(
        path=relative_path(root, path),
        file_size=int(stat.st_size),
        modified_time=pd.Timestamp(stat.st_mtime, unit="s").isoformat(),
    )


def python_ast_details(path: Path) -> tuple[list[str], list[str]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return [], []
    imports: list[str] = []
    functions: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imports.append(module)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)
    return sorted(set(imports)), functions


def extract_output_dirs(text: str) -> str:
    matches = sorted(set(re.findall(r"reports/alive_prediction[_a-zA-Z0-9/-]*", text)))
    return ";".join(matches[:20])


def likely_stage(rel: str) -> str:
    name = Path(rel).name
    if name in HISTORICAL_STAGE_MARKERS:
        return HISTORICAL_STAGE_MARKERS[name]
    if "temporal_drift" in rel:
        return "temporal_drift"
    if "feature_stability" in rel:
        return "feature_stability"
    if "calibration_v2" in rel:
        return "calibration_v2"
    if "demand_shape" in rel:
        return "demand_shape_label_review"
    if "small_model" in rel:
        return "small_model_experiment"
    if "notebook" in rel:
        return "notebook_or_builder"
    return "utility_or_general"


def script_inventory(root: Path) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for path in sorted((root / "scripts").glob("*.py")):
        rel = relative_path(root, path)
        text = path.read_text(encoding="utf-8", errors="ignore")
        imports, functions = python_ast_details(path)
        is_current = rel in CURRENT_ENTRYPOINTS
        historical = Path(rel).name in HISTORICAL_STAGE_MARKERS and not is_current
        rows.append(
            {
                **inventory_row(root, path).__dict__,
                "imports": ";".join(imports[:40]),
                "main_functions": ";".join(functions[:40]),
                "output_dirs": extract_output_dirs(text),
                "reads_reports": "reports/" in text and ("read_csv" in text or "read_text" in text),
                "writes_reports": "reports/" in text and ("to_csv" in text or "write_text" in text),
                "reads_data": "data/" in text and ("read_parquet" in text or "read_csv" in text),
                "writes_data": "data/" in text and ("to_parquet" in text or "write_artifact" in text),
                "likely_stage": likely_stage(rel),
                "is_current_entrypoint": is_current,
                "keep_reason": "current entrypoint" if is_current else ("historical reproducibility" if historical else "utility or supporting script"),
                "deprecation_candidate": historical,
                "deprecation_reason": "historical stage; keep until reports and notebook references are stable" if historical else "",
            }
        )
    return pd.DataFrame(rows)


def generic_inventory(root: Path, rel_dir: str) -> pd.DataFrame:
    base = root / rel_dir
    rows = [inventory_row(root, path).__dict__ for path in sorted(base.rglob("*")) if path.is_file()] if base.exists() else []
    return pd.DataFrame(rows, columns=["path", "file_size", "modified_time"])


def duplicate_code_candidates(root: Path) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for path in iter_files(root, ["scripts", "src/alg"]):
        if path.suffix.lower() != ".py":
            continue
        rel = relative_path(root, path)
        text = path.read_text(encoding="utf-8", errors="ignore")
        for category, patterns in DUPLICATE_PATTERNS.items():
            hits = [pattern for pattern in patterns if re.search(pattern, text, flags=re.IGNORECASE)]
            if hits:
                rows.append(
                    {
                        "path": rel,
                        "duplicate_category": category,
                        "matched_patterns": ";".join(hits),
                        "canonical_location": CANONICAL_LOCATIONS[category],
                        "recommendation": "review for consolidation; do not delete automatically",
                    }
                )
    return pd.DataFrame(rows)


def obsolete_doc_candidates(root: Path) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    docs = root / "docs"
    if not docs.exists():
        return pd.DataFrame(columns=["path", "reason", "recommended_action"])
    markers = ["old", "legacy", "deprecated", "draft", "archive"]
    for path in sorted(docs.rglob("*")):
        if not path.is_file():
            continue
        rel = relative_path(root, path)
        lower = rel.lower()
        reason = ""
        if any(marker in lower for marker in markers):
            reason = "name suggests historical or draft document"
        elif "alive_prediction" in lower and "current_entrypoints" not in lower:
            reason = "alive prediction design doc; keep but classify as historical/reference once notebook is current"
        if reason:
            rows.append({"path": rel, "reason": reason, "recommended_action": "keep or archive after manual review"})
    return pd.DataFrame(rows)


def obsolete_script_candidates(script_df: pd.DataFrame) -> pd.DataFrame:
    if script_df.empty:
        return pd.DataFrame(columns=["path", "reason", "recommended_action"])
    cand = script_df[script_df["deprecation_candidate"].astype(bool)].copy()
    if cand.empty:
        return pd.DataFrame(columns=["path", "reason", "recommended_action"])
    return cand.rename(columns={"deprecation_reason": "reason"})[["path", "reason"]].assign(
        recommended_action="archive only after manual review; do not delete"
    )


def write_report(root: Path, output_dir: Path, dry_run: bool = True) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    scripts = script_inventory(root)
    reports = generic_inventory(root, "reports")
    cache = pd.concat(
        [
            generic_inventory(root, "data"),
            generic_inventory(root, "artifacts"),
        ],
        ignore_index=True,
    )
    duplicates = duplicate_code_candidates(root)
    obsolete_docs = obsolete_doc_candidates(root)
    obsolete_scripts = obsolete_script_candidates(scripts)
    safe_delete = ["No safe delete candidates in this dry-run. Keep all data/cache/parquet/reports until manual approval."]
    archive_candidates = obsolete_scripts["path"].tolist() if not obsolete_scripts.empty else []
    archive_candidates += obsolete_docs["path"].head(50).tolist() if not obsolete_docs.empty else []

    outputs = {
        "summary": output_dir / "repo_cleanup_summary.md",
        "script_inventory": output_dir / "script_inventory.csv",
        "report_inventory": output_dir / "report_inventory.csv",
        "cache_artifact_inventory": output_dir / "cache_artifact_inventory.csv",
        "duplicate_code_candidates": output_dir / "duplicate_code_candidates.csv",
        "obsolete_doc_candidates": output_dir / "obsolete_doc_candidates.csv",
        "obsolete_script_candidates": output_dir / "obsolete_script_candidates.csv",
        "safe_delete_candidates": output_dir / "safe_delete_candidates.txt",
        "archive_candidates": output_dir / "archive_candidates.txt",
        "cleanup_apply_plan": output_dir / "cleanup_apply_plan.md",
    }
    scripts.to_csv(outputs["script_inventory"], index=False, encoding="utf-8-sig")
    reports.to_csv(outputs["report_inventory"], index=False, encoding="utf-8-sig")
    cache.to_csv(outputs["cache_artifact_inventory"], index=False, encoding="utf-8-sig")
    duplicates.to_csv(outputs["duplicate_code_candidates"], index=False, encoding="utf-8-sig")
    obsolete_docs.to_csv(outputs["obsolete_doc_candidates"], index=False, encoding="utf-8-sig")
    obsolete_scripts.to_csv(outputs["obsolete_script_candidates"], index=False, encoding="utf-8-sig")
    outputs["safe_delete_candidates"].write_text("\n".join(safe_delete) + "\n", encoding="utf-8")
    outputs["archive_candidates"].write_text("\n".join(archive_candidates) + ("\n" if archive_candidates else ""), encoding="utf-8")
    outputs["cleanup_apply_plan"].write_text(
        "\n".join(
            [
                "# Cleanup Apply Plan",
                "",
                "This stage is dry-run only. Do not delete files.",
                "",
                "If an apply mode is used later, it must be invoked as:",
                "",
                "```bash",
                "python scripts/audit_alive_prediction_repo_cleanup.py --apply --confirm",
                "```",
                "",
                "Apply mode may only move manually reviewed candidates to `_archive/`; it must not remove data/cache/parquet/reports.",
                "",
                "Recommended canonical locations:",
                "- metrics: `src/alg/metrics/`",
                "- calibration: `src/alg/metrics/calibration.py` or `src/alg/validation/`",
                "- temporal split: `src/alg/validation/`",
                "- feature set definitions: `src/alg/features/`",
                "- presentation/report helpers: `src/alg/evaluation/`",
                "- path helpers: `src/alg/artifacts/paths.py` or `src/alg/utils/`",
            ]
        ),
        encoding="utf-8",
    )
    outputs["summary"].write_text(
        "\n".join(
            [
                "# Alive Prediction Repo Cleanup Audit",
                "",
                f"Mode: {'dry-run' if dry_run else 'apply'}",
                "",
                "No files were deleted by this audit.",
                "",
                f"- Script files scanned: {len(scripts)}",
                f"- Report files inventoried: {len(reports)}",
                f"- Data/artifact files inventoried: {len(cache)}",
                f"- Duplicate-code candidate rows: {len(duplicates)}",
                f"- Obsolete script candidate rows: {len(obsolete_scripts)}",
                f"- Obsolete doc candidate rows: {len(obsolete_docs)}",
                "",
                "Key duplicate categories are repeated ECE/calibration utilities, TopK metrics, report writers, path constants, feature-set definitions, and temporal split definitions.",
                "",
                "Safe delete policy: none in this dry-run. Archive candidates require manual review and later `_archive/` move only.",
            ]
        ),
        encoding="utf-8",
    )
    return outputs


def apply_archive(root: Path, output_dir: Path, confirm: bool) -> None:
    if not confirm:
        raise RuntimeError("--apply requires --confirm")
    archive_file = output_dir / "archive_candidates.txt"
    if not archive_file.exists():
        raise RuntimeError("archive_candidates.txt missing; run dry-run first")
    archive_root = root / "_archive/alive_prediction_cleanup"
    archive_root.mkdir(parents=True, exist_ok=True)
    for line in archive_file.read_text(encoding="utf-8").splitlines():
        rel = line.strip()
        if not rel:
            continue
        source = root / rel
        if not source.exists() or not source.is_file():
            continue
        if rel.startswith("data/") or rel.startswith("reports/"):
            continue
        target = archive_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
