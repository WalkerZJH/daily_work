from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.detectors.base import BaseDetector
from app.detectors.cycle_deviation import CycleDeviationDetector
from app.detectors.frequency_drop import FrequencyDropDetector
from app.detectors.inactive_terminal import InactiveTerminalDetector
from app.detectors.ip_interval import IpIntervalDetector
from app.detectors.new_terminal import NewTerminalDetector
from app.detectors.sku_shrink import SkuShrinkDetector
from app.detectors.substitution_risk import SubstitutionRiskDetector

DETECTOR_CATEGORIES = [
    "price_warning",
    "delivery_response",
    "terminal_change",
    "sales_fluctuation",
    "common_preprocess",
]


class DetectorMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detector_id: str
    name: str
    category: str
    family: str
    version: str
    description: str
    enabled_by_default: bool
    required_features: list[str] = Field(default_factory=list)
    required_columns: list[str] = Field(default_factory=list)
    output_schema_version: str = "detector_evidence.v1"
    implemented: bool = True


DETECTOR_META: dict[str, DetectorMeta] = {
    "inactive_terminal": DetectorMeta(
        detector_id="inactive_terminal",
        name="Inactive terminal",
        category="terminal_change",
        family="terminal_activity",
        version="v0",
        description="Terminal/product line has been inactive longer than expected.",
        enabled_by_default=True,
        required_features=["inactive_days", "historical_median_ipi"],
        required_columns=["org_code", "product_line_code", "order_time"],
    ),
    "new_terminal": DetectorMeta(
        detector_id="new_terminal",
        name="New terminal",
        category="terminal_change",
        family="terminal_expansion",
        version="v0",
        description="Terminal/product line first appeared recently.",
        enabled_by_default=True,
        required_features=["first_order_date", "has_recent_order"],
        required_columns=["org_code", "product_line_code", "order_time"],
    ),
    "ip_interval": DetectorMeta(
        detector_id="ip_interval",
        name="Inter-purchase interval",
        category="terminal_change",
        family="terminal_activity",
        version="v0",
        description="Recent inactive days exceed historical purchase interval.",
        enabled_by_default=True,
        required_features=["inactive_days", "historical_median_ipi", "historical_mad_ipi"],
        required_columns=["org_code", "product_line_code", "order_time"],
    ),
    "frequency_drop": DetectorMeta(
        detector_id="frequency_drop",
        name="Frequency drop",
        category="terminal_change",
        family="terminal_activity",
        version="v0",
        description="Recent purchasing frequency dropped versus baseline.",
        enabled_by_default=True,
        required_features=["recent_order_count", "baseline_order_count"],
        required_columns=["org_code", "product_line_code", "order_time"],
    ),
    "sku_shrink": DetectorMeta(
        detector_id="sku_shrink",
        name="SKU shrink",
        category="terminal_change",
        family="assortment_change",
        version="v0",
        description="Recent active SKU/spec count shrank versus baseline.",
        enabled_by_default=True,
        required_features=["recent_active_sku_count", "baseline_active_sku_count"],
        required_columns=["org_code", "product_line_code", "drug_code", "spec"],
    ),
    "substitution_risk": DetectorMeta(
        detector_id="substitution_risk",
        name="Substitution risk",
        category="terminal_change",
        family="substitution",
        version="v0",
        description="Own product drops while broader group remains stable.",
        enabled_by_default=True,
        required_features=["own_recent_qty", "same_group_recent_qty"],
        required_columns=["org_code", "product_line_code"],
    ),
    "cycle_deviation": DetectorMeta(
        detector_id="cycle_deviation",
        name="Cycle deviation",
        category="terminal_change",
        family="cycle_prior",
        version="v0",
        description="Observed inactivity deviates from treatment-cycle prior.",
        enabled_by_default=True,
        required_features=["inactive_days", "refill_days"],
        required_columns=["org_code", "product_line_code", "order_time"],
    ),
    "low_price": DetectorMeta(
        detector_id="low_price",
        name="Low price warning",
        category="price_warning",
        family="price_threshold",
        version="v1",
        description="Comparable unit price is lower than configured warning price.",
        enabled_by_default=False,
        required_columns=[
            "comparable_unit_price",
            "drug_code",
            "product_line_code",
            "org_code",
            "order_time",
        ],
    ),
    "price_spread": DetectorMeta(
        detector_id="price_spread",
        name="Price spread warning",
        category="price_warning",
        family="price_spread",
        version="v1",
        description="Recent max/min comparable unit price spread exceeds threshold.",
        enabled_by_default=True,
        required_columns=["comparable_unit_price", "product_line_code", "org_code", "province"],
    ),
    "delivery_refusal": DetectorMeta(
        detector_id="delivery_refusal",
        name="Delivery refusal",
        category="delivery_response",
        family="delivery_status",
        version="v1",
        description="Order status contains refusal/return/unable-to-deliver keywords.",
        enabled_by_default=False,
        required_columns=["order_status", "order_id"],
        implemented=True,
    ),
    "delivery_delay": DetectorMeta(
        detector_id="delivery_delay",
        name="Delivery delay",
        category="delivery_response",
        family="delivery_timing",
        version="v1",
        description="Placeholder for delivery_time - order_time approximate delay rule.",
        enabled_by_default=False,
        required_columns=["order_time", "delivery_time"],
        implemented=False,
    ),
    "low_delivery_rate": DetectorMeta(
        detector_id="low_delivery_rate",
        name="Low delivery rate",
        category="delivery_response",
        family="delivery_fulfillment",
        version="v1",
        description="Placeholder for delivery_qty / purchase_qty fulfillment warning.",
        enabled_by_default=False,
        required_columns=["delivery_qty", "purchase_qty"],
        implemented=False,
    ),
}


class DetectorRegistry:
    def __init__(self) -> None:
        self._detectors: dict[str, BaseDetector] = {}

    def register(self, detector: BaseDetector) -> None:
        if detector.name in self._detectors:
            raise ValueError(f"Duplicate detector name: {detector.name}")
        self._detectors[detector.name] = detector

    def get(self, name: str) -> BaseDetector:
        return self._detectors[name]

    def list(self) -> list[BaseDetector]:
        return list(self._detectors.values())

    def names(self) -> list[str]:
        return list(self._detectors.keys())

    def catalog(self) -> list[DetectorMeta]:
        return list(DETECTOR_META.values())

    def meta(self, detector_id: str) -> DetectorMeta:
        return DETECTOR_META[detector_id]


def build_default_detector_registry() -> DetectorRegistry:
    registry = DetectorRegistry()
    for detector in [
        InactiveTerminalDetector(),
        NewTerminalDetector(),
        IpIntervalDetector(),
        FrequencyDropDetector(),
        SkuShrinkDetector(),
        SubstitutionRiskDetector(),
        CycleDeviationDetector(),
    ]:
        registry.register(detector)
    return registry
