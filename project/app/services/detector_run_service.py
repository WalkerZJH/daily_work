from __future__ import annotations

import time
from collections import Counter
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from app.core.config import PROJECT_ROOT
from app.detectors.registry import DETECTOR_META, DetectorMeta
from app.features.label_builder import effective_purchase_mask
from app.schemas.api import (
    DataSourceRequest,
    DetectorRunRequest,
    DetectorRunResponse,
    DetectorRunResult,
)
from app.schemas.config import AppConfig
from app.services.detector_narrative_service import DetectorNarrativeService
from app.services.feature_service import FeatureService

DEMAND_DETECTOR_IDS = [
    "low_price_warning",
    "price_spread_warning",
    "delivery_rejection_warning",
    "delivery_delay_warning",
    "low_delivery_rate_warning",
    "terminal_lost_warning",
    "new_terminal_warning",
    "purchase_quantity_fluctuation_warning",
    "purchase_frequency_fluctuation_warning",
]

REJECTION_PATTERN = (
    "部分退货|过期配送|经营企业拒绝|拒绝|拒绝配送|拒绝确认|拒绝入库|拒绝收货|拒绝响应|"
    "配送企业无法配送|企业拒绝配送|企业配送撤废|全部退货|缺货|退货|未及时配送|"
    "无法配送|已驳回|已拒绝|异议撤单|拒收"
)


class DetectorRunService:
    def __init__(self, config: AppConfig, threshold_path: Path | None = None) -> None:
        self.config = config
        self.thresholds = self._load_thresholds(threshold_path or PROJECT_ROOT / "configs" / "detector_thresholds.yaml")
        self.narrative = DetectorNarrativeService()

    @staticmethod
    def _load_thresholds(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as file:
            raw = yaml.safe_load(file) or {}
        return raw if isinstance(raw, dict) else {}

    def run(self, request: DetectorRunRequest) -> DetectorRunResponse:
        started = time.perf_counter()
        source = self._source_from_request(request)
        feature_run = FeatureService(self.config).run_preprocess(source, request.as_of_date)
        orders = feature_run.prepared_orders.copy()
        if "order_time" in orders.columns:
            orders["order_time"] = pd.to_datetime(orders["order_time"], errors="coerce")
            orders = orders[orders["order_time"].notna()]
            orders = orders[orders["order_time"].dt.date <= request.as_of_date]
        valid_rows = int(effective_purchase_mask(orders).sum()) if not orders.empty else 0
        detector_ids = self._selected_detector_ids(request)
        results: list[DetectorRunResult] = []
        for detector_id in detector_ids:
            spec = DETECTOR_META[detector_id]
            results.extend(self._run_one(spec, orders, request))
        warning_summary: Counter[str] = Counter()
        for result in results:
            warning_summary.update(result.warnings)
        total_result_count = len(results)
        hit_count = sum(1 for result in results if result.hit)
        warning_count = sum(len(result.warnings) for result in results)
        limited_results = results[:50]
        implemented_count = sum(1 for detector_id in detector_ids if DETECTOR_META[detector_id].implemented)
        interface_count = sum(
            1
            for detector_id in detector_ids
            if DETECTOR_META[detector_id].status in {"interface_only", "blocked_by_missing_fields", "reserved"}
        )
        return DetectorRunResponse(
            summary={
                "loaded_rows": int(len(orders)),
                "valid_rows": valid_rows,
                "detector_count": len(detector_ids),
                "implemented_detector_count": implemented_count,
                "interface_only_detector_count": interface_count,
                "result_count": total_result_count,
                "returned_result_count": len(limited_results),
                "hit_count": hit_count,
                "warning_count": warning_count,
                "elapsed_seconds": round(time.perf_counter() - started, 4),
            },
            detector_results=limited_results,
            warning_summary=dict(warning_summary),
            debug={
                "dataset_name": feature_run.dataset_name,
                "source_type": source.source_type,
                "enabled_detectors": detector_ids,
                "result_limit": 50,
            } if request.include_debug else {},
        )

    def _source_from_request(self, request: DetectorRunRequest) -> DataSourceRequest:
        date_to = request.as_of_date
        date_from = request.date_from or (date_to - timedelta(days=request.days))
        source_type = "csv" if request.source_type == "sample" else request.source_type
        return DataSourceRequest(
            source_type=source_type,
            dataset_name=request.dataset_name or ("sample" if request.source_type == "sample" else None),
            csv_path=request.csv_path,
            date_from=date_from if source_type == "database" else request.date_from,
            date_to=date_to if source_type == "database" else request.date_to,
            enterprise_code=request.enterprise_code,
            province=request.province,
            province_code=request.province_code,
            row_limit=min(request.row_limit or 5000, 5000) if source_type == "database" else request.row_limit,
        )

    def _selected_detector_ids(self, request: DetectorRunRequest) -> list[str]:
        selected = request.enabled_detectors or DEMAND_DETECTOR_IDS
        output = []
        for detector_id in selected:
            if detector_id not in DETECTOR_META:
                continue
            spec = DETECTOR_META[detector_id]
            if request.category and spec.category != request.category:
                continue
            output.append(detector_id)
        return output

    def _run_one(
        self,
        spec: DetectorMeta,
        orders: pd.DataFrame,
        request: DetectorRunRequest,
    ) -> list[DetectorRunResult]:
        if spec.status in {"interface_only", "blocked_by_missing_fields", "reserved"} or not spec.implemented:
            return [self._result(spec, False, 0, 0, spec.status.upper(), {}, [], [spec.notes or spec.status])]
        missing = [field for field in spec.required_fields if field not in orders.columns]
        if missing:
            return [
                self._result(
                    spec,
                    False,
                    0,
                    0,
                    "MISSING_REQUIRED_FIELDS",
                    {"missing_fields": missing},
                    [],
                    ["缺少字段：" + ", ".join(missing)],
                )
            ]
        if orders.empty:
            return [self._result(spec, False, 0, 0, "NO_ROWS_AVAILABLE", {}, [], ["当前查询窗口无可用订单数据"])]
        if spec.detector_id == "low_delivery_rate_warning":
            return self._low_delivery_rate(spec, orders)
        if spec.detector_id == "delivery_delay_warning":
            return self._delivery_delay(spec, orders)
        if spec.detector_id == "delivery_rejection_warning":
            return self._delivery_rejection(spec, orders)
        if spec.detector_id == "low_price_warning":
            return self._low_price(spec, orders)
        if spec.detector_id == "price_spread_warning":
            return self._price_spread(spec, orders)
        if spec.detector_id == "terminal_lost_warning":
            return self._terminal_lost(spec, orders, request.as_of_date)
        if spec.detector_id == "new_terminal_warning":
            return self._new_terminal(spec, orders, request.as_of_date)
        if spec.detector_id == "purchase_quantity_fluctuation_warning":
            return self._quantity_fluctuation(spec, orders, request.as_of_date)
        if spec.detector_id == "purchase_frequency_fluctuation_warning":
            return self._frequency_fluctuation(spec, orders, request.as_of_date)
        return [self._result(spec, False, 0, 0, "DETECTOR_INTERFACE_ONLY", {}, [], ["该 detector 仅保留接口"])]

    def _low_delivery_rate(self, spec: DetectorMeta, orders: pd.DataFrame) -> list[DetectorRunResult]:
        results = []
        cfg = self.thresholds.get("low_delivery_rate_warning") or {}
        province_thresholds = cfg.get("province_thresholds") or {}
        for _, row in orders.iterrows():
            threshold = float(province_thresholds.get(str(row.get("province")), cfg.get("default_threshold", 0.8)))
            purchase_qty = _float(row.get("purchase_qty"))
            delivery_qty = _float(row.get("delivery_qty"))
            if purchase_qty is None or delivery_qty is None:
                continue
            if purchase_qty <= 0:
                results.append(
                    self._result(
                        spec,
                        False,
                        0,
                        0,
                        "PURCHASE_QTY_NOT_POSITIVE",
                        {"purchase_qty": purchase_qty, "delivery_qty": delivery_qty},
                        [_order_evidence(row)],
                        ["采购数量小于等于 0，无法计算有效配送率"],
                    )
                )
                continue
            rate = delivery_qty / purchase_qty
            if rate < threshold:
                metrics = {
                    "purchase_qty": purchase_qty,
                    "delivery_qty": delivery_qty,
                    "delivery_rate": rate,
                    "threshold": threshold,
                    "distributor_name": _value(row, "distributor_name"),
                }
                results.append(self._result(spec, True, min(100, (threshold - rate) / threshold * 100), 0.8, "DELIVERY_RATE_BELOW_THRESHOLD", metrics, [_order_evidence(row)], []))
        return results or [self._result(spec, False, 0, 0.7, "NO_LOW_DELIVERY_RATE_FOUND", {"threshold": float(cfg.get("default_threshold", 0.8))}, [], [])]

    def _delivery_delay(self, spec: DetectorMeta, orders: pd.DataFrame) -> list[DetectorRunResult]:
        threshold_hours = float((self.thresholds.get("delivery_delay_warning") or {}).get("threshold_hours", 48))
        frame = orders.copy()
        frame["order_time"] = pd.to_datetime(frame["order_time"], errors="coerce")
        frame["delivery_time"] = pd.to_datetime(frame["delivery_time"], errors="coerce")
        frame["delivery_delay_hours"] = (frame["delivery_time"] - frame["order_time"]).dt.total_seconds() / 3600
        results = []
        for _, row in frame[frame["delivery_delay_hours"] > threshold_hours].iterrows():
            metrics = {
                "order_time": _iso(row.get("order_time")),
                "delivery_time": _iso(row.get("delivery_time")),
                "delivery_delay_hours": round(float(row["delivery_delay_hours"]), 2),
                "threshold_hours": threshold_hours,
                "distributor_name": _value(row, "distributor_name"),
            }
            results.append(
                self._result(
                    spec,
                    True,
                    min(100, max(35, metrics["delivery_delay_hours"] / threshold_hours * 35)),
                    0.55,
                    "DELIVERY_DELAY_APPROX_BY_ORDER_TO_DELIVERY_TIME",
                    metrics,
                    [_order_evidence(row)],
                    ["当前缺少确认订单时间，使用 delivery_time - order_time 作为降级判断"],
                )
            )
        return results or [self._result(spec, False, 0, 0.5, "NO_DELIVERY_DELAY_FOUND", {"threshold_hours": threshold_hours}, [], ["当前口径使用 delivery_time - order_time 近似判断"])]

    def _delivery_rejection(self, spec: DetectorMeta, orders: pd.DataFrame) -> list[DetectorRunResult]:
        status = orders["order_status"].fillna("").astype(str)
        hits = orders[status.str.contains(REJECTION_PATTERN, regex=True)]
        results = []
        for _, row in hits.iterrows():
            metrics = {
                "order_status": _value(row, "order_status"),
                "distributor_name": _value(row, "distributor_name"),
                "purchase_qty": _float(row.get("purchase_qty")),
                "delivery_qty": _float(row.get("delivery_qty")),
            }
            results.append(self._result(spec, True, 80, 0.8, "DELIVERY_REJECTION_STATUS_MATCHED", metrics, [_order_evidence(row)], []))
        return results or [self._result(spec, False, 0, 0.8, "NO_REJECTION_STATUS_FOUND", {}, [], [])]

    def _low_price(self, spec: DetectorMeta, orders: pd.DataFrame) -> list[DetectorRunResult]:
        cfg = self.thresholds.get("low_price_warning") or {}
        warning_price = cfg.get("warning_price")
        overrides: dict[str, Any] = cfg.get("overrides") or {}
        if warning_price is None:
            return [self._result(spec, False, 0, 0, "MISSING_WARNING_PRICE_CONFIG", {}, [], ["缺少客户预警价配置，不能编造预警价"])]
        results = []
        for _, row in orders.iterrows():
            threshold = overrides.get(str(row.get("product_line_code")), overrides.get(str(row.get("drug_code")), warning_price))
            price = _float(row.get("comparable_unit_price"))
            if price is None:
                continue
            warnings = []
            if _float(row.get("conversion_factor")) in {None, 0}:
                warnings.append("转换系数缺失或无效，当前 comparable_unit_price 可能来自 fallback")
            threshold = float(threshold)
            if price < threshold:
                discount = (threshold - price) / max(threshold, 0.01)
                metrics = {
                    "comparable_unit_price": price,
                    "warning_price": threshold,
                    "price_discount_ratio": discount,
                    "purchase_amount": _float(row.get("purchase_amount")),
                }
                results.append(self._result(spec, True, min(100, max(35, discount * 100)), 0.75, "LOW_PRICE_BELOW_WARNING_PRICE", metrics, [_order_evidence(row)], warnings))
        return results or [self._result(spec, False, 0, 0.5, "NO_LOW_PRICE_FOUND", {"warning_price": warning_price}, [], [])]

    def _price_spread(self, spec: DetectorMeta, orders: pd.DataFrame) -> list[DetectorRunResult]:
        threshold = float((self.thresholds.get("price_spread_warning") or {}).get("spread_ratio_threshold", 1.8))
        results = []
        for product_line_code, group in orders.groupby("product_line_code", dropna=True):
            prices = pd.to_numeric(group["comparable_unit_price"], errors="coerce").dropna()
            if prices.empty:
                continue
            min_price = float(prices.min())
            max_price = float(prices.max())
            if min_price <= 0:
                results.append(self._result(spec, False, 0, 0, "PRICE_SPREAD_MIN_PRICE_NOT_POSITIVE", {"min_price": min_price, "max_price": max_price}, [], ["最低价小于等于 0，跳过价差倍数判断"]))
                continue
            ratio = max_price / min_price
            if ratio >= threshold:
                metrics = {
                    "product_line_code": str(product_line_code),
                    "min_price": min_price,
                    "max_price": max_price,
                    "price_spread_ratio": round(ratio, 4),
                    "threshold": threshold,
                    "sample_order_ids": group["order_id"].astype(str).head(10).tolist() if "order_id" in group.columns else [],
                }
                results.append(self._result(spec, True, min(100, max(45, (ratio / threshold - 1) * 80 + 45)), 0.75, "PRICE_SPREAD_RATIO_EXCEEDED", metrics, [_group_evidence(group)], []))
        return results or [self._result(spec, False, 0, 0.7, "NO_PRICE_SPREAD_FOUND", {"threshold": threshold}, [], [])]

    def _terminal_lost(self, spec: DetectorMeta, orders: pd.DataFrame, as_of_date) -> list[DetectorRunResult]:
        results = []
        for (org_code, product_line_code), group in orders.groupby(["org_code", "product_line_code"], dropna=True):
            sorted_group = group.sort_values("order_time")
            dates = sorted_group["order_time"].dt.normalize().drop_duplicates().tolist()
            if len(dates) < 2:
                continue
            intervals = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates)) if (dates[i] - dates[i - 1]).days > 0]
            if not intervals:
                continue
            avg_cycle = sum(intervals) / len(intervals)
            days_since = (pd.Timestamp(as_of_date) - dates[-1]).days
            threshold = avg_cycle * float((self.thresholds.get("terminal_lost_warning") or {}).get("cycle_multiplier", 1.5))
            avg_qty = float(pd.to_numeric(sorted_group["purchase_qty"], errors="coerce").dropna().mean())
            if days_since > threshold:
                metrics = {
                    "last_order_date": dates[-1].date().isoformat(),
                    "days_since_last_order": days_since,
                    "avg_purchase_cycle_days": round(avg_cycle, 2),
                    "avg_purchase_qty": round(avg_qty, 2),
                    "estimated_stockout_days": round(threshold, 2),
                    "lost_threshold_days": round(threshold, 2),
                }
                results.append(self._result(spec, True, min(100, max(45, days_since / max(threshold, 1) * 40)), 0.55 if len(intervals) < 3 else 0.75, "TERMINAL_OVERDUE_BY_PURCHASE_CYCLE", metrics, [_group_evidence(sorted_group)], [] if len(intervals) >= 3 else ["历史采购间隔样本较少，置信度降低"]))
        return results or [self._result(spec, False, 0, 0.4, "NO_TERMINAL_LOST_SIGNAL", {}, [], ["未发现超过历史采购周期阈值的分析单元，或历史样本不足"])]

    def _new_terminal(self, spec: DetectorMeta, orders: pd.DataFrame, as_of_date) -> list[DetectorRunResult]:
        results = []
        min_qty = float((self.thresholds.get("new_terminal_warning") or {}).get("min_purchase_qty", 1))
        recent_start = pd.Timestamp(as_of_date) - pd.Timedelta(days=30)
        for (org_code, product_line_code), group in orders.groupby(["org_code", "product_line_code"], dropna=True):
            sorted_group = group.sort_values("order_time")
            recent = sorted_group[sorted_group["order_time"] >= recent_start]
            if recent.empty:
                continue
            latest = recent.iloc[-1]
            previous = sorted_group[sorted_group["order_time"] < latest["order_time"]]
            days_since_previous = None
            if not previous.empty:
                days_since_previous = (latest["order_time"] - previous["order_time"].max()).days
            purchase_qty = _float(latest.get("purchase_qty")) or 0.0
            first_or_reactivated = previous.empty or (days_since_previous is not None and days_since_previous >= 180)
            if first_or_reactivated:
                warnings = [] if purchase_qty >= min_qty else ["采购数量低于新进终端数量阈值，作为低置信观察信号"]
                metrics = {
                    "first_order_date": latest["order_time"].date().isoformat(),
                    "no_purchase_180d": bool(previous.empty or (days_since_previous or 0) >= 180),
                    "purchase_qty": purchase_qty,
                    "new_terminal_min_qty": min_qty,
                    "days_since_previous_purchase": days_since_previous,
                }
                results.append(self._result(spec, purchase_qty >= min_qty, 55 if purchase_qty >= min_qty else 15, 0.7 if purchase_qty >= min_qty else 0.25, "NEW_TERMINAL_OR_REACTIVATED", metrics, [_order_evidence(latest)], warnings))
        return results or [self._result(spec, False, 0, 0.5, "NO_NEW_TERMINAL_FOUND", {"new_terminal_min_qty": min_qty}, [], [])]

    def _quantity_fluctuation(self, spec: DetectorMeta, orders: pd.DataFrame, as_of_date) -> list[DetectorRunResult]:
        results = []
        current_month_start = pd.Timestamp(as_of_date).replace(day=1)
        last_month_start = current_month_start - pd.DateOffset(months=1)
        six_month_start = pd.Timestamp(as_of_date) - pd.DateOffset(months=6)
        for (_, _), group in orders.groupby(["org_code", "product_line_code"], dropna=True):
            history = group[(group["order_time"] >= six_month_start) & (group["order_time"] < current_month_start)]
            current = group[group["order_time"] >= current_month_start]
            last_month = group[(group["order_time"] >= last_month_start) & (group["order_time"] < current_month_start)]
            avg_qty = float(pd.to_numeric(history["purchase_qty"], errors="coerce").dropna().mean()) if not history.empty else 0.0
            if not current.empty and avg_qty > 0:
                latest = current.iloc[-1]
                current_qty = _float(latest.get("purchase_qty")) or 0.0
                ratio = current_qty / avg_qty
                if ratio >= 3:
                    metrics = {"current_order_qty": current_qty, "avg_qty_last_6m": round(avg_qty, 4), "fluctuation_ratio": round(ratio, 4)}
                    results.append(self._result(spec, True, min(100, max(45, ratio * 20)), 0.65, "PURCHASE_QTY_ABOVE_6M_AVG", metrics, [_order_evidence(latest)], []))
            current_qty_sum = _sum(current, "purchase_qty")
            last_month_qty = _sum(last_month, "purchase_qty")
            if last_month_qty > 0 and current_qty_sum / last_month_qty <= 0.5:
                metrics = {"current_month_qty": current_qty_sum, "last_month_qty": last_month_qty, "fluctuation_ratio": round(current_qty_sum / last_month_qty, 4)}
                results.append(self._result(spec, True, 55, 0.55, "PURCHASE_QTY_MOM_DROP", metrics, [_group_evidence(group)], []))
        return results or [self._result(spec, False, 0, 0.5, "NO_PURCHASE_QTY_FLUCTUATION_FOUND", {}, [], [])]

    def _frequency_fluctuation(self, spec: DetectorMeta, orders: pd.DataFrame, as_of_date) -> list[DetectorRunResult]:
        results = []
        as_ts = pd.Timestamp(as_of_date)
        recent_start = as_ts - pd.Timedelta(days=30)
        six_month_start = as_ts - pd.DateOffset(months=6)
        last_month_start = as_ts.replace(day=1) - pd.DateOffset(months=1)
        current_month_start = as_ts.replace(day=1)
        for (_, _), group in orders.groupby(["org_code", "product_line_code"], dropna=True):
            recent_count = int(len(group[group["order_time"] >= recent_start]))
            six_month_count = int(len(group[(group["order_time"] >= six_month_start) & (group["order_time"] < recent_start)]))
            avg_monthly = six_month_count / 5 if six_month_count else 0
            if avg_monthly > 0 and recent_count / avg_monthly >= 2:
                metrics = {"purchase_count_30d": recent_count, "avg_monthly_frequency_6m": round(avg_monthly, 4), "fluctuation_ratio": round(recent_count / avg_monthly, 4)}
                results.append(self._result(spec, True, 60, 0.6, "PURCHASE_FREQUENCY_ABOVE_6M_AVG", metrics, [_group_evidence(group)], []))
            current_month_count = int(len(group[group["order_time"] >= current_month_start]))
            last_month_count = int(len(group[(group["order_time"] >= last_month_start) & (group["order_time"] < current_month_start)]))
            if last_month_count > 0 and current_month_count / last_month_count <= 0.5:
                metrics = {"current_month_frequency": current_month_count, "last_month_frequency": last_month_count, "fluctuation_ratio": round(current_month_count / last_month_count, 4)}
                results.append(self._result(spec, True, 55, 0.55, "PURCHASE_FREQUENCY_MOM_DROP", metrics, [_group_evidence(group)], []))
        return results or [self._result(spec, False, 0, 0.5, "NO_PURCHASE_FREQUENCY_FLUCTUATION_FOUND", {}, [], [])]

    def _result(
        self,
        spec: DetectorMeta,
        hit: bool,
        severity: float,
        confidence: float,
        reason_code: str,
        metrics: dict[str, Any],
        evidence_items: list[dict[str, Any]],
        warnings: list[str],
    ) -> DetectorRunResult:
        return DetectorRunResult(
            detector_id=spec.detector_id,
            detector_name=spec.name,
            name_zh=spec.name_zh or spec.name,
            category=spec.category,
            status=spec.status,
            hit=hit,
            severity=round(float(max(0, min(100, severity))), 4),
            confidence=round(float(max(0, min(1, confidence))), 4),
            reason_code=reason_code,
            metrics=metrics,
            evidence_items=evidence_items,
            warnings=warnings,
            narrative=self.narrative.build(
                detector_id=spec.detector_id,
                hit=hit,
                reason_code=reason_code,
                metrics=metrics,
                warnings=warnings,
            ),
        )


def _float(value: Any) -> float | None:
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _value(row: pd.Series, field: str) -> Any:
    value = row.get(field)
    return None if pd.isna(value) else value


def _iso(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).isoformat()


def _sum(frame: pd.DataFrame, column: str) -> float:
    if frame.empty or column not in frame.columns:
        return 0.0
    return float(pd.to_numeric(frame[column], errors="coerce").fillna(0).sum())


def _order_evidence(row: pd.Series) -> dict[str, Any]:
    fields = [
        "order_id",
        "order_detail_id",
        "order_time",
        "org_code",
        "org_name",
        "product_line_code",
        "product_line_name",
        "drug_code",
        "distributor_name",
        "province",
        "purchase_qty",
        "delivery_qty",
        "purchase_amount",
        "comparable_unit_price",
        "order_status",
    ]
    payload = {}
    for field in fields:
        value = row.get(field)
        if value is None or pd.isna(value):
            continue
        payload[field] = _iso(value) if field.endswith("_time") else value
    return payload


def _group_evidence(group: pd.DataFrame) -> dict[str, Any]:
    return {
        "sample_order_ids": group["order_id"].astype(str).head(10).tolist() if "order_id" in group.columns else [],
        "row_count": int(len(group)),
        "org_code": str(group.iloc[0].get("org_code")) if not group.empty else None,
        "product_line_code": str(group.iloc[0].get("product_line_code")) if not group.empty else None,
    }
