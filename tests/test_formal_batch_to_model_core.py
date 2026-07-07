from __future__ import annotations

from risk_model_core.repositories import ParquetRiskResultRepository
from risk_model_core.services import ReportService, RiskQueryService
from risk_model_core.validation import validate_batch
from tests.formal_raw_to_batch_test_utils import require_formal_batch


def test_formal_batch_is_readable_by_model_core() -> None:
    batch_dir = require_formal_batch()
    validate_batch(batch_dir)
    repo = ParquetRiskResultRepository(batch_dir)
    assert RiskQueryService(repo).list_entities()
    assert ReportService(repo).list_reports()
    assert repo.manifest().auto_dispatch_allowed is False
    assert repo.manifest().customer_facing_probability_service_allowed is False
