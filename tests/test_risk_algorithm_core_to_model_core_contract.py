from __future__ import annotations

from risk_algorithm_core.monthly_runner import MonthlyRiskRunner
from risk_model_core.page_payload_builder import PagePayloadBuilder
from risk_model_core.repositories import ParquetRiskResultRepository
from risk_model_core.validation import validate_batch
from tests.risk_algorithm_core_test_utils import RUN_CONFIG


def test_algorithm_core_batch_is_readable_by_model_core(tmp_path) -> None:
    runner = MonthlyRiskRunner.from_config_file(RUN_CONFIG)
    runner.config.output_root = str(tmp_path)
    summary = runner.run(use_rule_baseline=False)
    validate_batch(summary["batch_dir"])
    repo = ParquetRiskResultRepository(summary["batch_dir"])
    entities = repo.list_risk_entities()
    assert not entities.empty
    payload = PagePayloadBuilder(repo).build_clues_payload()
    assert len(payload["items"]) == len(entities)
    assert repo.manifest().customer_facing_probability_service_allowed is False
