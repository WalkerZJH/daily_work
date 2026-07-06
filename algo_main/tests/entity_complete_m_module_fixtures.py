from __future__ import annotations

import pandas as pd

from alg.tasks.die_prediction import entity_complete_m_module_closure as closure


def sample_candidates() -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "manufacturer_code": ["m1", "m1", "m2", "m2"],
            "hospital_code": ["h1", "h2", "h3", "h4"],
            "drug_group": ["d1", "d2", "d3", "d4"],
            "drug_group_source": ["drug_code", "drug_code", "drug_code", "drug_code"],
            "cutoff_month": ["2025-01-31", "2025-01-31", "2025-01-31", "2025-01-31"],
            "horizon": ["H3", "H3", "H3", "H3"],
            "candidate_policy": ["multi_recall_union_top10", "multi_recall_union_top10", "multi_recall_union_top10", "multi_recall_union_top10"],
            "probability_score": [0.85, 0.75, 0.65, 0.55],
            "frequency_decay_baseline": [0.7, 0.1, 0.8, 0.2],
            "interval_overdue_baseline": [1.4, 0.5, 1.8, 0.3],
            "history_sufficiency_flag": ["history_sufficient", "history_sufficient", "history_sufficient", "history_insufficient"],
            "demand_shape_label": ["smooth", "smooth", "lumpy", "smooth"],
            "one_shot_flag": [False, True, False, False],
            "label_die_H": [1, 0, 1, 0],
            "label_alive_H": [0, 1, 0, 1],
            "label_window_closed": [True, True, True, True],
        }
    )
    df["candidate_id"] = closure.make_candidate_id(df)
    return df


def sample_gate(candidates: pd.DataFrame | None = None) -> pd.DataFrame:
    df = candidates.copy() if candidates is not None else sample_candidates()
    gate = df[
        [
            "candidate_id",
            "manufacturer_code",
            "hospital_code",
            "drug_group",
            "drug_group_source",
            "cutoff_month",
            "horizon",
            "history_sufficiency_flag",
            "demand_shape_label",
        ]
    ].copy()
    gate["churn_probability_H"] = [0.85, 0.75, 0.65, 0.55]
    gate["probability_display_allowed"] = [True, False, False, False]
    gate["probability_display_level"] = ["probability_allowed", "hidden_data_insufficient", "risk_band_only", "hidden_data_insufficient"]
    gate["display_mode"] = ["show_probability", "hide_probability", "show_risk_band", "hide_probability"]
    gate["reason_code"] = ["stable_recurring", "one_shot_not_recurring_churn", "demand_shape_observation", "history_insufficient"]
    gate["model_confidence_bucket"] = ["high", "hidden", "medium", "hidden"]
    gate["choice_set_caveat"] = [True, True, True, True]
    gate["selected_subset_caveat"] = [True, True, True, True]
    gate["manual_review_required"] = [True, True, True, True]
    gate["auto_dispatch_allowed"] = [False, False, False, False]
    return gate


def sample_features() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "manufacturer_code": ["m1", "m1", "m2", "m2"],
            "hospital_code": ["h1", "h2", "h3", "h4"],
            "drug_group": ["d1", "d2", "d3", "d4"],
            "drug_group_source": ["drug_code", "drug_code", "drug_code", "drug_code"],
            "cutoff_month": pd.to_datetime(["2025-01-31", "2025-01-31", "2025-01-31", "2025-01-31"]),
            "purchase_count_asof_cutoff": [12, 1, 8, 2],
            "months_since_last_purchase_asof_cutoff": [6.0, 1.0, 7.0, 2.0],
            "median_purchase_interval_days_asof_cutoff": [90.0, 60.0, 100.0, None],
            "order_count_last_3m_asof_cutoff": [0.0, 1.0, 0.0, 1.0],
            "order_count_last_12m_asof_cutoff": [5.0, 1.0, 4.0, 2.0],
            "terminal_count_last_3m_asof_cutoff": [0.0, 0.0, 0.0, 0.0],
            "terminal_count_last_12m_asof_cutoff": [1.0, 0.0, 1.0, 0.0],
            "purchase_quantity_sum_last_3m_asof_cutoff": [0.0, 1.0, 0.0, 1.0],
            "purchase_quantity_sum_last_12m_asof_cutoff": [10.0, 2.0, 8.0, 3.0],
            "demand_shape_label": ["smooth", "smooth", "lumpy", "smooth"],
            "history_sufficiency_flag": ["history_sufficient", "history_sufficient", "history_sufficient", "history_insufficient"],
        }
    )


def sample_m_pipeline() -> tuple[dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    candidates = sample_candidates()
    gate = sample_gate(candidates)
    features = sample_features()
    m1 = closure.build_m1_closure(candidates, gate)
    m3 = closure.build_m3_survival_refinement(m1["recurring_by_horizon"], features)
    m4 = closure.build_m4_detector_evidence(m1["all_by_horizon"], m3, features)
    m5 = closure.build_m5_status_decision(m1["all_by_horizon"], m3, m4, gate)
    return m1, m3, m4, m5, gate
