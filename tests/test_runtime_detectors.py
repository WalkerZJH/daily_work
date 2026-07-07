from __future__ import annotations

from risk_algorithm_core.artifact_loader import load_current_model_artifact
from risk_algorithm_core.candidate_selector import BoundedCandidateSelector
from risk_algorithm_core.detectors import FrequencyDropDetector, IntervalOverdueDetector, OneShotAttentionDetector, QuantityDropDetector, TerminalLossDetector
from risk_algorithm_core.entity_builder import build_monthly_entities
from risk_algorithm_core.feature_engineering import engineer_features
from risk_algorithm_core.normalization import normalize_raw_tables
from risk_algorithm_core.raw_input import read_raw_input_batch
from risk_algorithm_core.scorer import ArtifactRiskScorer
from tests.risk_algorithm_core_test_utils import MODEL_FIXTURE, RAW_FIXTURE, SCHEMA_MAPPING


def test_runtime_detectors_emit_safe_evidence() -> None:
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
    selected, _ = BoundedCandidateSelector({"global_candidate_cap": 20}).select(scores, features)
    frames = [
        TerminalLossDetector().run(selected, features),
        IntervalOverdueDetector().run(selected, features),
        FrequencyDropDetector().run(selected, features),
        QuantityDropDetector().run(selected, features),
        OneShotAttentionDetector().run(selected, features),
    ]
    assert sum(len(frame) for frame in frames) > 0
    combined_text = "\n".join(frame.to_csv(index=False) for frame in frames)
    assert "distributor responsibility" not in combined_text.lower()
    assert "competitor replacement" not in combined_text.lower()
