from __future__ import annotations

from datetime import date

import pandas as pd

from app.detectors.order_level import run_order_level_detectors
from app.core.config import load_config
from app.detectors.registry import DETECTOR_META
from app.schemas.api import DetectorRunRequest
from app.services.detector_run_service import DetectorRunService


def test_low_price_uses_comparable_unit_price() -> None:
    orders = pd.DataFrame(
        [
            _row(
                order_id="O1",
                comparable_unit_price=4,
                purchase_price=100,
            )
        ]
    )

    evidence_by_unit = run_order_level_detectors(
        orders,
        as_of_date=date(2026, 6, 24),
        enabled_detectors=["low_price"],
        recent_days=14,
        low_price_config={"warning_price": 5},
    )

    evidence = evidence_by_unit["ORG_A|product_line|PL_A"][0]
    assert evidence.hit is True
    assert evidence.statistics["comparable_unit_price"] == 4
    assert evidence.statistics["warning_price"] == 5


def test_low_price_missing_threshold_returns_warning_without_hit() -> None:
    evidence_by_unit = run_order_level_detectors(
        pd.DataFrame([_row(order_id="O1", comparable_unit_price=4)]),
        as_of_date=date(2026, 6, 24),
        enabled_detectors=["low_price"],
        recent_days=14,
    )

    evidence = evidence_by_unit["|product_line|"][0]
    assert evidence.hit is False
    assert "LOW_PRICE_THRESHOLD_NOT_CONFIGURED" in evidence.warnings


def test_price_spread_uses_recent_max_min_ratio() -> None:
    orders = pd.DataFrame(
        [
            _row(order_id="O1", comparable_unit_price=10),
            _row(order_id="O2", comparable_unit_price=20),
        ]
    )

    evidence_by_unit = run_order_level_detectors(
        orders,
        as_of_date=date(2026, 6, 24),
        enabled_detectors=["price_spread"],
        recent_days=14,
        spread_ratio_threshold=1.8,
    )

    evidence = evidence_by_unit["ORG_A|product_line|PL_A"][0]
    assert evidence.hit is True
    assert evidence.statistics["min_price"] == 10
    assert evidence.statistics["max_price"] == 20
    assert evidence.statistics["spread_ratio"] == 2


def test_requirement_low_price_missing_warning_price_config_does_not_fabricate() -> None:
    result = _run_requirement_detector(
        pd.DataFrame([_row(order_id="O1", comparable_unit_price=4)]),
        "low_price_warning",
    )[0]

    assert result.hit is False
    assert result.reason_code == "LOW_PRICE_THRESHOLD_NOT_CONFIGURED"
    assert any("缺少客户预警价配置" in warning for warning in result.warnings)


def test_requirement_price_spread_hits_when_ratio_exceeds_threshold() -> None:
    results = _run_requirement_detector(
        pd.DataFrame(
            [
                _row(order_id="O1", comparable_unit_price=10),
                _row(order_id="O2", comparable_unit_price=20),
            ]
        ),
        "price_spread_warning",
    )

    hit = [result for result in results if result.hit][0]
    assert hit.metrics["price_spread_ratio"] == 2


def test_requirement_price_detector_warns_when_conversion_factor_missing(tmp_path) -> None:
    config_path = tmp_path / "thresholds.yaml"
    config_path.write_text("low_price_warning:\n  warning_price: 5\n  overrides: {}\n", encoding="utf-8")
    frame = pd.DataFrame([_row(order_id="O1", comparable_unit_price=4)])
    prepared = frame.copy()
    prepared["order_time"] = pd.to_datetime(prepared["order_time"], errors="coerce")
    service = DetectorRunService(load_config(), threshold_path=config_path)
    request = DetectorRunRequest(
        source_type="csv",
        dataset_name="sample",
        as_of_date=date(2026, 6, 24),
        enabled_detectors=["low_price_warning"],
    )
    result = service._run_one(DETECTOR_META["low_price_warning"], prepared, request)[0]

    assert result.hit is True
    assert "转换系数缺失或无效" in result.warnings[0]


def _row(
    *,
    order_id: str,
    comparable_unit_price: float,
    purchase_price: float | None = None,
) -> dict:
    return {
        "order_id": order_id,
        "org_code": "ORG_A",
        "org_name": "Org A",
        "product_line_code": "PL_A",
        "product_line_name": "Product A",
        "drug_code": "D1",
        "province": "江苏省",
        "order_time": "2026-06-20",
        "purchase_qty": 1,
        "purchase_amount": 10,
        "purchase_price": purchase_price if purchase_price is not None else comparable_unit_price,
        "comparable_unit_price": comparable_unit_price,
    }


def _run_requirement_detector(frame: pd.DataFrame, detector_id: str):
    service = DetectorRunService(load_config())
    prepared = frame.copy()
    prepared["order_time"] = pd.to_datetime(prepared["order_time"], errors="coerce")
    request = DetectorRunRequest(
        source_type="csv",
        dataset_name="sample",
        as_of_date=date(2026, 6, 24),
        enabled_detectors=[detector_id],
    )
    return service._run_one(DETECTOR_META[detector_id], prepared, request)
