from __future__ import annotations

from pathlib import Path

import pandas as pd


BATCH_DIR = Path("data/entity_complete_v2_coverage_expansion/10_frontend_worklist_model_package/risk_result_batches/batch_id=2025-12-frontend-worklist-v1")
M_DIR = Path("data/entity_complete_v2_coverage_expansion/09_m_module_closure")


def test_cards_and_evidence_are_candidate_subsets() -> None:
    entities = pd.read_parquet(BATCH_DIR / "risk_entities.parquet", columns=["candidate_id"])
    cards = pd.read_parquet(BATCH_DIR / "risk_cards.parquet", columns=["candidate_id"])
    evidence = pd.read_parquet(BATCH_DIR / "risk_card_evidence.parquet", columns=["candidate_id"])
    entity_ids = set(entities["candidate_id"].astype(str))

    assert set(cards["candidate_id"].astype(str)).issubset(entity_ids)
    assert set(evidence["candidate_id"].astype(str)).issubset(entity_ids)


def test_one_shot_and_observation_are_not_full_dumped() -> None:
    entities = pd.read_parquet(BATCH_DIR / "risk_entities.parquet", columns=["candidate_id", "is_one_shot", "is_observation"])
    all_one_shot_rows = len(pd.read_csv(M_DIR / "m1_one_shot_attention_candidates.csv", usecols=["candidate_id"]))
    all_observation_rows = len(pd.read_csv(M_DIR / "m1_demand_shape_observation_candidates.csv", usecols=["candidate_id"]))

    assert int(entities["is_one_shot"].sum()) < all_one_shot_rows
    assert int(entities["is_observation"].sum()) < all_observation_rows


def test_frontend_payloads_do_not_reference_internal_full_dump() -> None:
    payload_dir = BATCH_DIR / "page_payloads"
    for path in payload_dir.rglob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert "10_mvc_model_package" not in text
        assert "internal_full_status_package" not in text

