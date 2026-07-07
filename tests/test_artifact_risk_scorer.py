from __future__ import annotations

from pathlib import Path

import pandas as pd

from risk_algorithm_core.artifact_loader import load_current_model_artifact
from risk_algorithm_core.scorer import ArtifactRiskScorer


ARTIFACT_DIR = Path("model_artifacts/risk_algorithm_core/main_churn/current")


def test_artifact_risk_scorer_runs_with_frozen_feature_order() -> None:
    artifact = load_current_model_artifact(ARTIFACT_DIR, require_artifact=True)
    schema = artifact.feature_schema
    row = {
        "entity_id": "M|H|D",
        "manufacturer_code": "M",
        "hospital_code": "H",
        "drug_group": "D",
        "drug_group_source": "drug_code",
        "cutoff_month": "2026-07",
        "horizon": "H6",
    }
    for feature in schema["feature_order"]:
        dtype = schema["dtype_policy"][feature]
        row[feature] = False if dtype == "bool" else ("__missing__" if dtype == "string" else 0.0)
    scores = ArtifactRiskScorer(artifact).score(pd.DataFrame([row]))
    assert len(scores) == 1
    assert scores["churn_probability_H"].between(0, 1).all()
    assert scores["score_source"].iloc[0] == "artifact"
    assert scores["feature_schema_version"].iloc[0] == "xgboost_small_without_choice_set_v1"
