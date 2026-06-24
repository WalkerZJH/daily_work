from __future__ import annotations

from datetime import date

from app.core.config import load_config
from app.schemas.api import DataSourceRequest
from app.services.inspection_service import InspectionService


def test_as_of_date_excludes_future_orders_from_features() -> None:
    service = InspectionService(load_config())
    result = service.inspect_unit(
        DataSourceRequest(dataset_name="sample"),
        org_code="ORG_A",
        product_line_code="PL_A",
        as_of_date=date(2025, 12, 31),
    )

    snapshot = result["feature_snapshot"]
    assert snapshot is not None
    assert snapshot["features"]["last_order_date"] == date(2025, 6, 20).isoformat()
    assert "OA013" not in str(snapshot["features"])
