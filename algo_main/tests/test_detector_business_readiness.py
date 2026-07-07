from __future__ import annotations

from pathlib import Path

import pandas as pd


REPORT_DIR = Path("reports/entity_complete_v2_coverage_expansion/15_business_detector_adaptation")


def test_detector_readiness_matrix_exists_and_has_expected_statuses() -> None:
    matrix = pd.read_csv(REPORT_DIR / "detector_business_readiness_matrix.csv")
    status = dict(zip(matrix["detector_name"], matrix["implementation_status"]))

    assert status["terminal_loss_warning"] == "enabled_rule_v1"
    assert status["purchase_interval_overdue_warning"] == "enabled_rule_v1"
    assert status["purchase_frequency_fluctuation_warning"] == "enabled_rule_v1"
    assert status["purchase_quantity_fluctuation_warning"] == "weak_enabled_review_required"
    assert status["new_terminal_detection"] == "enabled_rule_v1"
    assert status["delayed_response_warning"] == "deferred_missing_data"
    assert status["sku_narrowing_warning"] == "deferred_missing_mapping"
    assert status["wallet_share_decline_warning"] == "deferred_missing_mapping"


def test_readiness_summary_states_delivery_time_skipped() -> None:
    text = (REPORT_DIR / "detector_business_readiness_summary.md").read_text(encoding="utf-8")

    assert "detector 没有全部完成" in text
    assert "delivery_time" in text
    assert "arrival_time" in text
    assert "配送商责任结论" in text

