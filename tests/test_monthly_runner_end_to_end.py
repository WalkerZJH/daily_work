from __future__ import annotations

import pytest

from risk_algorithm_core.monthly_runner import MonthlyRiskRunner
from tests.risk_algorithm_core_test_utils import RUN_CONFIG


def test_monthly_runner_end_to_end_with_artifact(tmp_path) -> None:
    runner = MonthlyRiskRunner.from_config_file(RUN_CONFIG)
    runner.config.output_root = str(tmp_path)
    summary = runner.run(use_rule_baseline=False)
    assert summary["report_month"] == "2026-07"
    assert summary["cutoff_date"] == "2026-07-31"
    assert summary["entity_rows"] > 0
    assert summary["feature_rows"] == summary["score_rows"]
    assert summary["selected_candidate_rows"] > 0
    assert str(summary["model_artifact_id"]).startswith("xgboost_small_without_choice_set_")


def test_monthly_runner_dry_run_with_rule_baseline(tmp_path) -> None:
    runner = MonthlyRiskRunner.from_config_file(RUN_CONFIG)
    runner.config.output_root = str(tmp_path)
    summary = runner.run(use_rule_baseline=True)
    assert summary["dry_run_rule_baseline"] is True
    assert summary["model_artifact_id"] == "dry_run_rule_baseline"


def test_formal_monthly_runner_missing_artifact_fails(tmp_path) -> None:
    runner = MonthlyRiskRunner.from_config_file(RUN_CONFIG)
    runner.config.output_root = str(tmp_path / "out")
    runner.config.artifact_dir = str(tmp_path / "missing_artifact")
    with pytest.raises(FileNotFoundError):
        runner.run(use_rule_baseline=False)
