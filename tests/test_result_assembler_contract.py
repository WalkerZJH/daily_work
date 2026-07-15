from __future__ import annotations

import json
from pathlib import Path

import pytest

import risk_algorithm_core.result_assembler as result_assembler
from risk_algorithm_core.monthly_runner import MonthlyRiskRunner
from risk_model_core.repositories import ParquetRiskResultRepository
from risk_result_contracts import validate_result_batch
from risk_result_contracts.schemas import RISK_ENTITY_HORIZON_PROFILE_REQUIRED_COLUMNS
from tests.risk_algorithm_core_test_utils import RUN_CONFIG


def test_result_assembler_outputs_monthly_contract(tmp_path) -> None:
    runner = MonthlyRiskRunner.from_config_file(RUN_CONFIG)
    runner.config.output_root = str(tmp_path)
    summary = runner.run(use_rule_baseline=False)
    batch_dir = summary["batch_dir"]
    validate_result_batch(batch_dir)
    repo = ParquetRiskResultRepository(batch_dir)
    assert repo.manifest().report_type == "monthly"
    assert repo.manifest().schema_version == "risk_result_batch_monthly_v2"
    assert len(repo.list_monthly_reports()) == 1
    assert repo.manifest().auto_dispatch_allowed is False
    profiles = repo.load_table("risk_entity_horizon_profiles")
    assert set(RISK_ENTITY_HORIZON_PROFILE_REQUIRED_COLUMNS).issubset(profiles.columns)
    assert {"H3", "H6", "H12"}.issubset(set(profiles["horizon"].astype(str)))
    assert profiles["involved_amount_source"].astype(str).str.match(r"purchase_amount_sum_last_(3|6|12)m_asof_cutoff").all()
    assert not profiles["involved_amount_source"].astype(str).str.contains("total|full_history|all_history", case=False).any()


def test_result_assembler_validates_monthly_core_without_detector_tables(tmp_path) -> None:
    runner = MonthlyRiskRunner.from_config_file(RUN_CONFIG)
    runner.config.output_root = str(tmp_path)

    summary = runner.run(use_rule_baseline=False, include_detector_evidence=False)
    batch_dir = Path(summary["batch_dir"])

    validate_result_batch(batch_dir)
    assert not (batch_dir / "daily_detector_clues.parquet").exists()
    assert not (batch_dir / "high_risk_detector_evidence.parquet").exists()


def test_main_only_batch_context_declares_detector_as_independent(tmp_path) -> None:
    from scripts.generate_multi_month_formal_batches import update_manifest_and_context

    runner = MonthlyRiskRunner.from_config_file(RUN_CONFIG)
    runner.config.output_root = str(tmp_path)
    summary = runner.run(use_rule_baseline=False, include_detector_evidence=False)
    batch_dir = Path(summary["batch_dir"])

    update_manifest_and_context(
        batch_dir=batch_dir,
        observation_date="2025-12-31",
        runtime_profile_summary={"monthly_probability_total_seconds": 1.0, "detector_total_seconds": 0.0},
    )

    manifest = json.loads((batch_dir / "manifest.json").read_text(encoding="utf-8"))
    context = json.loads((batch_dir / "report_context.json").read_text(encoding="utf-8"))
    assert manifest["detector_tables"] == {}
    assert manifest["detector_default_scope"] == "independent_detector_batch"
    assert manifest["full_recurring_count"] == manifest["persisted_recurring_count"]
    assert context["detector_run_dates"] == []
    assert context["monthly_candidate_batch_available"] is True


def test_multi_month_generator_can_publish_main_batch_without_running_detector(tmp_path) -> None:
    from scripts.generate_multi_month_formal_batches import run_profiled_month

    runner = MonthlyRiskRunner.from_config_file(RUN_CONFIG)
    runner.config.output_root = str(tmp_path)

    result = run_profiled_month(runner.config, "2026-08-01", include_detector_evidence=False)

    batch_dir = Path(result["summary"]["batch_dir"])
    assert result["summary"]["detector_runs"] == 0
    assert not (batch_dir / "daily_detector_runs.parquet").exists()
    assert json.loads((batch_dir / "manifest.json").read_text(encoding="utf-8"))["detector_tables"] == {}


def test_result_assembler_does_not_publish_partial_batch_when_a_table_write_fails(tmp_path, monkeypatch) -> None:
    runner = MonthlyRiskRunner.from_config_file(RUN_CONFIG)
    runner.config.output_root = str(tmp_path)
    actual_write = result_assembler.write_production_parquet
    write_count = 0

    def fail_on_fourth_table(frame, output_path, **kwargs):
        nonlocal write_count
        write_count += 1
        if write_count == 4:
            raise RuntimeError("simulated table write failure")
        return actual_write(frame, output_path, **kwargs)

    monkeypatch.setattr(result_assembler, "write_production_parquet", fail_on_fourth_table)

    with pytest.raises(RuntimeError, match="simulated table write failure"):
        runner.run(use_rule_baseline=False, include_detector_evidence=False)

    final_batch = tmp_path / "report_month=2026-07" / "batch_id=2026-07-monthly-risk-algorithm-fixture"
    staging_batches = list(final_batch.parent.glob(".batch_id=2026-07-monthly-risk-algorithm-fixture.staging-*"))
    assert not final_batch.exists()
    assert len(staging_batches) == 1
    assert not (staging_batches[0] / "manifest.json").exists()
