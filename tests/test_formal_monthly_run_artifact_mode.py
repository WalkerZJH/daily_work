from __future__ import annotations

import json

import pytest

from risk_algorithm_core.monthly_runner import MonthlyRiskRunner
from tests.formal_raw_to_batch_test_utils import FORMAL_BATCH_DIR, FORMAL_CONFIG


def test_formal_config_requires_artifact_mode() -> None:
    runner = MonthlyRiskRunner.from_config_file(FORMAL_CONFIG)
    assert runner.config.require_artifact is True
    assert str(runner.config.artifact_dir).endswith("model_artifacts/risk_algorithm_core/main_churn/current")
    assert "allow_rule_baseline: false" in FORMAL_CONFIG.read_text(encoding="utf-8")


def test_formal_output_manifest_uses_best_artifact_when_available() -> None:
    manifest_path = FORMAL_BATCH_DIR / "manifest.json"
    if not manifest_path.exists():
        pytest.skip("formal result batch is generated from local ignored data")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["report_type"] == "monthly"
    assert manifest["model_family"] == "xgboost_small"
    assert manifest["feature_group"] == "all_safe_features_without_choice_set"
    assert manifest["calibration"] == "raw"
    assert manifest["excludes_choice_set"] is True
    assert manifest["auto_dispatch_allowed"] is False
    assert manifest["customer_facing_probability_service_allowed"] is False
