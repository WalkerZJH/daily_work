from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "risk_raw_input_minimal"
MODEL_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "model_artifacts" / "risk_algorithm_core" / "main_churn" / "current"
SCHEMA_MAPPING = REPO_ROOT / "configs" / "risk_algorithm_core" / "schema_mapping.example.yaml"
RUN_CONFIG = REPO_ROOT / "configs" / "risk_algorithm_core" / "monthly_run.example.yaml"
