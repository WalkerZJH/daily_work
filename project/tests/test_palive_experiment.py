from __future__ import annotations

from datetime import date

import pandas as pd
from fastapi.testclient import TestClient

from app.core.config import load_config
from app.main import app
from app.schemas.api import PAliveExperimentConfig
from app.services.palive_experiment_service import PAliveExperimentService


def _orders(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _row(org: str, line: str, day: str, *, shape: str = "smooth") -> dict:
    return {
        "order_id": f"{org}-{line}-{day}",
        "org_code": org,
        "org_name": f"{org} Hospital",
        "org_level": "三级",
        "province": "江苏省",
        "product_line_code": line,
        "product_line_name": f"{line} Line",
        "drug_code": f"{line}-D",
        "order_time": day,
        "purchase_qty": 10,
        "purchase_price": 10,
        "demand_shape": shape,
    }


def test_interval_survival_proxy_declines_as_days_since_purchase_grows() -> None:
    orders = _orders(
        [_row("ORG_A", "PL_A", day) for day in ["2026-01-01", "2026-02-01", "2026-03-01"]]
        + [_row("ORG_B", "PL_A", day) for day in ["2026-01-01", "2026-02-01", "2026-03-01"]]
    )
    service = PAliveExperimentService(load_config())
    cfg = PAliveExperimentConfig(min_cohort_intervals=1)

    early = service.run_on_orders(
        orders,
        dataset_name="unit",
        as_of_date=date(2026, 3, 15),
        config=cfg,
    ).results[0]
    late = service.run_on_orders(
        orders,
        dataset_name="unit",
        as_of_date=date(2026, 4, 25),
        config=cfg,
    ).results[0]

    assert early.p_alive_proxy_interval is not None
    assert late.p_alive_proxy_interval is not None
    assert early.p_alive_proxy_interval > late.p_alive_proxy_interval


def test_cold_start_uses_cohort_prior_with_low_confidence() -> None:
    orders = _orders(
        [_row("ORG_COLD", "PL_A", "2026-03-01")]
        + [_row("ORG_B", "PL_A", day) for day in ["2026-01-01", "2026-02-01", "2026-03-01"]]
        + [_row("ORG_D", "PL_A", day) for day in ["2026-01-05", "2026-02-05", "2026-03-05"]]
    )
    service = PAliveExperimentService(load_config())
    cfg = PAliveExperimentConfig(min_cohort_intervals=1, low_confidence_threshold=0.3)

    result = service.run_on_orders(
        orders,
        dataset_name="unit",
        as_of_date=date(2026, 3, 20),
        config=cfg,
    )
    cold = next(item for item in result.results if item.org_code == "ORG_COLD")

    assert cold.selected_p_alive is not None
    assert cold.model_confidence <= 0.3
    assert "UNIT_INTERVALS_INSUFFICIENT_USING_COHORT_PRIOR" in cold.warnings
    assert "COLD_START_LOW_CONFIDENCE" in cold.warnings


def test_intermittent_unit_prefers_intermit_proxy_not_simple_trend_high_risk() -> None:
    orders = _orders(
        [_row("ORG_INT", "PL_I", day) for day in ["2025-01-01", "2025-04-01", "2025-07-01"]]
        + [_row("ORG_PEER", "PL_I", day) for day in ["2025-01-10", "2025-04-10", "2025-07-10"]]
    )
    service = PAliveExperimentService(load_config())
    cfg = PAliveExperimentConfig(min_cohort_intervals=1)

    result = service.run_on_orders(
        orders,
        dataset_name="unit",
        as_of_date=date(2025, 9, 15),
        config=cfg,
    )
    intermittent = next(item for item in result.results if item.org_code == "ORG_INT")

    assert intermittent.demand_profile == "intermittent"
    assert intermittent.selected_model_name == "intermittent_overdue_proxy"
    assert intermittent.selected_p_alive is not None
    assert intermittent.selected_p_alive > 0.5
    assert "INTERMITTENT_PROFILE_AVOIDS_SIMPLE_TREND_DROP" in intermittent.warnings


def test_bgnbd_failure_returns_sanitized_warning_without_api_failure() -> None:
    response = TestClient(app).post(
        "/api/v0/backbone/palive/experiment",
        json={
            "dataset_name": "sample",
            "as_of_date": "2025-12-31",
            "enabled_models": ["bgnbd_candidate"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["results"]
    warnings = {
        warning
        for result in payload["results"]
        for warning in result["warnings"]
    }
    assert "BGNBD_DEPENDENCY_NOT_AVAILABLE" in warnings or "BGNBD_INSUFFICIENT_HISTORY" in warnings
