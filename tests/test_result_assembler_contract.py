from __future__ import annotations

from risk_algorithm_core.monthly_runner import MonthlyRiskRunner
from risk_model_core.repositories import ParquetRiskResultRepository
from risk_result_contracts import validate_result_batch
from tests.risk_algorithm_core_test_utils import RUN_CONFIG


def test_result_assembler_outputs_monthly_contract(tmp_path) -> None:
    runner = MonthlyRiskRunner.from_config_file(RUN_CONFIG)
    runner.config.output_root = str(tmp_path)
    summary = runner.run(use_rule_baseline=False)
    batch_dir = summary["batch_dir"]
    validate_result_batch(batch_dir)
    repo = ParquetRiskResultRepository(batch_dir)
    assert repo.manifest().report_type == "monthly"
    assert len(repo.list_monthly_reports()) == 1
    assert repo.manifest().auto_dispatch_allowed is False
