from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

from risk_algorithm_core.candidate_selector import classify_candidate_type
from risk_algorithm_core.cutoff_features import build_source_cutoff_features
from risk_algorithm_core.result_assembler import _build_oneshot_terminals, _build_risk_entities
from risk_algorithm_core.status_decider import StatusDecider

ROOT = Path(__file__).resolve().parents[1]
ALGO_SRC = ROOT / "algo_main" / "src"
if str(ALGO_SRC) not in sys.path:
    sys.path.insert(0, str(ALGO_SRC))

from alg.tasks.die_prediction import entity_complete_rebuild as algo_rebuild  # noqa: E402


def _entity_month_rows() -> pd.DataFrame:
    rows = []
    for month in ["2026-01", "2026-02", "2026-07"]:
        rows.append(_row("M1", "H1", "D1", month, 1, 100.0))
    rows.append(_row("M1", "H2", "D2", "2026-07", 2, 200.0))
    rows.append(_row("M1", "H3", "D3", "2025-01", 1, 50.0))
    return pd.DataFrame(rows)


def _row(
    manufacturer_code: str,
    hospital_code: str,
    drug_group: str,
    purchase_month: str,
    order_count: int,
    amount: float,
) -> dict[str, object]:
    return {
        "manufacturer_code": manufacturer_code,
        "hospital_code": hospital_code,
        "drug_group": drug_group,
        "purchase_month": pd.Timestamp(purchase_month).to_period("M").to_timestamp("M"),
        "order_count": order_count,
        "purchase_quantity_sum": float(order_count),
        "purchase_amount_sum": amount,
    }


def test_cutoff_features_emit_strict_complete_three_class_sample_scope() -> None:
    features, _, _ = build_source_cutoff_features(
        _entity_month_rows(),
        [pd.Timestamp("2026-07-31")],
        max_monitor_gap_months=12,
    )

    assert features.attrs["all_seen_entity_count"] == 3
    assert features.attrs["unmonitorable_entity_count"] == 1
    assert features.attrs["one_shot_entity_count"] == 1
    assert features.attrs["recurring_entity_count"] == 1
    assert features.attrs["monitorable_entity_count"] == 2
    assert set(features["sample_class"]) == {"one_shot", "recurring"}
    assert "observation" not in set(features["sample_class"])
    assert "demand_shape_observation" not in set(features["sample_class"])


def test_algo_main_rebuild_uses_same_strict_three_class_scope() -> None:
    features = algo_rebuild.build_features_for_cutoff(
        _entity_month_rows(),
        pd.Timestamp("2026-07-31"),
        max_monitor_gap_months=12,
    )

    assert features.attrs["all_seen_entity_count"] == 3
    assert features.attrs["unmonitorable_entity_count"] == 1
    assert features.attrs["one_shot_entity_count"] == 1
    assert features.attrs["recurring_entity_count"] == 1
    assert set(features["sample_class"]) == {"one_shot", "recurring"}


def test_candidate_type_uses_active_month_count_not_demand_shape_observation() -> None:
    frame = pd.DataFrame(
        [
            {
                "active_month_count_asof_cutoff": 1,
                "months_since_last_purchase_asof_cutoff": 0,
                "demand_shape_label": "smooth",
                "history_sufficiency_flag": "history_insufficient",
            },
            {
                "active_month_count_asof_cutoff": 2,
                "months_since_last_purchase_asof_cutoff": 0,
                "demand_shape_label": "lumpy",
                "history_sufficiency_flag": "history_insufficient",
            },
            {
                "active_month_count_asof_cutoff": 5,
                "months_since_last_purchase_asof_cutoff": 13,
                "demand_shape_label": "smooth",
                "history_sufficiency_flag": "history_sufficient",
            },
        ]
    )

    assert classify_candidate_type(frame, max_monitor_gap_months=12).tolist() == [
        "one_shot",
        "recurring",
        "unmonitorable",
    ]


def test_status_decider_no_longer_emits_observation_only() -> None:
    candidates = pd.DataFrame(
        [
            _candidate("recurring-1", "recurring", 0.7),
            _candidate("oneshot-1", "one_shot", 0.9),
        ]
    )

    status = StatusDecider().decide(candidates, pd.DataFrame(), pd.DataFrame())

    assert set(status["candidate_type"]) == {"recurring", "one_shot"}
    assert "observation_only" not in set(status["final_candidate_status"])
    recurring = status[status["candidate_type"].eq("recurring")].iloc[0]
    oneshot = status[status["candidate_type"].eq("one_shot")].iloc[0]
    assert recurring["is_observation"] == False
    assert oneshot["is_observation"] == False
    assert recurring["probability_display_mode"] == "show_risk_band"
    assert oneshot["probability_display_mode"] == "hide_probability"


def test_result_batch_risk_entities_keep_recurring_probability_and_exclude_one_shot() -> None:
    status = pd.DataFrame(
        [
            {
                **_candidate("recurring-1", "recurring", 0.7),
                "final_candidate_status": "priority_review",
                "review_priority": "P1",
                "risk_level": "orange",
                "risk_color": "orange",
                "is_high_risk": True,
                "is_observation": False,
                "is_one_shot": False,
                "probability_display_mode": "show_risk_band",
                "evidence_strength": "weak",
                "selection_caveat": "test",
            },
            {
                **_candidate("oneshot-1", "one_shot", 0.9),
                "final_candidate_status": "one_shot_attention",
                "review_priority": "P3",
                "risk_level": "attention",
                "risk_color": "gray",
                "is_high_risk": False,
                "is_observation": False,
                "is_one_shot": True,
                "probability_display_mode": "hide_probability",
                "evidence_strength": "weak",
                "selection_caveat": "test",
            },
        ]
    )

    risk_entities = _build_risk_entities(status, "2026-07")

    assert risk_entities["risk_entity_id"].tolist() == ["recurring-1"]
    assert risk_entities.iloc[0]["risk_probability_value"] == 0.7
    assert risk_entities.iloc[0]["is_one_shot"] == False
    assert risk_entities.iloc[0]["is_observation"] == False


def test_result_batch_writes_independent_oneshot_terminal_serving_table() -> None:
    features = pd.DataFrame(
        [
            {
                "entity_id": "M1|H1|D1",
                "manufacturer_code": "M1",
                "hospital_code": "H1",
                "hospital_display_name": "Hospital One",
                "drug_group": "D1",
                "drug_display_name": "Drug One",
                "region_display_name": "North",
                "cutoff_month": pd.Timestamp("2026-07-31"),
                "sample_class": "one_shot",
                "one_shot_flag": True,
                "active_month_count_asof_cutoff": 1,
                "months_since_last_purchase_asof_cutoff": 0,
                "first_purchase_month_asof_cutoff": "2026-07-31",
                "first_purchase_amount": 1200,
                "risk_score": 0.83,
            },
            {
                "entity_id": "M1|H2|D2",
                "manufacturer_code": "M1",
                "hospital_code": "H2",
                "drug_group": "D2",
                "cutoff_month": pd.Timestamp("2026-07-31"),
                "sample_class": "recurring",
                "one_shot_flag": False,
                "active_month_count_asof_cutoff": 2,
                "months_since_last_purchase_asof_cutoff": 0,
            },
        ]
    )

    normalized_tables = {
        "orders": pd.DataFrame(
            [
                {
                    "manufacturer_code": "M1",
                    "hospital_code": "H1",
                    "drug_code": "D1",
                    "order_date": pd.Timestamp("2026-07-05"),
                    "order_amount": 500,
                },
                {
                    "manufacturer_code": "M1",
                    "hospital_code": "H1",
                    "drug_code": "D1",
                    "order_date": pd.Timestamp("2026-07-05"),
                    "order_amount": 700,
                },
            ]
        )
    }

    oneshot = _build_oneshot_terminals(features, "2026-07", normalized_tables=normalized_tables)

    assert oneshot["oneshot_id"].tolist() == ["M1|H1|D1"]
    assert oneshot.iloc[0]["report_month"] == "2026-07"
    assert oneshot.iloc[0]["first_purchase_date"] == "2026-07-05"
    assert oneshot.iloc[0]["first_purchase_amount"] == 1200
    assert oneshot.iloc[0]["days_since_first_purchase"] == 26
    assert oneshot.iloc[0]["candidate_type"] == "one_shot"


def _candidate(candidate_id: str, candidate_type: str, probability: float) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "entity_id": candidate_id,
        "tenant_id": "tenant",
        "enterprise_id": "enterprise",
        "manufacturer_code": "M1",
        "hospital_code": "H1",
        "drug_group": "D1",
        "cutoff_month": pd.Timestamp("2026-07-31"),
        "horizon": "H3",
        "candidate_type": candidate_type,
        "churn_probability_H": probability,
        "risk_score": probability,
        "selection_reason": "test",
        "potential_value_level": "known",
        "region_code": "R1",
        "region_display_name": "Region",
    }
