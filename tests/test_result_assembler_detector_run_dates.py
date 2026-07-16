from __future__ import annotations

import json
from pathlib import Path

from risk_algorithm_core.monthly_runner import MonthlyRiskRunner
from tests.risk_algorithm_core_test_utils import RUN_CONFIG


def test_monthly_result_assembler_does_not_publish_daily_detector_tables(tmp_path) -> None:
    runner = MonthlyRiskRunner.from_config_file(RUN_CONFIG)
    runner.config.output_root = str(tmp_path)

    summary = runner.run(use_rule_baseline=False, include_detector_evidence=True)
    batch = Path(summary["batch_dir"])
    manifest = json.loads((batch / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["detector_tables"] == {}
    assert manifest["detector_default_scope"] == "independent_detector_batch"
    assert not (batch / "daily_detector_runs.parquet").exists()
    assert not (batch / "daily_detector_clues.parquet").exists()
