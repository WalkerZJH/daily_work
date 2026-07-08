from __future__ import annotations

import inspect

from tests.test_daily_detector_contract_utils import write_minimal_detector_batch

from risk_model_core.repositories import ParquetRiskResultRepository
import risk_model_core.repositories as repositories


def test_risk_model_core_reads_daily_detector_tables_without_raw_access(tmp_path) -> None:
    batch_dir = write_minimal_detector_batch(tmp_path)
    repo = ParquetRiskResultRepository(batch_dir)

    assert not repo.list_detector_catalog().empty
    assert not repo.list_daily_detector_runs().empty
    assert not repo.list_daily_detector_clues(detector_id="purchase_interval_ipi").empty
    assert not repo.list_high_risk_detector_evidence(risk_entity_id="entity_high").empty

    source = inspect.getsource(repositories)
    forbidden = ["risk_algorithm_core.raw_input", "SQL_DATABASE_URL", "create_engine", "fact_purchase_event"]
    assert not any(token in source for token in forbidden)
