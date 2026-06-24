from __future__ import annotations

from datetime import date

import pandas as pd

from app.algorithms.fusion import fuse_detector_results
from app.features.snapshot import FeatureSnapshot
from app.schemas.algorithm import DetectorEvidence, DetectorResult
from app.schemas.config import FusionConfig
from app.services.clue_management_service import ClueManagementService


def test_terminal_change_without_palive_does_not_escalate_to_red_from_rule_score() -> None:
    snapshot = FeatureSnapshot(
        unit_id="ORG-1|product_line|PL-1",
        org_code="ORG-1",
        analysis_grain="product_line",
        target_code="PL-1",
        as_of_date=date(2026, 6, 1),
        features={},
    )
    evidence = DetectorEvidence(
        detector_id="inactive_terminal",
        category="terminal_change",
        family="terminal_activity",
        hit=True,
        severity=100,
        confidence=0.9,
        reason_code="INACTIVE_TERMINAL",
    )

    cards = ClueManagementService().build_candidates(
        snapshots_by_unit={snapshot.unit_id: snapshot},
        terminal_results_by_unit={},
        order_evidence_by_unit={snapshot.unit_id: [evidence]},
        prepared_orders=pd.DataFrame(),
        as_of_date=date(2026, 6, 1),
        config_version="test",
    )

    assert cards[0].backbone.p_alive is None
    assert cards[0].risk_level == "orange"
    assert cards[0].rule_score == 100
    assert cards[0].evidence_summary_structured["rule_score_note"].endswith("not probability.")


def test_legacy_fusion_uses_rule_score_not_weighted_probability() -> None:
    results = [
        DetectorResult(
            detector_name="inactive_terminal",
            hit=True,
            severity=100,
            confidence=0.8,
            reason_code="A",
        ),
        DetectorResult(
            detector_name="new_terminal",
            hit=True,
            severity=10,
            confidence=0.4,
            reason_code="B",
        ),
    ]

    fusion = fuse_detector_results(results, FusionConfig())

    assert fusion.risk_score == 100
    assert fusion.reason_code == "LEGACY_RULE_SCORE_NOT_PROBABILITY"
