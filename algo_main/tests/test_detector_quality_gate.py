from __future__ import annotations

from pathlib import Path

import pandas as pd

from alg.tasks.die_prediction.mvc_model_package.detector_quality_gate import build_detector_business_readiness_matrix, build_detector_quality_gate


GATE_PATH = Path("data/entity_complete_v2_coverage_expansion/11_business_detector_adaptation/detector_quality_gate.csv")


def test_detector_quality_gate_output_exists() -> None:
    gate = pd.read_csv(GATE_PATH)
    status = dict(zip(gate["detector_name"], gate["gate_status"]))
    frontend = dict(zip(gate["detector_name"], gate["enable_frontend_display"].astype(bool)))

    assert status["terminal_loss_warning"] == "enabled"
    assert status["purchase_interval_overdue_warning"] == "enabled"
    assert status["purchase_frequency_fluctuation_warning"] == "enabled"
    assert status["delayed_response_warning"] == "disabled"
    assert status["low_price_purchase_warning"] == "disabled"
    assert status["order_price_spread_warning"] == "disabled"
    assert status["low_delivery_rate_warning"] == "weak_enabled_review_required"
    assert frontend["low_delivery_rate_warning"] is False


def test_quality_gate_builder_disables_missing_delivery_and_price() -> None:
    readiness = build_detector_business_readiness_matrix()
    gate = build_detector_quality_gate(readiness)
    row = gate.set_index("detector_name")

    assert row.loc["delayed_response_warning", "gate_status"] == "disabled"
    assert row.loc["delayed_response_warning", "missing_rate_ok"] is False or not bool(row.loc["delayed_response_warning", "missing_rate_ok"])
    assert row.loc["low_price_purchase_warning", "gate_status"] == "disabled"
    assert row.loc["wallet_share_decline_warning", "mapping_available"] is False or not bool(row.loc["wallet_share_decline_warning", "mapping_available"])

