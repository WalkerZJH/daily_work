from __future__ import annotations

from tests.formal_raw_to_batch_test_utils import read_report_csv


def test_formal_result_batch_parity_has_no_blocking_failure() -> None:
    parity = read_report_csv("full_result_batch_parity.csv")
    assert not parity["status"].eq("blocked").any()
    auto_dispatch = parity[parity["metric"].eq("auto_dispatch_allowed_count")].iloc[0]
    assert auto_dispatch["status"] == "pass"
    assert int(auto_dispatch["production_value"]) == 0
