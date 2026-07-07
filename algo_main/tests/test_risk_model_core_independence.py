from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
CORE_DIR = REPO_ROOT / "risk_model_core"
FIXTURE_BATCH = REPO_ROOT / "tests" / "fixtures" / "risk_result_batch_minimal"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _source_texts() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in CORE_DIR.glob("*.py"))


def test_risk_model_core_imports_without_algorithm_modules() -> None:
    module = importlib.import_module("risk_model_core")
    assert module is not None

    source = _source_texts()
    forbidden = [
        "alg.tasks.die_prediction",
        "entity_complete_algorithm_consolidation",
        "xgboost",
        "lightgbm",
        "catboost",
        "sklearn",
    ]
    for token in forbidden:
        assert token not in source


def test_monthly_report_naming_is_explicit() -> None:
    scanned_paths = list(CORE_DIR.glob("*.py")) + list(FIXTURE_BATCH.rglob("*.*"))
    scanned_text = "\n".join(path.read_text(encoding="utf-8") for path in scanned_paths)

    forbidden_daily_names = [
        "daily_reports",
        "daily_report",
        "DailyReport",
        "list_daily",
    ]
    for token in forbidden_daily_names:
        assert token not in scanned_text

    assert (FIXTURE_BATCH / "monthly_reports.csv").exists()
    assert not (FIXTURE_BATCH / "daily_reports.csv").exists()


def test_independence_script_passes_without_algo_main_src() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "check_risk_model_core_independence.py"),
            "--batch-dir",
            str(FIXTURE_BATCH),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "independence_check: ok" in result.stdout


def test_project_and_frontend_are_not_modified() -> None:
    result = subprocess.run(
        ["git", "status", "--short", "--", "project", "front_end"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert result.stdout.strip() == ""


def test_clickhouse_repository_is_stub_only() -> None:
    from risk_model_core.repositories import ClickHouseRiskResultRepository

    repo = ClickHouseRiskResultRepository()
    with pytest.raises(NotImplementedError):
        repo.manifest()
