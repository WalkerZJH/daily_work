from __future__ import annotations

from datetime import date

from app.core.config import load_config
from app.schemas.api import DataSourceRequest
from app.services.inspection_service import InspectionService

AS_OF_DATE = date(2025, 12, 31)


def _detectors(org_code: str, product_line_code: str) -> dict[str, bool]:
    service = InspectionService(load_config())
    result = service.inspect_unit(
        DataSourceRequest(dataset_name="sample"),
        org_code=org_code,
        product_line_code=product_line_code,
        as_of_date=AS_OF_DATE,
    )
    return {detector.detector_name: detector.hit for detector in result.detector_results}


def test_inactive_terminal_hits_long_inactive_case() -> None:
    hits = _detectors("ORG_A", "PL_A")
    assert hits["inactive_terminal"] is True


def test_new_terminal_hits_new_case() -> None:
    hits = _detectors("ORG_B", "PL_B")
    assert hits["new_terminal"] is True


def test_sku_shrink_hits_shrink_case() -> None:
    hits = _detectors("ORG_C", "PL_A")
    assert hits["sku_shrink"] is True
