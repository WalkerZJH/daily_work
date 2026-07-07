from __future__ import annotations

from risk_algorithm_core.validation import raw_input_validation_report
from tests.formal_raw_to_batch_test_utils import SCHEMA_MAPPING, require_raw_batch


def test_formal_raw_input_validation_has_no_hard_failures() -> None:
    raw_batch = require_raw_batch()
    report = raw_input_validation_report(raw_batch, SCHEMA_MAPPING)
    assert "status" in report.columns
    assert not report["status"].eq("fail").any()
