from __future__ import annotations

import pytest

from risk_algorithm_core.config import load_run_config, resolve_report_month_and_cutoff
from tests.risk_algorithm_core_test_utils import RUN_CONFIG


def test_previous_month_cutoff_resolution() -> None:
    report_month, cutoff = resolve_report_month_and_cutoff("auto_previous_month", "2026-08-05")
    assert report_month == "2026-07"
    assert cutoff == "2026-07-31"


def test_monthly_run_config_loads() -> None:
    config = load_run_config(RUN_CONFIG)
    assert config.report_type == "monthly"
    assert config.primary_horizon == "H6"
    assert config.resolved_report_month == "2026-07"
    assert config.safety["auto_dispatch_allowed"] is False


def test_monthly_run_config_rejects_auto_dispatch_true(tmp_path) -> None:
    cfg = tmp_path / "bad.yaml"
    cfg.write_text("safety:\n  auto_dispatch_allowed: true\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_run_config(cfg)
