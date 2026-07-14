from __future__ import annotations

from risk_algorithm_core.artifact_loader import load_current_model_artifact
from risk_algorithm_core.candidate_selector import BoundedCandidateSelector
from risk_algorithm_core.entity_builder import build_monthly_entities
from risk_algorithm_core.feature_engineering import engineer_features
from risk_algorithm_core.normalization import normalize_raw_tables
from risk_algorithm_core.raw_input import read_raw_input_batch
from risk_algorithm_core.scorer import ArtifactRiskScorer
from tests.risk_algorithm_core_test_utils import MODEL_FIXTURE, RAW_FIXTURE, SCHEMA_MAPPING


def test_candidate_selector_persists_full_recurring_universe() -> None:
    batch = read_raw_input_batch(RAW_FIXTURE, SCHEMA_MAPPING)
    normalized, _ = normalize_raw_tables(batch.tables, "2026-07-31")
    entities = build_monthly_entities(
        normalized["orders"],
        normalized["drug_master"],
        normalized["hospital_master"],
        normalized["product_line_mapping"],
        "2026-07",
        "2026-07-31",
        ["H6"],
    )
    features, _ = engineer_features(entities, normalized["orders"], "2026-07-31")
    scores = ArtifactRiskScorer(load_current_model_artifact(MODEL_FIXTURE)).score(features)
    selected, report = BoundedCandidateSelector(
        {
            "frontend_default_topN_per_manufacturer": 1,
            "one_shot_topN_per_manufacturer": 1,
            "observation_topN_per_manufacturer": 1,
            "global_candidate_cap": 5,
        }
    ).select(scores, features)
    expected_recurring = int(features["sample_class"].eq("recurring").sum())
    assert len(selected) == expected_recurring
    assert selected["is_selected_for_frontend"].all()
    assert set(selected["candidate_policy"]) == {"full_recurring_universe"}
    assert set(selected["selection_reason"]) == {"recurring_eligible"}
    assert "selected_candidate_rows" in set(report["metric"])
