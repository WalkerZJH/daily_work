from __future__ import annotations

import pandas as pd
import pytest

from risk_algorithm_core.daily_detector_runner import build_daily_detector_tables
from risk_algorithm_core.detector_component_validation import validate_detector_component_tables
from tests.test_detector_release_a_rules import _all_rule_features


def test_release_a_component_validation_passes_and_marks_business_pending() -> None:
    tables = build_daily_detector_tables(
        risk_entities=pd.DataFrame(),
        scan_features=_all_rule_features(),
        report_month="2026-06",
        run_date="2026-07-16",
        source_raw_batch_id="clean-input",
        detector_ids=["purchase_interval_ipi"],
    )
    report = validate_detector_component_tables(
        tables, detector_id="purchase_interval_ipi", observation_date="2026-07-16"
    )
    assert report["engineering_gate_status"] == "passed"
    assert report["business_gate_status"] == "pending"
    assert report["config_missing_count"] == 0


def test_release_a_component_validation_rejects_config_missing() -> None:
    tables = build_daily_detector_tables(
        risk_entities=pd.DataFrame(),
        scan_features=_all_rule_features(),
        report_month="2026-06",
        run_date="2026-07-16",
        source_raw_batch_id="clean-input",
        detector_ids=["purchase_interval_ipi"],
    )
    tables["daily_detector_results"].loc[:, "eligibility_status"] = "config_missing"
    with pytest.raises(ValueError, match="config_missing"):
        validate_detector_component_tables(
            tables, detector_id="purchase_interval_ipi", observation_date="2026-07-16"
        )
