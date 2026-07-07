from __future__ import annotations

from risk_algorithm_core.artifact_loader import load_current_model_artifact
from risk_algorithm_core.entity_builder import build_monthly_entities
from risk_algorithm_core.feature_engineering import engineer_features
from risk_algorithm_core.normalization import normalize_raw_tables
from risk_algorithm_core.raw_input import read_raw_input_batch
from risk_algorithm_core.scorer import ArtifactRiskScorer, RuleBaselineScorer
from tests.risk_algorithm_core_test_utils import MODEL_FIXTURE, RAW_FIXTURE, SCHEMA_MAPPING


def _features():
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
    return engineer_features(entities, normalized["orders"], "2026-07-31")[0]


def test_artifact_scorer_outputs_probabilities() -> None:
    features = _features()
    artifact = load_current_model_artifact(MODEL_FIXTURE)
    scores = ArtifactRiskScorer(artifact).score(features)
    assert len(scores) == len(features)
    assert scores["churn_probability_H"].between(0, 1).all()
    assert set(scores["score_source"]) == {"artifact"}


def test_rule_baseline_is_dry_run_only() -> None:
    features = _features()
    scores = RuleBaselineScorer().score(features)
    assert set(scores["score_source"]) == {"dry_run_rule_baseline"}
