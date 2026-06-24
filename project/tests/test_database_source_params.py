from __future__ import annotations

from datetime import date

import pandas as pd

from app.core.config import load_config
from app.schemas.api import DataSourceRequest
from app.services.feature_service import FeatureService


def test_database_source_params_are_passed_to_sql_adapter(monkeypatch) -> None:
    captured = {}

    class FakeSQLAdapter:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)
            self.dataset_name = "database:fake"

        def load_dataset(self):
            from app.adapters.base import DatasetBundle

            return DatasetBundle(
                dataset_name="database:fake",
                orders=pd.DataFrame(columns=["order_time", "drug_code", "org_code", "purchase_qty", "purchase_price"]),
                drugs=pd.DataFrame(),
                orgs=pd.DataFrame(),
                product_line_mapping=pd.DataFrame(),
            )

    monkeypatch.setattr("app.services.feature_service.SQLTableSourceAdapter", FakeSQLAdapter)
    source = DataSourceRequest(
        source_type="database",
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 15),
        row_limit=123,
        enterprise_code="ENT",
        province_code="320000",
    )

    FeatureService(load_config()).load_dataset(source, date(2026, 6, 24))

    assert captured["date_from"] == date(2026, 6, 1)
    assert captured["date_to"] == date(2026, 6, 15)
    assert captured["row_limit"] == 123
    assert captured["enterprise_code"] == "ENT"
    assert captured["province_code"] == "320000"
