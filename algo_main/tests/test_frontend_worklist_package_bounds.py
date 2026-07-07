from __future__ import annotations

from pathlib import Path

import pandas as pd


M_WORKLIST = Path("data/entity_complete_v2_coverage_expansion/09_m_module_closure/m1_manufacturer_worklist_candidates.csv")
BATCH_DIR = Path("data/entity_complete_v2_coverage_expansion/10_frontend_worklist_model_package/risk_result_batches/batch_id=2025-12-frontend-worklist-v1")


def test_frontend_entities_do_not_exceed_m1_worklist_scope() -> None:
    worklist_rows = len(pd.read_csv(M_WORKLIST, usecols=["candidate_id"]))
    entities = pd.read_parquet(BATCH_DIR / "risk_entities.parquet", columns=["candidate_id"])

    assert len(entities) <= worklist_rows


def test_frontend_worklist_has_bounded_card_and_evidence_counts() -> None:
    cards = pd.read_parquet(BATCH_DIR / "risk_cards.parquet", columns=["risk_entity_id", "risk_card_id"])
    evidence = pd.read_parquet(BATCH_DIR / "risk_card_evidence.parquet", columns=["risk_card_id", "visibility_level"])

    assert cards.groupby("risk_entity_id").size().max() <= 5
    business_visible = evidence[evidence["visibility_level"].eq("business_visible")]
    if not business_visible.empty:
        assert business_visible.groupby("risk_card_id").size().max() <= 3


def test_index_payload_is_top_eight_only() -> None:
    import json

    payload = json.loads((BATCH_DIR / "page_payloads/index_payload.json").read_text(encoding="utf-8"))
    assert len(payload["top_clues"]) <= 8

