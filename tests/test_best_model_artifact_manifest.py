from __future__ import annotations

import json
from pathlib import Path


ARTIFACT_DIR = Path("model_artifacts/risk_algorithm_core/main_churn/current")


def test_best_model_artifact_manifest_freezes_v2_choice() -> None:
    manifest = json.loads((ARTIFACT_DIR / "artifact_manifest.json").read_text(encoding="utf-8"))
    assert manifest["model_family"] == "xgboost_small"
    assert manifest["feature_group"] == "all_safe_features_without_choice_set"
    assert manifest["excludes_choice_set"] is True
    assert manifest["calibration"] == "raw"
    assert manifest["hyperparameter_search_allowed"] is False
    assert manifest["required_features"]


def test_best_model_bundle_contains_policy_files() -> None:
    for name in [
        "model.joblib",
        "feature_schema.json",
        "calibration.json",
        "candidate_policy.json",
        "detector_config.json",
        "status_policy.json",
        "display_policy.json",
    ]:
        assert (ARTIFACT_DIR / name).exists()
