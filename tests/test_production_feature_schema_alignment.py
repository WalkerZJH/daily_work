from __future__ import annotations

import json
from pathlib import Path


ARTIFACT_DIR = Path("model_artifacts/risk_algorithm_core/main_churn/current")
REPORT_DIR = Path("algo_main/reports/entity_complete_v2_coverage_expansion/18_best_model_runtime_alignment")


def test_feature_schema_is_ordered_and_excludes_choice_set() -> None:
    schema = json.loads((ARTIFACT_DIR / "feature_schema.json").read_text(encoding="utf-8"))
    required = schema["required_features"]
    assert len(required) == 49
    assert schema["feature_order"] == required
    assert not any("competitor_order_count" in col for col in required)
    assert "manufacturer_share_within_hospital_drug_asof_cutoff" not in required


def test_feature_parity_matrix_covers_required_features() -> None:
    import pandas as pd

    schema = json.loads((ARTIFACT_DIR / "feature_schema.json").read_text(encoding="utf-8"))
    parity = pd.read_csv(REPORT_DIR / "feature_parity_matrix.csv")
    assert set(schema["required_features"]).issubset(set(parity["required_feature"]))
    assert parity["implemented_in_risk_algorithm_core"].astype(bool).all()
