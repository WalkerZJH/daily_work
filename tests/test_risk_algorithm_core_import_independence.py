from __future__ import annotations

import importlib
from pathlib import Path


def test_risk_algorithm_core_imports_independently() -> None:
    module = importlib.import_module("risk_algorithm_core")
    assert module is not None


def test_risk_algorithm_core_does_not_import_algo_main_or_training_libs() -> None:
    root = Path(__file__).resolve().parents[1] / "risk_algorithm_core"
    source = "\n".join(path.read_text(encoding="utf-8") for path in root.rglob("*.py"))
    for token in ["alg.", "algo_main", "entity_complete_", "xgboost", "lightgbm", "catboost", "sklearn"]:
        assert token not in source


def test_project_and_frontend_are_unmodified() -> None:
    import subprocess

    repo = Path(__file__).resolve().parents[1]
    result = subprocess.run(["git", "status", "--short", "--", "project", "front_end"], cwd=repo, text=True, capture_output=True, check=True)
    assert result.stdout.strip() == ""
