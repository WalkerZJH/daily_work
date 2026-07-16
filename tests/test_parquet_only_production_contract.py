from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from production_pipeline.refresh_entity_display_lookup import main as refresh_lookup_main
from production_pipeline.rebuild_observation_registry import main as rebuild_registry_main
from production_pipeline.run_daily_detector import main as run_daily_detector_main
from risk_model_core.repositories import ParquetRiskResultRepository
from risk_model_core.repositories import resolve_observation_context_from_rows
from risk_result_contracts import ProductionParquetWriteError, write_production_parquet


FORMAL_ROOT = Path("data/project_result_batches")


def test_formal_project_result_batches_are_parquet_only() -> None:
    assert FORMAL_ROOT.exists()
    assert list(FORMAL_ROOT.rglob("*.csv")) == []
    for manifest_path in FORMAL_ROOT.glob("report_month=*/batch_id=*/manifest.json"):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["data_backend"] == "parquet"
        assert all(str(path).endswith(".parquet") for path in (manifest.get("detector_tables") or {}).values())
        horizon = manifest.get("horizon_profile_table") or {}
        assert str(horizon.get("path", "")).endswith(".parquet")
        lookup = manifest.get("entity_display_lookup") or {}
        assert str(lookup.get("path", "")).endswith(".parquet")


def test_writer_failure_does_not_create_csv_or_half_file(tmp_path, monkeypatch) -> None:
    import risk_result_contracts.parquet_io as parquet_io

    def fail_write(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(parquet_io.pq, "write_table", fail_write)
    target = tmp_path / "risk_entities.parquet"
    with pytest.raises(ProductionParquetWriteError):
        write_production_parquet(pd.DataFrame([{"id": "a"}]), target)
    assert not target.exists()
    assert list(tmp_path.glob("*.csv")) == []
    assert list(tmp_path.glob("*.tmp")) == []


def test_writer_persists_mixed_blank_and_numeric_evidence_values(tmp_path) -> None:
    target = tmp_path / "risk_card_evidence.parquet"
    frame = pd.DataFrame(
        {
            "business_metric_value": ["", 1.25],
            "source_feature_value": ["", 1.25],
        }
    )

    write_production_parquet(frame, target)

    persisted = pd.read_parquet(target)
    assert pd.isna(persisted["business_metric_value"].iloc[0])
    assert persisted["business_metric_value"].iloc[1] == 1.25
    assert pd.isna(persisted["source_feature_value"].iloc[0])
    assert persisted["source_feature_value"].iloc[1] == 1.25


def test_repository_does_not_fallback_to_csv(tmp_path) -> None:
    write_manifest(tmp_path)
    pd.DataFrame([{"risk_entity_id": "r1"}]).to_csv(tmp_path / "risk_entities.csv", index=False)
    repo = ParquetRiskResultRepository(tmp_path)
    with pytest.raises(FileNotFoundError):
        repo.load_table("risk_entities")


def test_display_lookup_refresh_keeps_core_hashes_unchanged(tmp_path) -> None:
    batch = make_minimal_stage_batch(tmp_path)
    assert refresh_lookup_main(["--batch-dir", str(batch)]) == 0
    status = json.loads((batch / "entity_display_lookup_refresh_status.json").read_text(encoding="utf-8"))
    assert status["immutable_hashes_unchanged"] is True


def test_daily_detector_rejects_the_removed_monthly_batch_output_parameter(tmp_path, capsys) -> None:
    batch = make_minimal_stage_batch(tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        run_daily_detector_main([
            "--batch-dir", str(batch), "--raw-batch-dir", str(tmp_path / "raw"),
            "--observation-date", "2025-12-05", "--run-id", "fixture",
            "--detector-id", "purchase_interval_ipi",
            "--detector-config-profiles", str(tmp_path / "profiles.parquet"),
        ])
    assert exc_info.value.code == 2
    assert "unrecognized arguments: --batch-dir" in capsys.readouterr().err


def test_registry_rebuild_uses_existing_parquet_batches(tmp_path) -> None:
    root = tmp_path / "result_batches"
    batch = root / "report_month=2025-11" / "batch_id=test"
    make_minimal_stage_batch(batch)
    assert rebuild_registry_main(["--batch-root", str(root)]) == 0
    assert (root / "available_observation_contexts.parquet").exists()
    assert (root / "observation_registry.parquet").exists()
    assert (root / "manufacturer_observation_registry.parquet").exists()
    registry = pd.read_parquet(root / "manufacturer_observation_registry.parquet")
    assert registry["manufacturer_code"].tolist() == ["m1"]
    assert registry["observation_date"].tolist() == ["2025-12-05"]


def test_registry_pairs_separate_monthly_and_detector_batches(tmp_path) -> None:
    root = tmp_path / "result_batches"
    detector_batch = root / "detector_run_date=2025-12-05" / "batch_id=daily-detector-fact-v1"
    make_minimal_stage_batch(detector_batch)
    detector_manifest_path = detector_batch / "manifest.json"
    detector_manifest = json.loads(detector_manifest_path.read_text(encoding="utf-8"))
    detector_manifest.update(
        {
            "report_type": "daily_detector",
            "observation_date": "2025-12-05",
            "detector_run_date": "2025-12-05",
        }
    )
    detector_manifest_path.write_text(json.dumps(detector_manifest), encoding="utf-8")
    monthly_batch = root / "report_month=2025-11" / "batch_id=full-recurring-v2"
    make_minimal_stage_batch(monthly_batch)
    for name in ["daily_detector_runs", "daily_detector_clues"]:
        (monthly_batch / f"{name}.parquet").unlink()

    assert rebuild_registry_main(["--batch-root", str(root)]) == 0

    context = pd.read_parquet(root / "available_observation_contexts.parquet").iloc[0]
    assert context["probability_batch_dir"].endswith("batch_id=full-recurring-v2")
    assert context["detector_batch_dir"].endswith("batch_id=daily-detector-fact-v1")
    assert bool(context["probability_batch_available"]) is True
    assert bool(context["detector_run_available"]) is True


def test_observation_context_preserves_separate_detector_batch_path() -> None:
    context = resolve_observation_context_from_rows(
        pd.DataFrame(
            [
                {
                    "observation_date": "2026-01-01",
                    "probability_report_month": "2025-12",
                    "probability_batch_id": "full-recurring-v2",
                    "probability_batch_dir": "monthly-batch",
                    "probability_batch_available": True,
                    "detector_run_date": "2026-01-01",
                    "detector_run_id": "daily-detector-v1",
                    "detector_batch_id": "formal-v2",
                    "detector_batch_dir": "detector-batch",
                    "detector_run_available": True,
                    "primary_horizon": "H6",
                    "available_horizons": "H3;H6;H12",
                }
            ]
        ),
        observation_date="2026-01-01",
    )

    assert context["probability_batch_dir"] == "monthly-batch"
    assert context["detector_batch_dir"] == "detector-batch"


def make_minimal_stage_batch(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    write_manifest(path)
    write_production_parquet(pd.DataFrame([{"risk_entity_id": "r1", "manufacturer_code": "m1"}]), path / "risk_entities.parquet")
    write_production_parquet(pd.DataFrame([{"risk_entity_id": "r1", "horizon": "H3"}]), path / "risk_entity_horizon_profiles.parquet")
    write_production_parquet(pd.DataFrame([{"monthly_report_id": "mr1"}]), path / "monthly_reports.parquet")
    write_production_parquet(pd.DataFrame([{"detector_run_id": "dr1", "run_date": "2025-12-05"}]), path / "daily_detector_runs.parquet")
    write_production_parquet(pd.DataFrame([{"detector_clue_id": "dc1", "run_date": "2025-12-05"}]), path / "daily_detector_clues.parquet")
    write_production_parquet(pd.DataFrame([{"detector_id": "purchase_interval_ipi"}]), path / "detector_catalog.parquet")
    write_production_parquet(pd.DataFrame([{"risk_entity_id": "r1"}]), path / "high_risk_detector_evidence.parquet")
    write_production_parquet(
        pd.DataFrame([{"manufacturer_code": "m1", "manufacturer_display_name": "Manufacturer One"}]),
        path / "entity_display_lookup.parquet",
    )
    return path


def write_manifest(path: Path) -> None:
    manifest = {
        "batch_id": "test",
        "report_type": "monthly",
        "report_month": "2025-11",
        "report_date": "2025-12-05",
        "score_cutoff_month": "2025-11",
        "primary_horizon": "H3",
        "available_horizons": ["H3"],
        "schema_version": "risk_result_batch_monthly_v2",
        "data_backend": "parquet",
        "allowed_usage": ["internal_diagnostic"],
        "forbidden_usage": ["auto_dispatch"],
        "customer_facing_probability_service_allowed": False,
        "auto_dispatch_allowed": False,
        "proof_case_report_allowed": False,
        "caveats": [],
        "detector_tables": {
            "detector_catalog": "detector_catalog.parquet",
            "daily_detector_runs": "daily_detector_runs.parquet",
            "daily_detector_clues": "daily_detector_clues.parquet",
            "high_risk_detector_evidence": "high_risk_detector_evidence.parquet",
        },
    }
    path.mkdir(parents=True, exist_ok=True)
    (path / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
