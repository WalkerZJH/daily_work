from __future__ import annotations

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
