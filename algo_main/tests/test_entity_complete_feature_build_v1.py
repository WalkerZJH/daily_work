from __future__ import annotations

import pandas as pd

from alg.facts.entity_month_builder import build_fact_entity_month
from alg.facts.purchase_event_builder import build_fact_purchase_event
from alg.features.alive_prediction_feature_builder import build_alive_prediction_feature_table
from alg.features.cutoff_dataset_builder import build_candidate_entities
from alg.labels.alive_label_builder import build_alive_labels
from alg.tasks.die_prediction.entity_complete_rebuild import add_feature_policy_columns, add_label_closure
from alg.tasks.die_prediction.entity_complete_rebuild import add_hospital_drug_choice_context_features


def _model_base() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "row_uid": ["r1", "r2", "r3"],
            "order_detail_id": ["o1", "o2", "o3"],
            "manufacturer_code": ["m1", "m1", "m1"],
            "hospital_code": ["h1", "h1", "h1"],
            "drug_code": ["d1", "d1", "d1"],
            "purchase_time": pd.to_datetime(["2024-01-10", "2024-03-10", "2024-07-10"]),
            "raw_sensitive_purchase_quantity": [1.0, 1.0, 1.0],
            "raw_sensitive_purchase_amount": [10.0, 10.0, 10.0],
        }
    )


def test_asof_features_do_not_use_future_purchase() -> None:
    events = build_fact_purchase_event(_model_base())
    entity_month = build_fact_entity_month(events)
    candidates, _ = build_candidate_entities(events, cutoff_months=[pd.Timestamp("2024-01-31")], policy="all_seen")

    features = build_alive_prediction_feature_table(entity_month, candidates)

    assert int(features["purchase_count_asof_cutoff"].iloc[0]) == 1


def test_label_window_closure_by_horizon() -> None:
    events = build_fact_purchase_event(_model_base())
    candidates, _ = build_candidate_entities(events, cutoff_months=[pd.Timestamp("2024-01-31")], policy="all_seen")
    labels = add_label_closure(build_alive_labels(events, candidates), events)

    assert bool(labels["label_window_closed_H3"].iloc[0]) is True
    assert bool(labels["label_window_closed_H12"].iloc[0]) is False


def test_history_sufficiency_and_demand_shape_columns_exist() -> None:
    events = build_fact_purchase_event(_model_base())
    entity_month = build_fact_entity_month(events)
    candidates, _ = build_candidate_entities(events, cutoff_months=[pd.Timestamp("2024-03-31")], policy="all_seen")
    features = add_feature_policy_columns(build_alive_prediction_feature_table(entity_month, candidates))

    assert "history_sufficiency_flag" in features
    assert "demand_shape_label" in features


def test_hospital_drug_choice_context_features_capture_competitor_orders() -> None:
    entity_month = pd.DataFrame(
        {
            "manufacturer_code": ["m1", "m2"],
            "hospital_code": ["h1", "h1"],
            "drug_group": ["d1", "d1"],
            "purchase_month": pd.to_datetime(["2024-01-31", "2024-01-31"]),
            "order_count": [2, 3],
        }
    )
    features = pd.DataFrame(
        {
            "manufacturer_code": ["m1"],
            "hospital_code": ["h1"],
            "drug_group": ["d1"],
            "cutoff_month": [pd.Timestamp("2024-01-31")],
            "purchase_count_asof_cutoff": [2],
            "order_count_last_12m_asof_cutoff": [2],
            "order_count_last_3m_asof_cutoff": [2],
        }
    )

    out = add_hospital_drug_choice_context_features(features, entity_month)

    assert out["hospital_drug_active_manufacturer_count_asof_cutoff"].iloc[0] == 2
    assert out["competitor_order_count_asof_cutoff"].iloc[0] == 3
    assert bool(out["manufacturer_substitution_context_available"].iloc[0]) is True
