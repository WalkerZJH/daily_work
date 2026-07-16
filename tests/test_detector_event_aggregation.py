from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from production_pipeline.materialize_detector_event_aggregates import main as materialize_aggregates
from production_pipeline.run_daily_detector import materialize_detector_component_batch
from risk_algorithm_core.detector_event_aggregation import (
    build_detector_event_aggregates,
    update_detector_event_aggregates,
    validate_detector_event_aggregates,
)


def _events() -> pd.DataFrame:
    rows = [
        ("2025-01-01", "m1", "h1", "d1", "detector_a", True),
        ("2025-01-01", "m1", "h1", "d1", "detector_a", True),
        ("2025-01-02", "m1", "h1", "d1", "detector_a", True),
        ("2025-01-02", "m1", "h1", "d1", "detector_b", True),
        ("2025-01-03", "m1", "h1", "d1", "detector_b", True),
        ("2025-01-02", "m1", "h2", "d2", "detector_b", True),
        ("2025-01-02", "m1", "h2", "d2", "detector_a", False),
    ]
    return pd.DataFrame(rows, columns=[
        "observation_date", "manufacturer_code", "hospital_code", "drug_code",
        "detector_id", "hit_flag",
    ])


def test_event_aggregation_counts_unique_date_detector_events_and_history() -> None:
    aggregates = build_detector_event_aggregates(
        _events(), generated_at="2025-02-01T00:00:00+00:00"
    )
    entity = aggregates.query("manufacturer_code == 'm1' and hospital_code == 'h1'")
    day_two = entity.loc[entity["observation_date"].eq("2025-01-02")].iloc[0]
    day_three = entity.loc[entity["observation_date"].eq("2025-01-03")].iloc[0]

    assert len(entity) == 3
    assert day_two["current_detector_count"] == 2
    assert day_two["current_detector_ids"] == "detector_a|detector_b"
    assert day_two["cumulative_hit_count"] == 3
    assert day_two["cumulative_hit_day_count"] == 2
    assert day_two["historical_detector_ids"] == "detector_a|detector_b"
    assert day_three["current_detector_count"] == 1
    assert day_three["cumulative_hit_count"] == 4
    assert day_three["first_hit_date"] == "2025-01-01"
    assert day_three["last_hit_date"] == "2025-01-03"
    assert validate_detector_event_aggregates(aggregates)["engineering_gate_status"] == "passed"

    state = {}
    streamed = pd.concat([
        update_detector_event_aggregates(
            frame, state, generated_at="2025-02-01T00:00:00+00:00"
        )
        for _, frame in _events().groupby("observation_date", sort=True)
    ], ignore_index=True)
    columns = [column for column in aggregates.columns if column != "generated_at"]
    pd.testing.assert_frame_equal(
        streamed[columns].reset_index(drop=True),
        aggregates[columns].reset_index(drop=True),
        check_dtype=False,
    )


def _snapshot() -> pd.DataFrame:
    return pd.DataFrame([{
        "entity_id": "m1|h1|d1", "tenant_id": "default_tenant",
        "manufacturer_code": "m1", "hospital_code": "h1", "drug_group": "d1",
        "days_since_last_purchase": 60, "historical_interval_median": 20,
        "historical_interval_mad": 5, "purchase_count_total": 12,
        "quantity_ratio": 0.2, "recent_quantity": 2, "baseline_quantity": 10,
        "frequency_ratio": 0.2, "purchase_frequency_baseline": 2,
    }])


def test_materializer_reads_result_drug_code_and_preserves_daily_components(tmp_path: Path) -> None:
    root = tmp_path / "results"
    for date in ["2025-01-01", "2025-01-02"]:
        for detector_id in ["purchase_interval_ipi", "purchase_quantity_trend"]:
            materialize_detector_component_batch(
                snapshot_frame=_snapshot(), output_root=root, observation_date=date,
                detector_id=detector_id, run_id="component-v1", raw_batch_id="clean-fixture",
            )
    source_manifests = sorted(root.glob("detector_run_date=*/detector_id=*/batch_id=*/manifest.json"))
    assert len(source_manifests) == 4

    assert materialize_aggregates([
        "--batch-root", str(root), "--start-date", "2025-01-01",
        "--end-date", "2025-01-02", "--run-id", "aggregate-v1",
        "--detector-id", "purchase_interval_ipi",
        "--detector-id", "purchase_quantity_trend",
    ]) == 0

    batch = root / "detector_event_aggregates" / "batch_id=2025-01-02-aggregate-v1"
    aggregates = pd.read_parquet(batch / "detector_event_aggregates.parquet")
    manifest = json.loads((batch / "manifest.json").read_text(encoding="utf-8"))
    assert list(aggregates["drug_code"].unique()) == ["d1"]
    assert aggregates["current_detector_count"].tolist() == [2, 2]
    assert aggregates["cumulative_hit_count"].tolist() == [2, 4]
    assert manifest["source_table"] == "daily_detector_results.parquet"
    assert manifest["source_component_count"] == 4
    assert manifest["source_components_rewritten"] is False
    assert all(path.is_file() for path in source_manifests)
