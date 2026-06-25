from __future__ import annotations

from datetime import date

import pandas as pd

from app.core.config import load_config
from app.detectors.registry import DETECTOR_META
from app.schemas.api import DetectorRunRequest
from app.services.detector_config_service import DetectorRuntimeConfigService
from app.services.detector_run_service import DetectorRunService


def test_rule_mode_missing_warning_price_does_not_hit(tmp_path) -> None:
    config_path = tmp_path / "runtime.yaml"
    config_path.write_text("low_price_warning:\n  enabled: true\n  mode: rule\n  params:\n    warning_price: null\n", encoding="utf-8")
    service = DetectorRunService(load_config())
    service.runtime_configs = DetectorRuntimeConfigService(config_path)

    result = service._run_one(DETECTOR_META["low_price_warning"], _frame([10, 12]), _request())[0]

    assert result.hit is False
    assert result.reason_code == "LOW_PRICE_THRESHOLD_NOT_CONFIGURED"


def test_auto_baseline_mean_factor_generates_threshold_without_using_mean_directly(tmp_path) -> None:
    config_path = tmp_path / "runtime.yaml"
    config_path.write_text(
        "low_price_warning:\n"
        "  enabled: true\n"
        "  mode: auto_baseline\n"
        "  params:\n"
        "    auto_baseline_method: mean_factor\n"
        "    auto_baseline_factor: 0.9\n",
        encoding="utf-8",
    )
    service = DetectorRunService(load_config())
    service.runtime_configs = DetectorRuntimeConfigService(config_path)

    hit = [item for item in service._run_one(DETECTOR_META["low_price_warning"], _frame([10, 10, 8]), _request()) if item.hit][0]

    assert hit.reason_code == "LOW_PRICE_BELOW_AUTO_BASELINE"
    assert hit.metrics["auto_baseline"]["method"] == "mean_factor"
    assert hit.metrics["auto_baseline_threshold"] != hit.metrics["auto_baseline"]["historical_mean_price"]
    assert "自动基线" in hit.narrative


def test_auto_baseline_quantile_generates_threshold(tmp_path) -> None:
    config_path = tmp_path / "runtime.yaml"
    config_path.write_text(
        "low_price_warning:\n"
        "  enabled: true\n"
        "  mode: auto_baseline\n"
        "  params:\n"
        "    auto_baseline_method: quantile\n"
        "    auto_baseline_quantile: 0.5\n",
        encoding="utf-8",
    )
    service = DetectorRunService(load_config())
    service.runtime_configs = DetectorRuntimeConfigService(config_path)

    result = service._run_one(DETECTOR_META["low_price_warning"], _frame([10, 9, 8]), _request())

    assert any(item.metrics.get("auto_baseline", {}).get("method") == "quantile" for item in result)


def _request() -> DetectorRunRequest:
    return DetectorRunRequest(
        source_type="csv",
        dataset_name="sample",
        as_of_date=date(2026, 6, 24),
        enabled_detectors=["low_price_warning"],
    )


def _frame(prices: list[float]) -> pd.DataFrame:
    rows = []
    for index, price in enumerate(prices):
        rows.append(
            {
                "order_id": f"O{index}",
                "org_code": "ORG_A",
                "product_line_code": "PL_A",
                "order_time": "2026-06-20",
                "purchase_qty": 1,
                "purchase_amount": price,
                "comparable_unit_price": price,
            }
        )
    frame = pd.DataFrame(rows)
    frame["order_time"] = pd.to_datetime(frame["order_time"], errors="coerce")
    return frame
