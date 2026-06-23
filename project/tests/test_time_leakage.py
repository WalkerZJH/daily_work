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

    assert result.baseline_metrics.last_order_time is not None
    assert result.baseline_metrics.last_order_time.date() == date(2025, 6, 20)
    assert "OA013" not in result.baseline_metrics.recent_order_ids
    assert "OA013" not in result.baseline_metrics.baseline_order_ids
