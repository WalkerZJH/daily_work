from __future__ import annotations

import pandas as pd
import yaml

from alg.experiments.sanity_check_alive_prediction import run_alive_prediction_sanity_check
from alg.facts.demand_profile_builder import build_entity_demand_profile
from alg.facts.entity_month_builder import build_fact_entity_month
from alg.facts.purchase_event_builder import build_fact_purchase_event
from alg.features.alive_prediction_feature_builder import build_alive_prediction_feature_table
from alg.features.cutoff_dataset_builder import build_candidate_entities
from alg.features.value_at_risk import add_business_priority_scores, add_value_at_risk_features
from alg.labels.alive_label_builder import build_alive_labels
from alg.experiments.baseline_rules import (
    add_one_shot_high_value_silence_flags,
    add_recurring_candidate_flag,
    build_model_probability_topk_placeholder,
    build_one_shot_attention_list,
)
from alg.metrics.ranking import cutoff_topk_metrics
from alg.metrics.value_weighted import cutoff_value_metrics


def _model_base() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "row_uid": "a1",
                "order_detail_id": "a-detail-1",
                "manufacturer_code": "m1",
                "hospital_code": "h1",
                "drug_code": "d1",
                "drug_category_code": "cat1",
                "purchase_time": "2024-01-15",
                "raw_sensitive_purchase_quantity": 10,
                "raw_sensitive_purchase_amount": 100,
                "raw_sensitive_delivery_quantity": 10,
                "raw_sensitive_arrival_quantity": 10,
                "order_phase_code": 60,
                "delivery_state_code": 5,
                "order_failure_flag": 0,
                "order_terminal_flag": 1,
                "province_code": "340000",
                "city_code": "340300",
                "county_code": "340323",
                "hospital_level_code": 3,
                "ownership_type_code": 1,
            },
            {
                "row_uid": "a2",
                "order_detail_id": "a-detail-2",
                "manufacturer_code": "m1",
                "hospital_code": "h1",
                "drug_code": "d1",
                "drug_category_code": "cat1",
                "purchase_time": "2024-03-10",
                "raw_sensitive_purchase_quantity": 20,
                "raw_sensitive_purchase_amount": 200,
                "raw_sensitive_delivery_quantity": 0,
                "raw_sensitive_arrival_quantity": 0,
                "order_phase_code": 20,
                "delivery_state_code": 1,
                "order_failure_flag": 0,
                "order_terminal_flag": 0,
                "province_code": "340000",
                "city_code": "340300",
                "county_code": "340323",
                "hospital_level_code": 3,
                "ownership_type_code": 1,
            },
            {
                "row_uid": "a3",
                "order_detail_id": "a-detail-3",
                "manufacturer_code": "m1",
                "hospital_code": "h1",
                "drug_code": "d1",
                "drug_category_code": "cat1",
                "purchase_time": "2024-05-10",
                "raw_sensitive_purchase_quantity": 99,
                "raw_sensitive_purchase_amount": 990,
                "raw_sensitive_delivery_quantity": 0,
                "raw_sensitive_arrival_quantity": 0,
                "order_phase_code": 100,
                "delivery_state_code": 9,
                "order_failure_flag": 1,
                "order_terminal_flag": 1,
                "province_code": "340000",
                "city_code": "340300",
                "county_code": "340323",
                "hospital_level_code": 3,
                "ownership_type_code": 1,
            },
            {
                "row_uid": "b1",
                "order_detail_id": "b-detail-1",
                "manufacturer_code": "m1",
                "hospital_code": "h2",
                "drug_code": "d2",
                "drug_category_code": "cat2",
                "purchase_time": "2024-04-05",
                "raw_sensitive_purchase_quantity": 5,
                "raw_sensitive_purchase_amount": 50,
                "order_phase_code": 60,
                "delivery_state_code": 5,
                "order_failure_flag": 0,
                "order_terminal_flag": 1,
            },
            {
                "row_uid": "c1",
                "order_detail_id": "c-detail-1",
                "manufacturer_code": "m2",
                "hospital_code": "h3",
                "drug_code": "d3",
                "drug_category_code": "cat3",
                "purchase_time": "2023-01-20",
                "raw_sensitive_purchase_quantity": 1,
                "raw_sensitive_purchase_amount": 10,
                "order_phase_code": 60,
                "delivery_state_code": 5,
                "order_failure_flag": 0,
                "order_terminal_flag": 1,
            },
        ]
    )


def test_fact_purchase_event_uses_drug_code_as_default_drug_group_and_keeps_failed_events():
    events = build_fact_purchase_event(_model_base(), drug_group_source="drug_code")
    assert set(events["drug_group"]) == {"d1", "d2", "d3"}
    assert len(events) == 5
    assert events.loc[events["row_uid"] == "a3", "order_failure_flag"].iloc[0] == 1


def test_candidate_entities_exclude_future_entities_and_apply_monitor_gap():
    events = build_fact_purchase_event(_model_base())
    cutoff = pd.Timestamp("2024-03-31")
    all_seen, report = build_candidate_entities(events, cutoff_months=[cutoff], policy="all_seen", max_monitor_gap_months=12)
    monitorable, _ = build_candidate_entities(events, cutoff_months=[cutoff], policy="monitorable", max_monitor_gap_months=12)

    assert ("m1", "h2", "d2") not in set(map(tuple, all_seen[["manufacturer_code", "hospital_code", "drug_group"]].to_numpy()))
    assert ("m2", "h3", "d3") in set(map(tuple, all_seen[["manufacturer_code", "hospital_code", "drug_group"]].to_numpy()))
    assert ("m2", "h3", "d3") not in set(map(tuple, monitorable[["manufacturer_code", "hospital_code", "drug_group"]].to_numpy()))
    assert report.loc[0, "all_seen_entity_count"] == 2
    assert report.loc[0, "monitorable_entity_count"] == 1
    assert report.loc[0, "excluded_by_monitor_gap_count"] == 1


def test_labels_use_months_after_cutoff_only():
    events = build_fact_purchase_event(_model_base())
    candidates, _ = build_candidate_entities(events, cutoff_months=[pd.Timestamp("2024-03-31")], policy="monitorable")
    labels = build_alive_labels(events, candidates, horizons=(1, 2, 3))
    entity = labels[(labels["manufacturer_code"] == "m1") & (labels["hospital_code"] == "h1") & (labels["drug_group"] == "d1")].iloc[0]
    assert entity["label_alive_H1"] == 0
    assert entity["label_die_H1"] == 1
    assert entity["label_alive_H2"] == 1
    assert entity["label_die_H2"] == 0


def test_feature_window_value_at_risk_and_status_history_are_asof_cutoff():
    events = build_fact_purchase_event(_model_base())
    entity_month = build_fact_entity_month(events)
    candidates, _ = build_candidate_entities(events, cutoff_months=[pd.Timestamp("2024-03-31")], policy="monitorable")
    demand = build_entity_demand_profile(
        entity_month,
        cutoff_months=[pd.Timestamp("2024-03-31")],
        cold_start={
            "min_purchase_count_asof_cutoff": 3,
            "min_active_month_count_asof_cutoff": 2,
            "min_months_observed_asof_cutoff": 3,
        },
    )
    features = build_alive_prediction_feature_table(
        entity_month,
        candidates,
        demand_profile=demand,
        include_status_history=True,
        horizons=(3,),
    )
    row = features[(features["manufacturer_code"] == "m1") & (features["hospital_code"] == "h1") & (features["drug_group"] == "d1")].iloc[0]
    assert row["order_count_last_3m_asof_cutoff"] == 2
    assert row["purchase_amount_sum_last_3m_asof_cutoff"] == 300
    assert row["historical_avg_monthly_amount_asof_cutoff"] == 25
    assert row["value_at_risk_amount_raw_H3_asof_cutoff"] == 75
    assert row["value_at_risk_amount_nonnegative_H3_asof_cutoff"] == 75
    assert row["failed_count_last_3m_asof_cutoff"] == 0
    assert bool(row["one_shot_flag"]) is False
    assert "business_priority_score_H3" not in features.columns
    assert "label_die_H3" not in features.columns


def test_business_priority_is_post_processing_only():
    base = pd.DataFrame(
        {
            "churn_probability_H3": [0.5],
            "value_at_risk_amount_nonnegative_H3_asof_cutoff": [100.0],
            "value_at_risk_amount_raw_H3_asof_cutoff": [-100.0],
        }
    )
    scored = add_business_priority_scores(base, horizons=(3,))
    assert scored.loc[0, "business_priority_score_H3"] == 50.0


def test_value_at_risk_raw_and_nonnegative_fields():
    candidates = pd.DataFrame(
        {
            "manufacturer_code": ["m1"],
            "hospital_code": ["h1"],
            "drug_group": ["d1"],
            "cutoff_month": [pd.Timestamp("2024-03-31")],
        }
    )
    entity_month = pd.DataFrame(
        {
            "manufacturer_code": ["m1"],
            "hospital_code": ["h1"],
            "drug_group": ["d1"],
            "purchase_month": [pd.Timestamp("2024-03-31")],
            "purchase_amount_sum": [-120.0],
            "purchase_quantity_sum": [-12.0],
        }
    )
    out = add_value_at_risk_features(candidates, entity_month, horizons=(3,))
    assert out.loc[0, "value_at_risk_amount_raw_H3_asof_cutoff"] == -30.0
    assert out.loc[0, "value_at_risk_amount_nonnegative_H3_asof_cutoff"] == 0.0
    assert bool(out.loc[0, "negative_value_at_risk_amount_flag"]) is True


def test_one_shot_high_value_silence_flags_and_independent_attention_list():
    features = pd.DataFrame(
        {
            "manufacturer_code": ["m1", "m1", "m1"],
            "hospital_code": ["h1", "h2", "h3"],
            "drug_group": ["d1", "d1", "d1"],
            "cutoff_month": [pd.Timestamp("2024-12-31")] * 3,
            "purchase_count_asof_cutoff": [1, 1, 4],
            "active_month_count_asof_cutoff": [1, 1, 3],
            "months_since_first_purchase_asof_cutoff": [6, 6, 20],
            "months_since_last_purchase_asof_cutoff": [4, 1, 2],
            "value_at_risk_amount_nonnegative_H12_asof_cutoff": [1000.0, 10.0, 500.0],
        }
    )
    recurring = add_recurring_candidate_flag(features)
    scored = add_one_shot_high_value_silence_flags(
        recurring,
        {
            "recent_one_shot_lookback_months": 36,
            "min_one_shot_silence_months": 3,
            "high_value_threshold_mode": "quantile_by_group",
            "high_value_quantile": 0.8,
            "group_keys": ["manufacturer_code", "drug_group"],
            "default_priority_score": "value_at_risk_amount_nonnegative_H12_asof_cutoff",
        },
    )
    assert bool(scored.loc[0, "one_shot_flag"]) is True
    assert bool(scored.loc[0, "one_shot_high_value_flag"]) is True
    assert bool(scored.loc[0, "one_shot_high_value_silence_flag"]) is True
    assert "churn_probability_H12" not in scored.columns
    model_topk = build_model_probability_topk_placeholder(scored)
    attention = build_one_shot_attention_list(scored)
    assert set(model_topk["hospital_code"]) == {"h3"}
    assert set(attention["hospital_code"]) == {"h1"}
    assert set(model_topk["hospital_code"]).isdisjoint(set(attention["hospital_code"]))


def test_metrics_compute_topk_within_cutoff_groups():
    df = pd.DataFrame(
        {
            "cutoff_month": ["2024-01-31", "2024-01-31", "2024-02-29", "2024-02-29"],
            "manufacturer_code": ["m1", "m1", "m1", "m1"],
            "label_die_H3": [1, 0, 0, 1],
            "churn_probability_H3": [0.9, 0.1, 0.2, 0.8],
            "business_priority_score_H3": [90, 1, 2, 80],
            "value_at_risk_amount_nonnegative_H3_asof_cutoff": [100, 10, 10, 100],
        }
    )
    probability_metrics = cutoff_topk_metrics(df, "label_die_H3", "churn_probability_H3", k_values=(1,), group_cols=("cutoff_month",))
    value_metrics = cutoff_value_metrics(
        df,
        "label_die_H3",
        "churn_probability_H3",
        "business_priority_score_H3",
        "value_at_risk_amount_nonnegative_H3_asof_cutoff",
        k_values=(1,),
        group_cols=("cutoff_month",),
    )
    assert len(probability_metrics) == 2
    assert probability_metrics["precision_at_k"].tolist() == [1.0, 1.0]
    assert len(value_metrics) == 2
    assert value_metrics["captured_value_at_k"].tolist() == [1.0, 1.0]


def test_topk_metrics_do_not_mix_cutoff_or_manufacturer():
    df = pd.DataFrame(
        {
            "cutoff_month": ["2024-01-31", "2024-01-31", "2024-01-31", "2024-01-31"],
            "manufacturer_code": ["m1", "m1", "m2", "m2"],
            "label_die_H3": [0, 1, 1, 0],
            "churn_probability_H3": [0.9, 0.8, 0.7, 0.6],
        }
    )
    metrics = cutoff_topk_metrics(
        df,
        "label_die_H3",
        "churn_probability_H3",
        k_values=(1,),
        group_cols=("cutoff_month", "manufacturer_code"),
    )
    assert len(metrics) == 2
    by_mfr = dict(zip(metrics["manufacturer_code"], metrics["precision_at_k"]))
    assert by_mfr["m1"] == 0.0
    assert by_mfr["m2"] == 1.0


def test_sanity_check_returns_expected_layers_without_writing_outputs():
    result = run_alive_prediction_sanity_check(_model_base(), horizons=(3,), include_status_history=False)
    for key in [
        "fact_purchase_event",
        "fact_entity_month",
        "entity_demand_profile",
        "candidate_entities",
        "labels",
        "feature_table",
        "reports",
    ]:
        assert key in result
    assert "status_history_features_enabled: False" in result["reports"]["leakage_guardrail_report"]


def test_feature_view_config_records_candidate_and_cold_start_policies():
    config = yaml.safe_load(open("configs/features/alive_prediction_feature_view.yaml", encoding="utf-8"))
    assert config["entity"]["primary_drug_group_source"] == "drug_code"
    assert config["candidate_policy"]["default"] == "monitorable"
    assert config["candidate_policy"]["max_monitor_gap_months"] == 12
    assert config["cold_start"]["min_purchase_count_asof_cutoff"] == 3
    assert "business_priority_score_H3" in config["excluded_columns"]["future_or_label_like"]
    assert any("historical value and scale features may enter" in rule for rule in config["leakage_rules"])
