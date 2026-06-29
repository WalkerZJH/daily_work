from __future__ import annotations

from alg.artifacts.paths import (
    get_alive_labels_path,
    get_candidate_entities_dir,
    get_fact_entity_month_path,
    get_fact_purchase_event_path,
    get_feature_table_path,
    get_train_set_dir,
)


def test_fact_paths_do_not_include_cutoff_horizon_or_status(tmp_path):
    event_path = get_fact_purchase_event_path(root=tmp_path, drug_group_source="drug_code")
    month_path = get_fact_entity_month_path(root=tmp_path, drug_group_source="drug_code")
    for path in [event_path, month_path]:
        text = str(path)
        assert "cutoff_" not in text
        assert "H3" not in text
        assert "status" not in text


def test_feature_paths_encode_configuration(tmp_path):
    feature_dir = get_candidate_entities_dir(
        root=tmp_path,
        drug_group_source="drug_code",
        candidate_policy="monitorable",
        max_monitor_gap_months=12,
        start_cutoff="2024-01",
        end_cutoff="2024-12",
    )
    label_path = get_alive_labels_path(
        root=tmp_path,
        drug_group_source="drug_code",
        candidate_policy="monitorable",
        max_monitor_gap_months=12,
        start_cutoff="2024-01",
        end_cutoff="2024-12",
        horizons=(3, 6, 12),
    )
    feature_path = get_feature_table_path(
        root=tmp_path,
        drug_group_source="drug_code",
        candidate_policy="monitorable",
        max_monitor_gap_months=12,
        start_cutoff="2024-01",
        end_cutoff="2024-12",
        include_status_history=False,
    )
    assert "v1_drug_code_monitorable_gap12" in str(feature_dir)
    assert "cutoff_2024-01_2024-12" in str(feature_dir)
    assert label_path.name == "alive_labels__H3_6_12.parquet"
    assert feature_path.name == "feature_table__status0.parquet"


def test_train_set_path_encodes_scope_horizon_and_temporal_split(tmp_path):
    path = get_train_set_dir(
        root=tmp_path,
        drug_group_source="drug_code",
        candidate_policy="monitorable",
        max_monitor_gap_months=12,
        scope="recurring_only",
        horizon=3,
        train_cutoff_start="2022-01",
        train_cutoff_end="2022-12",
        test_cutoff_start="2024-01",
        test_cutoff_end="2024-12",
    )
    text = str(path)
    assert "recurring_only" in text
    assert "H3" in text
    assert "train_2022-01_2022-12__test_2024-01_2024-12" in text
