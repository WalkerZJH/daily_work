from __future__ import annotations

from pathlib import Path
import json

import pandas as pd


BATCH_DIR = Path("data/entity_complete_v2_coverage_expansion/11_business_detector_adaptation/risk_result_batches/batch_id=2025-12-business-detector-v1")


def test_business_detector_payloads_do_not_overclaim() -> None:
    distributor = json.loads((BATCH_DIR / "page_payloads/distributor_payload.json").read_text(encoding="utf-8"))
    dashboard = json.loads((BATCH_DIR / "page_payloads/dashboard_payload.json").read_text(encoding="utf-8"))

    assert distributor["delivery_detector_enabled"] is False
    assert distributor["alerts"] == []
    text = json.dumps(distributor, ensure_ascii=False)
    assert "配送商责任明确" not in text
    assert "配送商导致流失" not in text
    assert "待接入" in json.dumps(dashboard["kpi_cards"], ensure_ascii=False)


def test_business_detector_cards_and_evidence_remain_bounded() -> None:
    entities = pd.read_parquet(BATCH_DIR / "risk_entities.parquet", columns=["risk_entity_id", "auto_dispatch_allowed"])
    cards = pd.read_parquet(BATCH_DIR / "risk_cards.parquet", columns=["risk_entity_id", "risk_card_id", "candidate_id"])
    evidence = pd.read_parquet(BATCH_DIR / "risk_card_evidence.parquet", columns=["risk_card_id", "candidate_id", "visibility_level"])

    assert len(entities) == 871
    assert cards.groupby("risk_entity_id").size().max() <= 5
    if not evidence.empty:
        assert evidence.groupby("risk_card_id").size().max() <= 3
    assert entities["auto_dispatch_allowed"].eq(False).all()


def test_business_detector_manifest_keeps_service_gate_closed() -> None:
    manifest = json.loads((BATCH_DIR / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["package_scope"] == "business_detector_frontend_worklist"
    assert manifest["customer_facing_probability_service_allowed"] is False
    assert manifest["auto_dispatch_allowed"] is False
    assert manifest["proof_case_report_allowed"] is False

