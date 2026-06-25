from __future__ import annotations

from datetime import date

import pandas as pd

from app.adapters.base import DatasetBundle
from app.core.config import load_config
from app.schemas.api import DatabaseSmokeTestRequest
from app.services.database_smoke_test_service import DatabaseSmokeTestService
from app.services.feature_service import FeatureService


def test_backbone_smoke_single_as_of_date_counts_units(monkeypatch) -> None:
    frame = pd.DataFrame(
        [
            _row("O1", "ORG_A", "PL_A"),
            _row("O2", "ORG_A", "PL_A"),
            _row("O3", "ORG_B", "PL_A"),
            _row("O4", "ORG_C", "PL_B"),
            _row("O5", "ORG_C", "PL_B"),
        ]
    )
    monkeypatch.setattr(FeatureService, "load_dataset", lambda self, source, as_of_date=None: _bundle(frame))

    response = DatabaseSmokeTestService(load_config()).run(
        DatabaseSmokeTestRequest(source_type="csv", as_of_date=date(2026, 6, 25), row_limit=5),
        persist_summary=False,
    )

    summary = response.summary
    assert summary["raw_order_rows"] == 5
    assert summary["effective_order_rows"] == 5
    assert summary["analysis_unit_count"] == 3
    assert summary["prediction_count"] == 3
    unit_ids = [row["analysis_unit_id"] for row in response.palive_preview]
    assert len(unit_ids) == len(set(unit_ids))


def test_backbone_unit_count_not_exceed_effective_rows(monkeypatch) -> None:
    frame = pd.DataFrame([_row(f"O{i}", f"ORG_{i}", "PL_A") for i in range(10)])
    monkeypatch.setattr(FeatureService, "load_dataset", lambda self, source, as_of_date=None: _bundle(frame))

    summary = DatabaseSmokeTestService(load_config()).run(
        DatabaseSmokeTestRequest(source_type="csv", as_of_date=date(2026, 6, 25), row_limit=10),
        persist_summary=False,
    ).summary

    assert summary["analysis_unit_count"] <= summary["effective_order_rows"]


def test_backbone_row_limit_consistency(monkeypatch) -> None:
    def fake_load_dataset(self, source, as_of_date=None):
        assert source.row_limit == 5
        return _bundle(pd.DataFrame([_row(f"O{i}", f"ORG_{i}", "PL_A") for i in range(source.row_limit)]))

    monkeypatch.setattr(FeatureService, "load_dataset", fake_load_dataset)

    summary = DatabaseSmokeTestService(load_config()).run(
        DatabaseSmokeTestRequest(source_type="database", as_of_date=date(2026, 6, 25), row_limit=5),
        persist_summary=False,
    ).summary

    assert summary["raw_order_rows"] == 5
    assert summary["effective_order_rows"] == 5
    assert summary["analysis_unit_count"] == 5
    assert summary["prediction_count"] == 5


def _row(order_id: str, org_code: str, product_line_code: str) -> dict:
    return {
        "order_id": order_id,
        "org_code": org_code,
        "org_name": org_code,
        "product_line_code": product_line_code,
        "product_line_name": product_line_code,
        "drug_code": "D1",
        "order_time": "2026-06-20",
        "purchase_qty": 1,
        "void_qty": 0,
        "purchase_amount": 10,
        "purchase_price": 10,
        "comparable_unit_price": 10,
    }


def _bundle(frame: pd.DataFrame) -> DatasetBundle:
    return DatasetBundle(
        dataset_name="test",
        orders=frame,
        drugs=pd.DataFrame(),
        orgs=pd.DataFrame(),
        product_line_mapping=pd.DataFrame(),
    )
