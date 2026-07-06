from __future__ import annotations

import pandas as pd

from alg.tasks.die_prediction.entity_complete_rebuild import (
    build_m1_candidates,
    build_m4_detector_evidence,
    build_m5_status_decision,
    build_m7_evidence_bundle,
)


def _predictions() -> pd.DataFrame:
    rows = []
    for i in range(12):
        rows.append(
            {
                "model_name": "logistic_regression_base_recency_frequency_interval",
                "manufacturer_code": "m1",
                "hospital_code": f"h{i}",
                "drug_group": "d1",
                "cutoff_month": "2024-01",
                "horizon": "H3",
                "label_die_H": int(i in {0, 1, 2}),
                "label_alive_H": int(i not in {0, 1, 2}),
                "probability_score": 0.99 - i * 0.05,
                "score": 0.99 - i * 0.05,
                "recency_only_baseline": i,
                "frequency_decay_baseline": 1.0 if i < 3 else 0.1,
                "interval_overdue_baseline": 2.0 if i < 3 else 0.5,
                "hybrid_interval_frequency_score": 0.99 - i * 0.05,
                "history_sufficiency_flag": "history_sufficient",
                "demand_shape_label": "smooth",
            }
        )
    return pd.DataFrame(rows)


def test_m1_candidate_coverage_calculation_correct() -> None:
    metrics, candidates = build_m1_candidates(_predictions())
    row = metrics[metrics["candidate_policy"].eq("probability_top10")].iloc[0]

    assert row["candidate_rows"] >= 1
    assert row["candidate_die_recall"] > 0
    assert not candidates.empty


def test_detector_status_and_evidence_semantics_are_separated() -> None:
    predictions = _predictions()
    _metrics, candidates = build_m1_candidates(predictions)
    detectors = build_m4_detector_evidence(predictions)
    status = build_m5_status_decision(candidates)
    bundle = build_m7_evidence_bundle(candidates, pd.DataFrame())

    assert detectors["semantic_note"].str.contains("not probability").all()
    assert status["auto_dispatch_allowed"].eq(False).all()
    assert bundle["forbidden_claims"].str.contains("auto dispatch").all()

