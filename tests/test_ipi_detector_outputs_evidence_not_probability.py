from __future__ import annotations

from tests.test_daily_detector_contract_utils import build_detector_fixture

from risk_algorithm_core.daily_detector_runner import build_daily_detector_tables


def test_ipi_detector_outputs_evidence_not_probability() -> None:
    tables = build_daily_detector_tables(**build_detector_fixture())
    clues = tables["daily_detector_clues"]
    ipi = clues[clues["detector_id"].eq("purchase_interval_ipi")]

    assert not ipi.empty
    assert "detector_score" in ipi.columns
    assert "detector_probability" not in ipi.columns
    assert ipi["detector_score"].between(0, 100).all()
    assert ipi["monthly_risk_probability"].between(0, 1).dropna().all()
    assert ipi["evidence_text"].str.contains("概率", regex=False).sum() == 0
