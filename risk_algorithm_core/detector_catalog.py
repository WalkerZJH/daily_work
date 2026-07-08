"""Detector capability and result-batch catalog tables."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .detector_config import DailyDetectorConfig, load_daily_detector_config


DETECTOR_CATALOG_SCHEMA_VERSION = "daily_detector_catalog_v1"
DETECTOR_OUTPUT_SCHEMA_VERSION = "daily_detector_clue_v1"


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
        "status": "interface_only",
        "enabled_by_default": False,
        "method": "requires_product_line_mapping",
        "required_fields": "drug_code,specification,dosage_form,product_line_code,baseline_active_sku_count,recent_active_sku_count",
        "optional_fields": "drug_category_code",
        "missing_fields": "product_line_code,portfolio_mapping,specification,dosage_form",
        "can_enter_v1_daily_detector": False,
        "backlog_only": True,
        "reason": "current entity grain is manufacturer-hospital-drug; true SKU shrink needs portfolio/product-line grouping",
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
        "status": "experimental",
        "enabled_by_default": False,
        "method": "reserved_three_stage_gap",
        "required_fields": "purchase_quantity,delivery_quantity,arrival_quantity,purchase_time,delivery_time,arrival_time,distributor_code",
        "optional_fields": "distributor_name",
        "missing_fields": "stable_delivery_time,stable_arrival_time",
        "can_enter_v1_daily_detector": False,
        "backlog_only": True,
        "reason": "delivery_time/received_time sentinel values make timing unreliable",
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
        "status": "reserved",
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


def build_detector_capability_matrix() -> pd.DataFrame:
    return _frame(CAPABILITY_ROWS)


def build_detector_catalog(config: DailyDetectorConfig | None = None) -> pd.DataFrame:
    cfg = config or load_daily_detector_config()
    rows = []
    for row in CAPABILITY_ROWS:
        detector_cfg = cfg.detectors.get(row["detector_id"], {})
        rows.append(
            {
                "detector_id": row["detector_id"],
                "detector_family": row["detector_family"],
                "detector_name": row["detector_name"],
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
