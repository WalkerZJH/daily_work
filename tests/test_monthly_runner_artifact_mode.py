from __future__ import annotations

import pytest

from risk_algorithm_core.monthly_runner import MonthlyRiskRunner
from tests.risk_algorithm_core_test_utils import RUN_CONFIG


def test_formal_monthly_runner_uses_best_model_artifact(tmp_path) -> None:
    runner = MonthlyRiskRunner.from_config_file(RUN_CONFIG)
    runner.config.output_root = str(tmp_path)
    summary = runner.run(use_rule_baseline=False)
    assert summary["dry_run_rule_baseline"] is False
    assert str(summary["model_artifact_id"]).startswith("xgboost_small_without_choice_set_")
    assert "report_month=2026-07" in summary["batch_dir"]


def test_formal_monthly_runner_still_fails_without_artifact(tmp_path) -> None:
    runner = MonthlyRiskRunner.from_config_file(RUN_CONFIG)
    runner.config.output_root = str(tmp_path / "out")
    runner.config.artifact_dir = str(tmp_path / "missing_artifact")
    with pytest.raises(FileNotFoundError):
        runner.run(use_rule_baseline=False)
