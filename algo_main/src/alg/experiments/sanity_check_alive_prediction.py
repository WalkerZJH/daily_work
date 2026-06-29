"""In-memory sanity check orchestration for alive prediction.

This module intentionally does not train models or save model artifacts.
"""

from __future__ import annotations

import pandas as pd

from alg.facts.demand_profile_builder import build_entity_demand_profile
from alg.facts.entity_month_builder import build_fact_entity_month
from alg.facts.purchase_event_builder import build_fact_purchase_event
from alg.features.alive_prediction_feature_builder import build_alive_prediction_feature_table
from alg.features.cutoff_dataset_builder import build_candidate_entities
from alg.labels.alive_label_builder import build_alive_labels
from alg.metrics.report import (
    build_entity_profile_report,
    build_feature_null_report,
    build_label_distribution_report,
    build_leakage_guardrail_report,
)


def run_alive_prediction_sanity_check(
    model_base: pd.DataFrame,
    drug_group_source: str = "drug_code",
    candidate_policy: str = "monitorable",
    max_monitor_gap_months: int = 12,
    horizons: tuple[int, ...] = (3, 6, 12),
    include_status_history: bool = False,
) -> dict:
    """Build facts, labels, feature skeleton, and report objects in memory."""

    events = build_fact_purchase_event(model_base, drug_group_source=drug_group_source)
    entity_month = build_fact_entity_month(events)
    candidates, candidate_report = build_candidate_entities(
        events,
        policy=candidate_policy,
        max_monitor_gap_months=max_monitor_gap_months,
    )
    demand_profile = build_entity_demand_profile(entity_month, candidates["cutoff_month"].drop_duplicates().tolist())
    labels = build_alive_labels(events, candidates, horizons=horizons)
    features = build_alive_prediction_feature_table(
        entity_month,
        candidates,
        demand_profile=demand_profile,
        include_status_history=include_status_history,
        horizons=horizons,
    )
    return {
        "fact_purchase_event": events,
        "fact_entity_month": entity_month,
        "entity_demand_profile": demand_profile,
        "candidate_entities": candidates,
        "candidate_report": candidate_report,
        "labels": labels,
        "feature_table": features,
        "reports": {
            "entity_profile_report": build_entity_profile_report(candidate_report, events),
            "label_distribution_report": build_label_distribution_report(labels, horizons=horizons),
            "feature_null_report": build_feature_null_report(features),
            "leakage_guardrail_report": build_leakage_guardrail_report(list(features.columns), include_status_history),
        },
    }
