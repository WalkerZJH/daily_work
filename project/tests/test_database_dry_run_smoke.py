from __future__ import annotations

from fastapi.testclient import TestClient
import pandas as pd

from app.adapters.base import DatasetBundle
from app.main import app
from app.services.feature_service import FeatureService


def test_database_dry_run_smoke_with_mocked_adapter(monkeypatch) -> None:
    raw_orders = pd.DataFrame(
        [
            {
                "数据唯一标识符": "SRC-1",
                "订单明细ID": "OD-1",
                "采购时间": "2026-01-02",
                "药品编码": "DRUG-1",
                "通用名": "通用名A",
                "转换系数": "1",
                "采购价(元)": "20",
                "采购数量": "3",
                "医疗机构编码": "ORG-1",
                "医疗机构": "医院A",
                "省": "江苏省",
            }
        ]
    )

    def fake_load_dataset(self: FeatureService, source, as_of_date=None) -> DatasetBundle:
        return DatasetBundle(
            dataset_name="database:mock",
            orders=raw_orders,
            drugs=pd.DataFrame(),
            orgs=pd.DataFrame(),
            product_line_mapping=pd.DataFrame(),
        )

    monkeypatch.setattr(FeatureService, "load_dataset", fake_load_dataset)
    response = TestClient(app).post(
        "/api/v0/inspection/dry-run",
        headers={"X-User-Id": "js_manager_001"},
        json={
            "source_type": "database",
            "dataset_name": "database:mock",
            "as_of_date": "2026-06-01",
            "row_limit": 10,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "risk_card_candidates" in payload
    assert "warning_summary" in payload
