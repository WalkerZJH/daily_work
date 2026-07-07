from __future__ import annotations

from tests.formal_raw_to_batch_test_utils import read_report_csv


def test_formal_raw_to_feature_parity_covers_required_features_without_blocker() -> None:
    parity = read_report_csv("raw_to_feature_parity.csv")
    required = parity[parity["metric"].eq("required_feature_coverage")].iloc[0]
    assert required["status"] == "pass"
    assert float(required["production_value"]) == float(required["reference_value"])
    assert not parity["status"].eq("blocked").any()
