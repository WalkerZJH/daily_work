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
    name_zh: str | None = None
    category: str
    family: str
    version: str
    description: str
    enabled_by_default: bool
    status: str = "implemented"
    required_fields: list[str] = Field(default_factory=list)
    optional_fields: list[str] = Field(default_factory=list)
    required_features: list[str] = Field(default_factory=list)
    required_columns: list[str] = Field(default_factory=list)
    output_schema_version: str = "detector_evidence.v1"
    output_schema: str = "detector_result.v1"
    implemented: bool = True
    notes: str = ""
    implementation_detector_ids: list[str] = Field(default_factory=list)


DETECTOR_META: dict[str, DetectorMeta] = {
    "inactive_terminal": DetectorMeta(
        detector_id="inactive_terminal",
        name="Inactive terminal",
        name_zh="内部：长期未采购",
        category="terminal_change",
        family="terminal_activity",
        version="v0",
        description="Terminal/product line has been inactive longer than expected.",
        enabled_by_default=True,
        status="interface_only",
        notes="内部 detector，用于支撑 terminal_lost_warning；health 页面优先展示需求 detector。",
        required_features=["inactive_days", "historical_median_ipi"],
        required_columns=["org_code", "product_line_code", "order_time"],
        required_fields=["org_code", "product_line_code", "order_time"],
    ),
    "new_terminal": DetectorMeta(
        detector_id="new_terminal",
        name="New terminal",
        name_zh="内部：新终端",
        category="terminal_change",
        family="terminal_expansion",
        version="v0",
        description="Terminal/product line first appeared recently.",
        enabled_by_default=True,
        status="interface_only",
        notes="内部 detector，用于支撑 new_terminal_warning；health 页面优先展示需求 detector。",
        required_features=["first_order_date", "has_recent_order"],
        required_columns=["org_code", "product_line_code", "order_time"],
        required_fields=["org_code", "product_line_code", "order_time"],
    ),
    "ip_interval": DetectorMeta(
        detector_id="ip_interval",
        name="Inter-purchase interval",
        name_zh="内部：采购间隔异常",
        category="terminal_change",
        family="terminal_activity",
        version="v0",
        description="Recent inactive days exceed historical purchase interval.",
        enabled_by_default=True,
        status="interface_only",
        notes="内部 detector，用于支撑 terminal_lost_warning。",
        required_features=["inactive_days", "historical_median_ipi", "historical_mad_ipi"],
        required_columns=["org_code", "product_line_code", "order_time"],
        required_fields=["org_code", "product_line_code", "order_time"],
    ),
    "frequency_drop": DetectorMeta(
        detector_id="frequency_drop",
        name="Frequency drop",
        name_zh="内部：采购频次下降",
        category="terminal_change",
        family="terminal_activity",
        version="v0",
        description="Recent purchasing frequency dropped versus baseline.",
        enabled_by_default=True,
        status="interface_only",
        notes="内部 detector，可支撑 purchase_frequency_fluctuation_warning 的下降方向。",
        required_features=["recent_order_count", "baseline_order_count"],
        required_columns=["org_code", "product_line_code", "order_time"],
        required_fields=["org_code", "product_line_code", "order_time"],
    ),
    "sku_shrink": DetectorMeta(
        detector_id="sku_shrink",
        name="SKU shrink",
        name_zh="保留：品规收缩",
        category="terminal_change",
        family="assortment_change",
        version="v0",
        description="Recent active SKU/spec count shrank versus baseline.",
        enabled_by_default=True,
        status="reserved",
        implemented=False,
        notes="初始需求未要求作为独立 health detector，本轮仅保留旧链路兼容。",
        required_features=["recent_active_sku_count", "baseline_active_sku_count"],
        required_columns=["org_code", "product_line_code", "drug_code", "spec"],
        required_fields=["org_code", "product_line_code", "drug_code", "spec"],
    ),
    "substitution_risk": DetectorMeta(
        detector_id="substitution_risk",
        name="Substitution risk",
        name_zh="保留：替代风险",
        category="terminal_change",
        family="substitution",
        version="v0",
        description="Own product drops while broader group remains stable.",
        enabled_by_default=True,
        status="reserved",
        implemented=False,
        notes="初始需求未要求本轮实现；保留接口，不在 health 页面默认运行。",
        required_features=["own_recent_qty", "same_group_recent_qty"],
        required_columns=["org_code", "product_line_code"],
        required_fields=["org_code", "product_line_code"],
    ),
    "cycle_deviation": DetectorMeta(
        detector_id="cycle_deviation",
        name="Cycle deviation",
        name_zh="保留：周期偏离",
        category="terminal_change",
        family="cycle_prior",
        version="v0",
        description="Observed inactivity deviates from treatment-cycle prior.",
        enabled_by_default=True,
        status="reserved",
        implemented=False,
        notes="初始需求未要求本轮实现；保留接口，不在 health 页面默认运行。",
        required_features=["inactive_days", "refill_days"],
        required_columns=["org_code", "product_line_code", "order_time"],
        required_fields=["org_code", "product_line_code", "order_time"],
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
        description="Approximate delivery delay based on delivery_time - order_time.",
        enabled_by_default=False,
        required_columns=["order_time", "delivery_time"],
        implemented=True,
    ),
    "low_delivery_rate": DetectorMeta(
        detector_id="low_delivery_rate",
        name="Low delivery rate",
        category="delivery_response",
        family="delivery_fulfillment",
        version="v1",
        description="Delivery quantity divided by purchase quantity is below threshold.",
        enabled_by_default=False,
        required_columns=["delivery_qty", "purchase_qty"],
        implemented=True,
    ),
    "purchase_qty_spike": DetectorMeta(
        detector_id="purchase_qty_spike",
        name="Purchase quantity spike",
        category="sales_fluctuation",
        family="purchase_quantity",
        version="v1",
        description="Recent purchase quantity is materially higher than baseline.",
        enabled_by_default=False,
        required_columns=["purchase_qty", "order_time", "org_code", "product_line_code"],
    ),
    "purchase_qty_drop": DetectorMeta(
        detector_id="purchase_qty_drop",
        name="Purchase quantity drop",
        category="sales_fluctuation",
        family="purchase_quantity",
        version="v1",
        description="Recent purchase quantity is materially lower than baseline.",
        enabled_by_default=False,
        required_columns=["purchase_qty", "order_time", "org_code", "product_line_code"],
    ),
    "purchase_freq_spike": DetectorMeta(
        detector_id="purchase_freq_spike",
        name="Purchase frequency spike",
        category="sales_fluctuation",
        family="purchase_frequency",
        version="v1",
        description="Recent purchase frequency is materially higher than baseline.",
        enabled_by_default=False,
        required_columns=["order_time", "org_code", "product_line_code"],
    ),
    "purchase_freq_drop": DetectorMeta(
        detector_id="purchase_freq_drop",
        name="Purchase frequency drop",
        category="sales_fluctuation",
        family="purchase_frequency",
        version="v1",
        description="Recent purchase frequency is materially lower than baseline.",
        enabled_by_default=False,
        required_columns=["order_time", "org_code", "product_line_code"],
    ),
    "low_price_warning": DetectorMeta(
        detector_id="low_price_warning",
        name="Low price warning",
        name_zh="低价采购预警",
        category="price_warning",
        family="price_threshold",
        version="v1",
        description="医院某品种订单单位可比价低于客户配置预警价。",
        enabled_by_default=False,
        status="implemented",
        required_fields=["comparable_unit_price", "org_code", "product_line_code", "order_time"],
        optional_fields=["purchase_amount", "warning_price", "conversion_factor", "drug_code", "org_name", "product_line_name"],
        required_columns=["comparable_unit_price", "org_code", "product_line_code", "order_time"],
        notes="若未配置 warning_price，则返回 MISSING_WARNING_PRICE_CONFIG，不编造预警价。",
        implementation_detector_ids=["low_price"],
    ),
    "price_spread_warning": DetectorMeta(
        detector_id="price_spread_warning",
        name="Price spread warning",
        name_zh="订单价差异常",
        category="price_warning",
        family="price_spread",
        version="v1",
        description="同一品规或产品线单位可比价最高价与最低价价差超过阈值。",
        enabled_by_default=True,
        status="implemented",
        required_fields=["comparable_unit_price", "product_line_code", "order_time"],
        optional_fields=["org_code", "province", "order_id", "drug_code"],
        required_columns=["comparable_unit_price", "product_line_code", "order_time"],
        notes="默认价差阈值 1.8；min_price <= 0 时返回 warning。",
        implementation_detector_ids=["price_spread"],
    ),
    "delivery_rejection_warning": DetectorMeta(
        detector_id="delivery_rejection_warning",
        name="Delivery rejection warning",
        name_zh="拒绝响应预警",
        category="delivery_response",
        family="delivery_status",
        version="v1",
        description="订单状态出现拒绝、退货、无法配送、缺货、驳回、拒收、撤单等拒绝响应类状态。",
        enabled_by_default=True,
        status="implemented",
        required_fields=["order_status", "order_id"],
        optional_fields=["distributor_name", "purchase_qty", "delivery_qty", "org_code", "product_line_code"],
        required_columns=["order_status", "order_id"],
        implementation_detector_ids=["delivery_refusal"],
    ),
    "delivery_delay_warning": DetectorMeta(
        detector_id="delivery_delay_warning",
        name="Delivery delay warning",
        name_zh="响应不及时预警",
        category="delivery_response",
        family="delivery_timing",
        version="v1",
        description="配送企业确认订单后超过 48 小时未发货；缺确认时间时用 delivery_time - order_time 降级判断。",
        enabled_by_default=True,
        status="implemented",
        required_fields=["order_time", "delivery_time"],
        optional_fields=["distributor_name", "order_id"],
        required_columns=["order_time", "delivery_time"],
        notes="当前真实表未提供确认时间字段，v1 使用下单到配送时间近似，并在 warnings 中说明。",
        implementation_detector_ids=["delivery_delay"],
    ),
    "low_delivery_rate_warning": DetectorMeta(
        detector_id="low_delivery_rate_warning",
        name="Low delivery rate warning",
        name_zh="配送率低预警",
        category="delivery_response",
        family="delivery_fulfillment",
        version="v1",
        description="配送数量除以采购数量低于配置阈值。",
        enabled_by_default=True,
        status="implemented",
        required_fields=["purchase_qty", "delivery_qty"],
        optional_fields=["province", "distributor_name", "order_id", "org_code", "product_line_code"],
        required_columns=["purchase_qty", "delivery_qty"],
        notes="默认阈值 0.8，后续可按省份配置。",
        implementation_detector_ids=["low_delivery_rate"],
    ),
    "terminal_lost_warning": DetectorMeta(
        detector_id="terminal_lost_warning",
        name="Terminal lost warning",
        name_zh="终端丢失预警",
        category="terminal_change",
        family="terminal_lost",
        version="v1",
        description="根据历史采购周期和当前未采购天数判断疑似终端丢失。",
        enabled_by_default=True,
        status="implemented",
        required_fields=["org_code", "product_line_code", "order_time", "purchase_qty"],
        optional_fields=["p_alive", "avg_purchase_qty"],
        required_columns=["org_code", "product_line_code", "order_time", "purchase_qty"],
        notes="v1 使用采购间隔和未采购天数；P_alive 结果可作为后续增强证据。",
        implementation_detector_ids=["inactive_terminal", "ip_interval"],
    ),
    "new_terminal_warning": DetectorMeta(
        detector_id="new_terminal_warning",
        name="New terminal warning",
        name_zh="新进终端识别",
        category="terminal_change",
        family="terminal_new",
        version="v1",
        description="医院首次采购某产品线，或 180 天未采购后恢复采购，且采购数量达到阈值。",
        enabled_by_default=True,
        status="implemented",
        required_fields=["org_code", "product_line_code", "order_time", "purchase_qty"],
        optional_fields=["new_terminal_min_qty"],
        required_columns=["org_code", "product_line_code", "order_time", "purchase_qty"],
        notes="采购数量不足阈值时返回低置信观察结果。",
        implementation_detector_ids=["new_terminal"],
    ),
    "purchase_quantity_fluctuation_warning": DetectorMeta(
        detector_id="purchase_quantity_fluctuation_warning",
        name="Purchase quantity fluctuation warning",
        name_zh="采购量异常波动",
        category="sales_fluctuation",
        family="purchase_quantity",
        version="v1",
        description="当前采购量超过近 6 月平均采购量 3 倍，或与上月相比骤降。",
        enabled_by_default=True,
        status="implemented",
        required_fields=["purchase_qty", "order_time", "org_code", "product_line_code"],
        optional_fields=["order_id"],
        required_columns=["purchase_qty", "order_time", "org_code", "product_line_code"],
        implementation_detector_ids=["purchase_qty_spike", "purchase_qty_drop"],
    ),
    "purchase_frequency_fluctuation_warning": DetectorMeta(
        detector_id="purchase_frequency_fluctuation_warning",
        name="Purchase frequency fluctuation warning",
        name_zh="采购频次异常波动",
        category="sales_fluctuation",
        family="purchase_frequency",
        version="v1",
        description="近 30 天采购次数超过近 6 月平均月频次 2 倍，或与上月相比骤降。",
        enabled_by_default=True,
        status="implemented",
        required_fields=["order_time", "org_code", "product_line_code"],
        optional_fields=["order_id"],
        required_columns=["order_time", "org_code", "product_line_code"],
        implementation_detector_ids=["purchase_freq_spike", "purchase_freq_drop"],
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
