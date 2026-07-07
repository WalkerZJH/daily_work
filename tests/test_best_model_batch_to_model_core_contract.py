from __future__ import annotations

from risk_algorithm_core.monthly_runner import MonthlyRiskRunner
from risk_model_core.repositories import ParquetRiskResultRepository
from risk_model_core.services import ReportService, RiskQueryService
from risk_model_core.validation import validate_batch
from tests.risk_algorithm_core_test_utils import RUN_CONFIG


def test_best_model_batch_is_readable_by_model_core(tmp_path) -> None:
    runner = MonthlyRiskRunner.from_config_file(RUN_CONFIG)
    runner.config.output_root = str(tmp_path)
    summary = runner.run(use_rule_baseline=False)
    validate_batch(summary["batch_dir"])
    repo = ParquetRiskResultRepository(summary["batch_dir"])
    manifest = repo.manifest()
    assert manifest.customer_facing_probability_service_allowed is False
    assert manifest.auto_dispatch_allowed is False
    assert repo.list_risk_entities().shape[0] == summary["selected_candidate_rows"]
    assert not repo.load_table("risk_cards").empty
    assert not repo.load_table("risk_card_evidence").empty
    assert ReportService(repo).list_reports()
    assert RiskQueryService(repo).list_entities()
