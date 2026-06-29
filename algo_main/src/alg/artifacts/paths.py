"""Stable artifact paths for alive prediction data layers."""

from __future__ import annotations

from pathlib import Path


def _root(root: str | Path = "data") -> Path:
    return Path(root)


def feature_view_slug(
    *,
    version: str = "v1",
    drug_group_source: str = "drug_code",
    candidate_policy: str = "monitorable",
    max_monitor_gap_months: int = 12,
) -> str:
    return f"{version}_{drug_group_source}_{candidate_policy}_gap{max_monitor_gap_months}"


def cutoff_slug(start_cutoff: str, end_cutoff: str) -> str:
    return f"cutoff_{start_cutoff}_{end_cutoff}"


def horizon_slug(horizons: list[int] | tuple[int, ...]) -> str:
    return "H" + "_".join(str(horizon) for horizon in horizons)


def status_slug(include_status_history: bool) -> str:
    return "status1" if include_status_history else "status0"


def get_fact_purchase_event_path(
    *,
    root: str | Path = "data",
    drug_group_source: str = "drug_code",
) -> Path:
    return _root(root) / "04_facts" / "alive_prediction" / f"fact_purchase_event__{drug_group_source}.parquet"


def get_fact_entity_month_path(
    *,
    root: str | Path = "data",
    drug_group_source: str = "drug_code",
) -> Path:
    return _root(root) / "04_facts" / "alive_prediction" / f"fact_entity_month__{drug_group_source}.parquet"


def get_candidate_entities_dir(
    *,
    root: str | Path = "data",
    version: str = "v1",
    drug_group_source: str = "drug_code",
    candidate_policy: str = "monitorable",
    max_monitor_gap_months: int = 12,
    start_cutoff: str,
    end_cutoff: str,
) -> Path:
    return (
        _root(root)
        / "05_features"
        / "alive_prediction"
        / feature_view_slug(
            version=version,
            drug_group_source=drug_group_source,
            candidate_policy=candidate_policy,
            max_monitor_gap_months=max_monitor_gap_months,
        )
        / cutoff_slug(start_cutoff, end_cutoff)
    )


def get_feature_table_dir(**kwargs) -> Path:
    return get_candidate_entities_dir(**kwargs)


def get_alive_labels_path(
    *,
    root: str | Path = "data",
    version: str = "v1",
    drug_group_source: str = "drug_code",
    candidate_policy: str = "monitorable",
    max_monitor_gap_months: int = 12,
    start_cutoff: str,
    end_cutoff: str,
    horizons: list[int] | tuple[int, ...] = (3, 6, 12),
) -> Path:
    return (
        get_candidate_entities_dir(
            root=root,
            version=version,
            drug_group_source=drug_group_source,
            candidate_policy=candidate_policy,
            max_monitor_gap_months=max_monitor_gap_months,
            start_cutoff=start_cutoff,
            end_cutoff=end_cutoff,
        )
        / f"alive_labels__{horizon_slug(horizons)}.parquet"
    )


def get_feature_table_path(
    *,
    root: str | Path = "data",
    version: str = "v1",
    drug_group_source: str = "drug_code",
    candidate_policy: str = "monitorable",
    max_monitor_gap_months: int = 12,
    start_cutoff: str,
    end_cutoff: str,
    include_status_history: bool = False,
) -> Path:
    return (
        get_feature_table_dir(
            root=root,
            version=version,
            drug_group_source=drug_group_source,
            candidate_policy=candidate_policy,
            max_monitor_gap_months=max_monitor_gap_months,
            start_cutoff=start_cutoff,
            end_cutoff=end_cutoff,
        )
        / f"feature_table__{status_slug(include_status_history)}.parquet"
    )


def get_train_set_dir(
    *,
    root: str | Path = "data",
    version: str = "v1",
    drug_group_source: str = "drug_code",
    candidate_policy: str = "monitorable",
    max_monitor_gap_months: int = 12,
    scope: str,
    horizon: int,
    train_cutoff_start: str | None = None,
    train_cutoff_end: str | None = None,
    test_cutoff_start: str | None = None,
    test_cutoff_end: str | None = None,
) -> Path:
    base = (
        _root(root)
        / "06_train_sets"
        / "alive_prediction"
        / feature_view_slug(
            version=version,
            drug_group_source=drug_group_source,
            candidate_policy=candidate_policy,
            max_monitor_gap_months=max_monitor_gap_months,
        )
        / scope
        / f"H{horizon}"
    )
    if train_cutoff_start and train_cutoff_end and test_cutoff_start and test_cutoff_end:
        return base / f"train_{train_cutoff_start}_{train_cutoff_end}__test_{test_cutoff_start}_{test_cutoff_end}"
    return base


def get_output_dir(*, root: str | Path = "data", output_type: str) -> Path:
    return _root(root) / "07_outputs" / "alive_prediction" / output_type
