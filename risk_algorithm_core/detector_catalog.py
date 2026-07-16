"""Detector capability and result-batch catalog tables."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .detector_config import DailyDetectorConfig, load_daily_detector_config


DETECTOR_CATALOG_SCHEMA_VERSION = "daily_detector_catalog_v1"
DETECTOR_OUTPUT_SCHEMA_VERSION = "daily_detector_clue_v1"


DETECTOR_RELEASE_B_LABELS = {
    "purchase_interval_ipi": ("采购间隔异常", "当前采购间隔明显超过对象自身历史正常间隔。"),
    "purchase_quantity_trend": ("采购量下降", "简单比例规则 v1：近期采购量 ÷ 历史基准采购量低于阈值。"),
    "purchase_frequency_drop": ("采购频次下降", "近期采购次数明显低于对象自身历史频次基准。"),
    "purchase_quantity_spike": ("采购量异常上升", "近期采购数量明显高于对象自身历史采购水平。"),
    "purchase_frequency_spike": ("采购频次异常上升", "近期采购次数明显高于对象自身历史频次基准。"),
    "low_price_warning": ("低价预警", "当前采购单价低于配置阈值或历史市场低位参考。"),
    "order_price_spread_warning": ("订单价格离散预警", "近期可比采购单价的高低差异超过规则阈值。"),
    "purchase_price_level_shift": ("采购价格水平漂移", "近期采购价格中位水平偏离历史基准。"),
    "first_purchase_fact": ("首次采购事实", "记录对象首次发生正常完成采购的事实。"),
    "reactivated_purchase_fact": ("恢复采购事实", "记录对象在较长静默期后恢复正常采购的事实。"),
    "sku_shrink": ("SKU 收缩", "当前缺少正式产品线领域概念，暂不可执行。"),
    "fulfillment_gap": ("履约缺口", "当前交付与到货时间字段不足，暂不可执行。"),
    "price_competition": ("价格竞争", "当前缺少可靠的可比单价与价格参考，暂不可执行。"),
    "peer_contrast": ("同群对比", "当前同群样本稳定性尚未完成业务验证，暂不可执行。"),
}

DETECTOR_FAMILY_NAMES_ZH = {
    "interval": "采购间隔异常",
    "quantity": "采购数量异常",
    "frequency": "采购频次异常",
    "price": "采购价格异常",
    "purchase_fact": "采购事实",
    "assortment": "SKU 结构",
    "fulfillment": "履约交付",
    "peer": "同群对比",
}


CAPABILITY_ROWS = [
    {
        "detector_family": "interval",
        "detector_id": "purchase_interval_ipi",
        "detector_name": "Purchase interval IPI",
        "design_source": "终端不丢智能体_设计方案.md",
        "design_section": "A.2",
        "current_model_implementation_path": "risk_algorithm_core/daily_detector_runner.py",
        "current_backend_reference_path": "project/app/detectors/ip_interval.py",
        "status": "implemented",
        "enabled_by_default": True,
        "method": "median_mad_robust_z_v1",
        "required_fields": "purchase_time,last_purchase_date,days_since_last_purchase,purchase_count,median_purchase_interval_days,mad_purchase_interval_days",
        "optional_fields": "demand_shape_label",
        "missing_fields": "",
        "can_enter_v1_daily_detector": True,
        "backlog_only": False,
        "reason": "stable interval evidence available from source-aligned cutoff features",
        "caveat": "detector_score is not probability",
    },
    {
        "detector_family": "quantity",
        "detector_id": "purchase_quantity_trend",
        "detector_name": "Purchase quantity trend",
        "design_source": "终端不丢智能体_设计方案.md",
        "design_section": "A.3",
        "current_model_implementation_path": "risk_algorithm_core/daily_detector_runner.py",
        "current_backend_reference_path": "project/app/detectors/order_level.py",
        "status": "implemented",
        "enabled_by_default": True,
        "method": "simplified_ratio_v1",
        "required_fields": "purchase_quantity,purchase_amount,purchase_month,recent_quantity,baseline_quantity",
        "optional_fields": "recent_amount,baseline_amount",
        "missing_fields": "",
        "can_enter_v1_daily_detector": True,
        "backlog_only": False,
        "reason": "first version uses labeled recent/base ratio, not MK/Theil-Sen/CUSUM",
        "caveat": "auxiliary evidence, not price or competitor conclusion",
    },
    {
        "detector_family": "frequency",
        "detector_id": "purchase_frequency_drop",
        "detector_name": "Purchase frequency drop",
        "design_source": "终端不丢智能体_设计方案.md",
        "design_section": "A.4",
        "current_model_implementation_path": "risk_algorithm_core/daily_detector_runner.py",
        "current_backend_reference_path": "project/app/detectors/frequency_drop.py",
        "status": "implemented",
        "enabled_by_default": True,
        "method": "recent_base_rate_ratio_v1",
        "required_fields": "order_id,purchase_time,recent_order_count,baseline_order_count,recent_month_count,baseline_month_count",
        "optional_fields": "",
        "missing_fields": "",
        "can_enter_v1_daily_detector": True,
        "backlog_only": False,
        "reason": "recent/base frequency ratio is available from production feature frame",
        "caveat": "low base-rate entities remain low confidence",
    },
    {
        "detector_family": "assortment",
        "detector_id": "sku_shrink",
        "detector_name": "SKU shrink",
        "design_source": "终端不丢智能体_设计方案.md",
        "design_section": "A.5",
        "current_model_implementation_path": "risk_algorithm_core/daily_detector_runner.py",
        "current_backend_reference_path": "project/app/detectors/sku_shrink.py",
        "status": "blocked_by_missing_domain_concept",
        "enabled_by_default": False,
        "method": "not_applicable_without_product_line_domain",
        "required_fields": "drug_code,specification,dosage_form,product_line_code,baseline_active_sku_count,recent_active_sku_count",
        "optional_fields": "drug_category_code",
        "missing_fields": "product_line_domain_concept",
        "can_enter_v1_daily_detector": False,
        "backlog_only": True,
        "reason": "current main chain has no product-line domain concept; SKU shrink is out of scope",
        "caveat": "do not infer competitor replacement",
    },
    {
        "detector_family": "fulfillment",
        "detector_id": "fulfillment_gap",
        "detector_name": "Fulfillment gap",
        "design_source": "终端不丢智能体_设计方案.md",
        "design_section": "B",
        "current_model_implementation_path": "risk_algorithm_core/daily_detector_runner.py",
        "current_backend_reference_path": "project/app/detectors/order_level.py",
        "status": "blocked_by_data",
        "enabled_by_default": False,
        "method": "disabled_due_to_unreliable_delivery_time_fields",
        "required_fields": "purchase_quantity,delivery_quantity,arrival_quantity,purchase_time,delivery_time,arrival_time,distributor_code",
        "optional_fields": "distributor_name",
        "missing_fields": "stable_delivery_time,stable_arrival_time",
        "can_enter_v1_daily_detector": False,
        "backlog_only": True,
        "reason": "delivery_time/received_time quality and completeness do not support formal execution",
        "caveat": "no distributor responsibility claim",
    },
    {
        "detector_family": "price",
        "detector_id": "price_competition",
        "detector_name": "Price competition",
        "design_source": "终端不丢智能体_设计方案.md",
        "design_section": "A backlog",
        "current_model_implementation_path": "risk_algorithm_core/daily_detector_runner.py",
        "current_backend_reference_path": "project/app/detectors/substitution_risk.py",
        "status": "not_implemented",
        "enabled_by_default": False,
        "method": "requires_comparable_unit_price",
        "required_fields": "purchase_price,comparable_unit_price,approval_number,price_reference",
        "optional_fields": "",
        "missing_fields": "comparable_unit_price,approval_number,price_reference",
        "can_enter_v1_daily_detector": False,
        "backlog_only": True,
        "reason": "price comparability and package conversion not confirmed",
        "caveat": "do not infer low-price or competitor replacement conclusion",
    },
    {
        "detector_family": "peer",
        "detector_id": "peer_contrast",
        "detector_name": "Peer contrast",
        "design_source": "终端不丢智能体_设计方案.md",
        "design_section": "A backlog",
        "current_model_implementation_path": "risk_algorithm_core/daily_detector_runner.py",
        "current_backend_reference_path": "project/app/detectors/registry.py",
        "status": "reserved",
        "enabled_by_default": False,
        "method": "requires_peer_group_quality",
        "required_fields": "hospital_level,region_code,peer_group_metrics",
        "optional_fields": "",
        "missing_fields": "peer_group_metrics",
        "can_enter_v1_daily_detector": False,
        "backlog_only": True,
        "reason": "peer cohort stability and sample quality need business validation",
        "caveat": "not enabled by default",
    },
]

CAPABILITY_ROWS.extend(
    [
        {
            "detector_family": "quantity",
            "detector_id": "purchase_quantity_spike",
            "detector_name": "Purchase quantity spike",
            "design_source": "Detector完整链路实现指导.md",
            "design_section": "11.3",
            "current_model_implementation_path": "risk_algorithm_core/daily_detector_runner.py",
            "current_backend_reference_path": "project/app/detectors/order_level.py",
            "status": "implemented",
            "enabled_by_default": True,
            "method": "recent_base_quantity_ratio_v1",
            "required_fields": "recent_quantity,baseline_quantity,quantity_ratio",
            "optional_fields": "recent_amount,baseline_amount,demand_shape_label",
            "missing_fields": "",
            "can_enter_v1_daily_detector": True,
            "backlog_only": False,
            "reason": "quantity rise is an independent rule from quantity decline",
            "caveat": "provisional threshold; auxiliary fact, not demand causality",
        },
        {
            "detector_family": "frequency",
            "detector_id": "purchase_frequency_spike",
            "detector_name": "Purchase frequency spike",
            "design_source": "Detector完整链路实现指导.md",
            "design_section": "11.5",
            "current_model_implementation_path": "risk_algorithm_core/daily_detector_runner.py",
            "current_backend_reference_path": "project/app/detectors/order_level.py",
            "status": "implemented",
            "enabled_by_default": True,
            "method": "recent_base_frequency_ratio_v1",
            "required_fields": "recent_order_count,baseline_order_count,frequency_ratio",
            "optional_fields": "demand_shape_label",
            "missing_fields": "",
            "can_enter_v1_daily_detector": True,
            "backlog_only": False,
            "reason": "frequency rise is an independent rule from frequency decline",
            "caveat": "provisional threshold; no causal claim",
        },
        {
            "detector_family": "price",
            "detector_id": "low_price_warning",
            "detector_name": "Low purchase price warning",
            "design_source": "Detector完整链路实现指导.md",
            "design_section": "11.6",
            "current_model_implementation_path": "risk_algorithm_core/daily_detector_runner.py",
            "current_backend_reference_path": "project/app/detectors/order_level.py",
            "status": "implemented",
            "enabled_by_default": True,
            "method": "configured_price_or_prior_market_p05_v1",
            "required_fields": "purchase_unit_price,purchase_unit,drug_code,order_status_lifecycle",
            "optional_fields": "configured_warning_price",
            "missing_fields": "",
            "can_enter_v1_daily_detector": True,
            "backlog_only": False,
            "reason": "clean direct price and unit are available on normal completed orders",
            "caveat": "price warning only; never infer competition",
        },
        {
            "detector_family": "price",
            "detector_id": "order_price_spread_warning",
            "detector_name": "Order price spread warning",
            "design_source": "Detector完整链路实现指导.md",
            "design_section": "11.7",
            "current_model_implementation_path": "risk_algorithm_core/daily_detector_runner.py",
            "current_backend_reference_path": "project/app/detectors/order_level.py",
            "status": "implemented",
            "enabled_by_default": True,
            "method": "recent_max_min_ratio_v1",
            "required_fields": "purchase_unit_price,purchase_unit,recent_price_window",
            "optional_fields": "p10_price,p90_price",
            "missing_fields": "",
            "can_enter_v1_daily_detector": True,
            "backlog_only": False,
            "reason": "comparable price group is drug_code plus purchase_unit",
            "caveat": "spread is not evidence of fraud, competition, or responsibility",
        },
        {
            "detector_family": "price",
            "detector_id": "purchase_price_level_shift",
            "detector_name": "Purchase price level shift",
            "design_source": "Detector完整链路实现指导.md",
            "design_section": "11.8",
            "current_model_implementation_path": "risk_algorithm_core/daily_detector_runner.py",
            "current_backend_reference_path": "",
            "status": "implemented",
            "enabled_by_default": True,
            "method": "recent_baseline_median_ratio_v1",
            "required_fields": "purchase_unit_price,purchase_unit,recent_price,baseline_price",
            "optional_fields": "demand_shape_label",
            "missing_fields": "",
            "can_enter_v1_daily_detector": True,
            "backlog_only": False,
            "reason": "directional price-level fact uses stable median comparison",
            "caveat": "price movement is not a causal conclusion",
        },
        {
            "detector_family": "purchase_fact",
            "detector_id": "first_purchase_fact",
            "detector_name": "First normal purchase fact",
            "design_source": "Detector完整链路实现指导.md",
            "design_section": "11.9",
            "current_model_implementation_path": "risk_algorithm_core/daily_detector_runner.py",
            "current_backend_reference_path": "risk_algorithm_core/detectors/one_shot.py",
            "status": "implemented",
            "enabled_by_default": True,
            "method": "first_normal_completed_purchase_fact_v1",
            "required_fields": "first_purchase_date,first_order_id",
            "optional_fields": "first_purchase_quantity,first_purchase_amount",
            "missing_fields": "",
            "can_enter_v1_daily_detector": True,
            "backlog_only": False,
            "reason": "fact-only first normal completed purchase",
            "caveat": "does not output repurchase probability",
        },
        {
            "detector_family": "purchase_fact",
            "detector_id": "reactivated_purchase_fact",
            "detector_name": "Reactivated normal purchase fact",
            "design_source": "Detector完整链路实现指导.md",
            "design_section": "11.10",
            "current_model_implementation_path": "risk_algorithm_core/daily_detector_runner.py",
            "current_backend_reference_path": "",
            "status": "implemented",
            "enabled_by_default": True,
            "method": "normal_purchase_after_silence_v1",
            "required_fields": "current_purchase_date,previous_purchase_date,silence_days",
            "optional_fields": "",
            "missing_fields": "",
            "can_enter_v1_daily_detector": True,
            "backlog_only": False,
            "reason": "fact-only return after a versioned silence interval",
            "caveat": "does not claim retention success or future behavior",
        },
    ]
)


def build_detector_capability_matrix() -> pd.DataFrame:
    return _frame(CAPABILITY_ROWS)


def build_detector_catalog(config: DailyDetectorConfig | None = None) -> pd.DataFrame:
    cfg = config or load_daily_detector_config()
    rows = []
    for row in CAPABILITY_ROWS:
        detector_cfg = cfg.detectors.get(row["detector_id"], {})
        detector_name_zh, detector_description_zh = DETECTOR_RELEASE_B_LABELS.get(
            row["detector_id"],
            (row["detector_name"], row["reason"]),
        )
        rows.append(
            {
                "detector_id": row["detector_id"],
                "detector_family": row["detector_family"],
                "detector_name": row["detector_name"],
                "detector_name_en": row["detector_name"],
                "detector_name_zh": detector_name_zh,
                "detector_description_zh": detector_description_zh,
                "detector_family_name_zh": DETECTOR_FAMILY_NAMES_ZH.get(
                    row["detector_family"], row["detector_family"]
                ),
                "status": str(detector_cfg.get("status") or row["status"]),
                "enabled_by_default": bool(detector_cfg.get("enabled", row["enabled_by_default"])),
                "method": str(detector_cfg.get("method") or row["method"]),
                "required_fields": row["required_fields"],
                "optional_fields": row["optional_fields"],
                "output_schema_version": DETECTOR_OUTPUT_SCHEMA_VERSION,
                "caveat": row["caveat"],
            }
        )
    return _frame(rows)


def write_detector_capability_matrix(report_dir: str | Path) -> tuple[Path, Path]:
    path = Path(report_dir)
    path.mkdir(parents=True, exist_ok=True)
    matrix = build_detector_capability_matrix()
    csv_path = path / "detector_capability_matrix.csv"
    md_path = path / "detector_capability_matrix.md"
    matrix.to_csv(csv_path, index=False)
    md_path.write_text(_to_markdown(matrix, "# Detector Capability Matrix"), encoding="utf-8")
    return md_path, csv_path


def _frame(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    for column in ["enabled_by_default", "can_enter_v1_daily_detector", "backlog_only"]:
        if column in frame:
            frame[column] = frame[column].astype(object)
    return frame


def _to_markdown(frame: pd.DataFrame, title: str) -> str:
    lines = [title, "", "| " + " | ".join(frame.columns) + " |", "| " + " | ".join(["---"] * len(frame.columns)) + " |"]
    for _, row in frame.iterrows():
        lines.append("| " + " | ".join(str(row[col]).replace("\n", " ") for col in frame.columns) + " |")
    return "\n".join(lines)
