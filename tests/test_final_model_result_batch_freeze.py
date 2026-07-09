from __future__ import annotations

from pathlib import Path

from risk_algorithm_core.monthly_runner import MonthlyRiskRunner
from risk_result_contracts import validate_result_batch
from tests.risk_algorithm_core_test_utils import RUN_CONFIG


def test_final_result_batch_manifest_freezes_detector_and_fact_mode_metadata(tmp_path) -> None:
    runner = MonthlyRiskRunner.from_config_file(RUN_CONFIG)
    runner.config.output_root = str(tmp_path)
    summary = runner.run(use_rule_baseline=False)
    batch_dir = Path(summary["batch_dir"])
    validate_result_batch(batch_dir)

    manifest = (batch_dir / "manifest.json").read_text(encoding="utf-8")

    for required in [
        '"report_type": "monthly"',
        '"detector_tables"',
        '"detector_config_version": "daily_detector_rules_v1"',
        '"detector_score_probability_interpretation": "detector_score_is_not_probability"',
        '"raw_orders_mode_ready": false',
        '"fact_mode_ready": true',
        '"conditional_fact_mode_ready": true',
        '"score_as_of_date"',
    ]:
        assert required in manifest


def test_daily_detector_config_documents_next_run_effective_semantics() -> None:
    config = Path("configs/risk_algorithm_core/daily_detector_rules.yaml").read_text(encoding="utf-8")

    assert "config_version:" in config
    assert "new_config_applies_to_next_detector_run" in config
    assert "historical_results_keep_detector_config_version" in config
    assert "trigger_new_detector_run_for_immediate_effect" in config
