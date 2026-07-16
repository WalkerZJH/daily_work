from __future__ import annotations

import pandas as pd
import pytest
from pathlib import Path

from production_pipeline.run_daily_detector import materialize_detector_component_batch
from production_pipeline.run_daily_detector import _validate_windows_readable_publish_path
from production_pipeline.rebuild_observation_registry import main as rebuild_observation_registry
from risk_model_core.repositories import CompositeDetectorResultRepository


def _snapshot() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "entity_id": "m1|h1|d1",
                "tenant_id": "default_tenant",
                "manufacturer_code": "m1",
                "hospital_code": "h1",
                "drug_group": "d1",
                "days_since_last_purchase": 60,
                "historical_interval_median": 20,
                "historical_interval_mad": 5,
                "purchase_count_total": 12,
                "quantity_ratio": 0.2,
                "recent_quantity": 2,
                "baseline_quantity": 10,
                "frequency_ratio": 0.2,
                "purchase_frequency_baseline": 2,
            }
        ]
    )


def test_detector_components_publish_and_compose_independently(tmp_path) -> None:
    root = tmp_path / "results"
    common = {
        "snapshot_frame": _snapshot(),
        "output_root": root,
        "observation_date": "2025-12-31",
        "run_id": "component-v1",
        "raw_batch_id": "raw-fixture",
    }
    interval = materialize_detector_component_batch(detector_id="purchase_interval_ipi", **common)
    quantity = materialize_detector_component_batch(detector_id="purchase_quantity_trend", **common)

    date_partition = root / "detector_run_date=2025-12-31"
    repository = CompositeDetectorResultRepository(date_partition)
    assert set(repository.list_detector_catalog()["detector_id"]) == {
        "purchase_interval_ipi",
        "purchase_quantity_trend",
    }
    assert set(repository.list_daily_detector_runs()["detector_id"]) == {
        "purchase_interval_ipi",
        "purchase_quantity_trend",
    }
    assert set(repository.list_daily_detector_clues()["detector_id"]) == {
        "purchase_interval_ipi",
        "purchase_quantity_trend",
    }
    assert "detector_id=purchase_interval_ipi" in str(interval["batch_dir"])
    assert "detector_id=purchase_quantity_trend" in str(quantity["batch_dir"])

    materialize_detector_component_batch(
        snapshot_frame=_snapshot(),
        output_root=root,
        observation_date="2025-12-31",
        detector_id="purchase_interval_ipi",
        run_id="component-z2",
        raw_batch_id="raw-fixture",
    )
    refreshed = CompositeDetectorResultRepository(date_partition)
    interval_batches = [path for path in refreshed.component_batch_dirs if "purchase_interval_ipi" in str(path)]
    quantity_batches = [path for path in refreshed.component_batch_dirs if "purchase_quantity_trend" in str(path)]
    assert len(interval_batches) == len(quantity_batches) == 1
    assert interval_batches[0].name.endswith("component-z2")
    assert quantity_batches[0].name.endswith("component-v1")

    assert rebuild_observation_registry(["--batch-root", str(root)]) == 0
    registry = pd.read_parquet(root / "observation_registry.parquet")
    assert len(registry) == 1
    assert registry.iloc[0]["detector_batch_dir"].endswith("detector_run_date=2025-12-31")


def test_model_core_keeps_detector_and_monthly_production_runbook() -> None:
    runbook = Path("risk_model_core/DETECTOR_PRODUCTION_BOUNDARY.md").read_text(encoding="utf-8")
    assert "Updating a Detector does not require rerunning monthly prediction" in runbook
    assert "Never run every Detector for every date" in runbook
    assert "--detector-id <detector_id>" in runbook
    assert "CompositeDetectorResultRepository" in runbook
    for obsolete in [
        "project/docs/backend_model_contract_blocker.md",
        "project/docs/frontend_detector_api_adaptation.md",
        "front_end/docs/frontend_recovery_and_api_adaptation_plan.md",
        "reports/parquet_and_pipeline_boundary_completion.md",
    ]:
        assert not Path(obsolete).exists()


def test_windows_publish_path_gate_rejects_unreadable_final_path(monkeypatch, tmp_path) -> None:
    import production_pipeline.run_daily_detector as module

    monkeypatch.setattr(module.os, "name", "nt")
    too_long = tmp_path.joinpath(*(["very-long-detector-segment"] * 12))
    with pytest.raises(ValueError, match="too long"):
        _validate_windows_readable_publish_path(too_long)


def test_repeated_detector_components_reuse_one_snapshot_record_conversion(monkeypatch) -> None:
    from risk_algorithm_core.daily_detector_runner import build_daily_detector_tables

    snapshot = _snapshot()
    original = pd.DataFrame.to_dict
    conversions = 0

    def counted_to_dict(frame, *args, **kwargs):
        nonlocal conversions
        orient = kwargs.get("orient", args[0] if args else "dict")
        if frame is snapshot and orient == "records":
            conversions += 1
        return original(frame, *args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "to_dict", counted_to_dict)
    for detector_id in ["purchase_interval_ipi", "purchase_quantity_trend"]:
        build_daily_detector_tables(
            risk_entities=pd.DataFrame(), scan_features=snapshot, report_month="2025-12",
            run_date="2025-12-31", source_raw_batch_id="clean-fixture",
            detector_ids=[detector_id],
        )
    assert conversions == 1
