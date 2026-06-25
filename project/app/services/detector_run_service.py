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
    DetectorRuntimeConfig,
)
from app.schemas.config import AppConfig
from app.services.detector_config_service import DetectorRuntimeConfigService
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
        self.threshold_path = threshold_path
        self.thresholds = self._load_thresholds(threshold_path or PROJECT_ROOT / "configs" / "detector_thresholds.yaml")
        self.runtime_configs = DetectorRuntimeConfigService()
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
        if request.history_start_date is not None and "order_time" in orders.columns:
            orders = orders[orders["order_time"].dt.date >= request.history_start_date]
        if request.product_line_code and "product_line_code" in orders.columns:
            orders = orders[orders["product_line_code"].astype(str) == str(request.product_line_code)]
        valid_rows = int(effective_purchase_mask(orders).sum()) if not orders.empty else 0
        detector_ids = self._selected_detector_ids(request)
        time_scope = self._time_scope(request)
        results: list[DetectorRunResult] = []
        for detector_id in detector_ids:
            spec = DETECTOR_META[detector_id]
            results.extend(self._run_one(spec, orders, request))
        run_scope = self._run_scope(request)
        for result in results:
            result.as_of_date = request.as_of_date
            result.lookback_start_date = pd.Timestamp(time_scope["lookback_start_date"]).date()
            result.baseline_start_date = pd.Timestamp(time_scope["baseline_start_date"]).date()
            result.baseline_end_date = pd.Timestamp(time_scope["baseline_end_date"]).date()
            result.run_scope = run_scope
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
                **time_scope,
            },
            detector_results=limited_results,
            warning_summary=dict(warning_summary),
            debug={
                "dataset_name": feature_run.dataset_name,
                "source_type": source.source_type,
                "enabled_detectors": detector_ids,
                "result_limit": 50,
                "run_scope": self._run_scope(request),
            } if request.include_debug else {},
        )

    def _source_from_request(self, request: DetectorRunRequest) -> DataSourceRequest:
        date_to = request.as_of_date
        date_from = request.date_from or (date_to - timedelta(days=request.lookback_days or request.days))
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

    def _time_scope(self, request: DetectorRunRequest) -> dict[str, str]:
        lookback_days = request.lookback_days or request.days
        as_of = pd.Timestamp(request.as_of_date)
        lookback_start = as_of - pd.Timedelta(days=lookback_days)
        baseline_end = lookback_start - pd.Timedelta(days=1)
        baseline_start = baseline_end - pd.Timedelta(days=request.baseline_days)
        return {
            "as_of_date": request.as_of_date.isoformat(),
            "lookback_start_date": lookback_start.date().isoformat(),
            "baseline_start_date": baseline_start.date().isoformat(),
            "baseline_end_date": baseline_end.date().isoformat(),
        }

    def _run_scope(self, request: DetectorRunRequest) -> dict[str, Any]:
        return {
            "source_type": request.source_type,
            "enterprise_code": request.enterprise_code,
            "enterprise_name": request.enterprise_name,
            "province_code": request.province_code,
            "province_name": request.province_name or request.province,
            "product_line_code": request.product_line_code,
            "category": request.category,
            "enabled_detectors": request.enabled_detectors,
        }

    def _runtime_config(self, detector_id: str) -> tuple[DetectorRuntimeConfig, list[str]]:
        config, warnings = self.runtime_configs.get_config(detector_id)
        legacy = self.thresholds.get(detector_id)
        if legacy:
            params = dict(config.params)
            params.update(self._translate_legacy_params(detector_id, legacy))
            config = config.model_copy(update={"params": params})
        return config, warnings

    @staticmethod
    def _translate_legacy_params(detector_id: str, params: dict[str, Any]) -> dict[str, Any]:
        translated = dict(params)
        if detector_id == "low_delivery_rate_warning":
            translated["delivery_rate_threshold"] = translated.pop("default_threshold", translated.get("delivery_rate_threshold", 0.8))
        if detector_id == "delivery_delay_warning":
            translated["delay_hours_threshold"] = translated.pop("threshold_hours", translated.get("delay_hours_threshold", 48))
        if detector_id == "terminal_lost_warning":
            translated["inactive_days_multiplier"] = translated.pop("cycle_multiplier", translated.get("inactive_days_multiplier", 1.5))
        if detector_id == "new_terminal_warning":
            translated["new_terminal_min_qty"] = translated.pop("min_purchase_qty", translated.get("new_terminal_min_qty", 1))
        if detector_id in {"purchase_quantity_fluctuation_warning", "purchase_frequency_fluctuation_warning"}:
            translated["drop_rate_threshold"] = translated.pop("drop_ratio_threshold", translated.get("drop_rate_threshold", 0.5))
        return translated

    def _run_one(
        self,
        spec: DetectorMeta,
        orders: pd.DataFrame,
        request: DetectorRunRequest,
    ) -> list[DetectorRunResult]:
        if spec.status in {"interface_only", "blocked_by_missing_fields", "reserved"} or not spec.implemented:
            return [self._result(spec, False, 0, 0, spec.status.upper(), {}, [], [spec.notes or spec.status])]
        runtime_config, config_warnings = self._runtime_config(spec.detector_id)
        if not runtime_config.enabled:
            return [
                self._result(
                    spec,
                    False,
                    0,
                    0,
                    "DETECTOR_DISABLED_BY_CONFIG",
                    {"mode": runtime_config.mode},
                    [],
                    config_warnings,
                )
            ]
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
            return self._low_delivery_rate(spec, orders, runtime_config, config_warnings)
        if spec.detector_id == "delivery_delay_warning":
            return self._delivery_delay(spec, orders, runtime_config, config_warnings)
        if spec.detector_id == "delivery_rejection_warning":
            return self._delivery_rejection(spec, orders, runtime_config, config_warnings)
        if spec.detector_id == "low_price_warning":
            return self._low_price(spec, orders, runtime_config, config_warnings)
        if spec.detector_id == "price_spread_warning":
            return self._price_spread(spec, orders, runtime_config, config_warnings)
        if spec.detector_id == "terminal_lost_warning":
            return self._terminal_lost(spec, orders, request.as_of_date, runtime_config, config_warnings)
        if spec.detector_id == "new_terminal_warning":
            return self._new_terminal(spec, orders, request.as_of_date, runtime_config, config_warnings)
        if spec.detector_id == "purchase_quantity_fluctuation_warning":
            return self._quantity_fluctuation(spec, orders, request, runtime_config, config_warnings)
        if spec.detector_id == "purchase_frequency_fluctuation_warning":
            return self._frequency_fluctuation(spec, orders, request, runtime_config, config_warnings)
        return [self._result(spec, False, 0, 0, "DETECTOR_INTERFACE_ONLY", {}, [], ["该 detector 仅保留接口"])]

    def _low_delivery_rate(self, spec: DetectorMeta, orders: pd.DataFrame, runtime_config: DetectorRuntimeConfig | None = None, config_warnings: list[str] | None = None) -> list[DetectorRunResult]:
        results = []
        cfg = runtime_config.params if runtime_config else self.thresholds.get("low_delivery_rate_warning") or {}
        config_warnings = config_warnings or []
        province_thresholds = cfg.get("province_thresholds") or {}
        for _, row in orders.iterrows():
            threshold = float(province_thresholds.get(str(row.get("province")), cfg.get("delivery_rate_threshold", cfg.get("default_threshold", 0.8))))
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
                results.append(self._result(spec, True, min(100, (threshold - rate) / threshold * 100), 0.8, "DELIVERY_RATE_BELOW_THRESHOLD", metrics, [_order_evidence(row)], config_warnings))
        return results or [self._result(spec, False, 0, 0.7, "NO_LOW_DELIVERY_RATE_FOUND", {"threshold": float(cfg.get("delivery_rate_threshold", cfg.get("default_threshold", 0.8)))}, [], config_warnings)]

    def _delivery_delay(self, spec: DetectorMeta, orders: pd.DataFrame, runtime_config: DetectorRuntimeConfig | None = None, config_warnings: list[str] | None = None) -> list[DetectorRunResult]:
        cfg = runtime_config.params if runtime_config else self.thresholds.get("delivery_delay_warning") or {}
        config_warnings = config_warnings or []
        threshold_hours = float(cfg.get("delay_hours_threshold", cfg.get("threshold_hours", 48)))
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

    def _delivery_rejection(self, spec: DetectorMeta, orders: pd.DataFrame, runtime_config: DetectorRuntimeConfig | None = None, config_warnings: list[str] | None = None) -> list[DetectorRunResult]:
        cfg = runtime_config.params if runtime_config else {}
        config_warnings = config_warnings or []
        keywords = cfg.get("status_keywords") or []
        pattern = "|".join(str(item) for item in keywords) if keywords else REJECTION_PATTERN
        status = orders["order_status"].fillna("").astype(str)
        hits = orders[status.str.contains(pattern, regex=True)]
        results = []
        for _, row in hits.iterrows():
            metrics = {
                "order_status": _value(row, "order_status"),
                "distributor_name": _value(row, "distributor_name"),
                "purchase_qty": _float(row.get("purchase_qty")),
                "delivery_qty": _float(row.get("delivery_qty")),
            }
            results.append(self._result(spec, True, 80, 0.8, "DELIVERY_REJECTION_STATUS_MATCHED", metrics, [_order_evidence(row)], config_warnings))
        return results or [self._result(spec, False, 0, 0.8, "NO_REJECTION_STATUS_FOUND", {}, [], config_warnings)]

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

    def _low_price(self, spec: DetectorMeta, orders: pd.DataFrame, runtime_config: DetectorRuntimeConfig | None = None, config_warnings: list[str] | None = None) -> list[DetectorRunResult]:
        cfg = runtime_config.params if runtime_config else self.thresholds.get("low_price_warning") or {}
        mode = runtime_config.mode if runtime_config else "rule"
        config_warnings = config_warnings or []
        warning_price = cfg.get("warning_price")
        auto_baseline = None
        if warning_price is None and mode == "auto_baseline":
            auto_baseline = self._auto_low_price_threshold(orders, cfg)
            warning_price = auto_baseline.get("threshold")
        if warning_price is None:
            return [self._result(spec, False, 0, 0, "LOW_PRICE_THRESHOLD_NOT_CONFIGURED", {}, [], [*config_warnings, "缺少客户预警价配置，rule 模式下不能编造预警价"])]
        overrides: dict[str, Any] = cfg.get("overrides") or {}
        results = []
        for _, row in orders.iterrows():
            threshold = overrides.get(str(row.get("product_line_code")), overrides.get(str(row.get("drug_code")), warning_price))
            price = _float(row.get("comparable_unit_price"))
            if price is None:
                continue
            warnings = list(config_warnings)
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
                reason_code = "LOW_PRICE_BELOW_WARNING_PRICE"
                confidence = 0.75
                if auto_baseline is not None:
                    reason_code = "LOW_PRICE_BELOW_AUTO_BASELINE"
                    confidence = 0.45
                    metrics["auto_baseline"] = auto_baseline
                    metrics["auto_baseline_threshold"] = threshold
                    warnings.append("LOW_PRICE_AUTO_BASELINE_FOR_ALGORITHM_VALIDATION")
                results.append(self._result(spec, True, min(100, max(35, discount * 100)), confidence, reason_code, metrics, [_order_evidence(row)], warnings))
        return results or [self._result(spec, False, 0, 0.5, "NO_LOW_PRICE_FOUND", {"warning_price": warning_price, "auto_baseline": auto_baseline}, [], config_warnings)]

    def _auto_low_price_threshold(self, orders: pd.DataFrame, cfg: dict[str, Any]) -> dict[str, Any]:
        prices = pd.to_numeric(orders.get("comparable_unit_price"), errors="coerce").dropna()
        prices = prices[prices > 0]
        if prices.empty:
            return {"threshold": None, "method": cfg.get("auto_baseline_method", "mean_factor"), "warning": "NO_VALID_PRICE_HISTORY"}
        method = str(cfg.get("auto_baseline_method", "mean_factor"))
        if method == "quantile":
            q = float(cfg.get("auto_baseline_quantile", 0.1))
            threshold = float(prices.quantile(q))
            return {"threshold": threshold, "method": "quantile", "quantile": q, "sample_count": int(len(prices))}
        factor = float(cfg.get("auto_baseline_factor", 0.9))
        mean_price = float(prices.mean())
        threshold = mean_price * factor
        return {"threshold": threshold, "method": "mean_factor", "factor": factor, "historical_mean_price": mean_price, "sample_count": int(len(prices))}

    def _price_spread(self, spec: DetectorMeta, orders: pd.DataFrame, runtime_config: DetectorRuntimeConfig | None = None, config_warnings: list[str] | None = None) -> list[DetectorRunResult]:
        cfg = runtime_config.params if runtime_config else self.thresholds.get("price_spread_warning") or {}
        config_warnings = config_warnings or []
        threshold = float(cfg.get("spread_ratio_threshold", 1.8))
        results = []
        for product_line_code, group in orders.groupby("product_line_code", dropna=True):
            prices = pd.to_numeric(group["comparable_unit_price"], errors="coerce").dropna()
            if prices.empty:
                continue
            min_price = float(prices.min())
            max_price = float(prices.max())
            if min_price <= 0:
                results.append(self._result(spec, False, 0, 0, "PRICE_SPREAD_MIN_PRICE_NOT_POSITIVE", {"min_price": min_price, "max_price": max_price}, [], [*config_warnings, "最低价小于等于 0，跳过价差倍数判断"]))
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
                results.append(self._result(spec, True, min(100, max(45, (ratio / threshold - 1) * 80 + 45)), 0.75, "PRICE_SPREAD_RATIO_EXCEEDED", metrics, [_group_evidence(group)], config_warnings))
        return results or [self._result(spec, False, 0, 0.7, "NO_PRICE_SPREAD_FOUND", {"threshold": threshold}, [], config_warnings)]

    def _terminal_lost(self, spec: DetectorMeta, orders: pd.DataFrame, as_of_date, runtime_config: DetectorRuntimeConfig | None = None, config_warnings: list[str] | None = None) -> list[DetectorRunResult]:
        cfg = runtime_config.params if runtime_config else self.thresholds.get("terminal_lost_warning") or {}
        config_warnings = config_warnings or []
        multiplier = float(cfg.get("inactive_days_multiplier", cfg.get("cycle_multiplier", 1.5)))
        min_history_orders = int(cfg.get("min_history_orders", 2))
        results = []
        for (_, _), group in orders.groupby(["org_code", "product_line_code"], dropna=True):
            sorted_group = group.sort_values("order_time")
            dates = sorted_group["order_time"].dt.normalize().drop_duplicates().tolist()
            if len(dates) < min_history_orders:
                continue
            intervals = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates)) if (dates[i] - dates[i - 1]).days > 0]
            if not intervals:
                continue
            avg_cycle = sum(intervals) / len(intervals)
            days_since = (pd.Timestamp(as_of_date) - dates[-1]).days
            threshold = avg_cycle * multiplier
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
                warnings = list(config_warnings)
                if len(intervals) < 3:
                    warnings.append("TERMINAL_HISTORY_INTERVAL_SAMPLE_LOW")
                results.append(self._result(spec, True, min(100, max(45, days_since / max(threshold, 1) * 40)), 0.55 if len(intervals) < 3 else 0.75, "TERMINAL_OVERDUE_BY_PURCHASE_CYCLE", metrics, [_group_evidence(sorted_group)], warnings))
        return results or [self._result(spec, False, 0, 0.4, "NO_TERMINAL_LOST_SIGNAL", {}, [], [*config_warnings, "未发现超过历史采购周期阈值的分析单元，或历史样本不足"])]

    def _new_terminal(self, spec: DetectorMeta, orders: pd.DataFrame, as_of_date, runtime_config: DetectorRuntimeConfig | None = None, config_warnings: list[str] | None = None) -> list[DetectorRunResult]:
        cfg = runtime_config.params if runtime_config else self.thresholds.get("new_terminal_warning") or {}
        config_warnings = config_warnings or []
        min_qty = float(cfg.get("new_terminal_min_qty", cfg.get("min_purchase_qty", 1)))
        comeback_days = int(cfg.get("comeback_days", 180))
        recent_start = pd.Timestamp(as_of_date) - pd.Timedelta(days=30)
        results = []
        for (_, _), group in orders.groupby(["org_code", "product_line_code"], dropna=True):
            sorted_group = group.sort_values("order_time")
            recent = sorted_group[sorted_group["order_time"] >= recent_start]
            if recent.empty:
                continue
            latest = recent.iloc[-1]
            previous = sorted_group[sorted_group["order_time"] < latest["order_time"]]
            days_since_previous = None if previous.empty else (latest["order_time"] - previous["order_time"].max()).days
            purchase_qty = _float(latest.get("purchase_qty")) or 0.0
            first_or_reactivated = previous.empty or (days_since_previous is not None and days_since_previous >= comeback_days)
            if first_or_reactivated:
                warnings = list(config_warnings)
                if purchase_qty < min_qty:
                    warnings.append("NEW_TERMINAL_PURCHASE_QTY_BELOW_THRESHOLD")
                metrics = {
                    "first_order_date": latest["order_time"].date().isoformat(),
                    "no_purchase_180d": bool(previous.empty or (days_since_previous or 0) >= comeback_days),
                    "purchase_qty": purchase_qty,
                    "new_terminal_min_qty": min_qty,
                    "comeback_days": comeback_days,
                    "days_since_previous_purchase": days_since_previous,
                }
                results.append(self._result(spec, purchase_qty >= min_qty, 55 if purchase_qty >= min_qty else 15, 0.7 if purchase_qty >= min_qty else 0.25, "NEW_TERMINAL_OR_REACTIVATED", metrics, [_order_evidence(latest)], warnings))
        return results or [self._result(spec, False, 0, 0.5, "NO_NEW_TERMINAL_FOUND", {"new_terminal_min_qty": min_qty, "comeback_days": comeback_days}, [], config_warnings)]

    def _quantity_fluctuation(self, spec: DetectorMeta, orders: pd.DataFrame, request: DetectorRunRequest, runtime_config: DetectorRuntimeConfig | None = None, config_warnings: list[str] | None = None) -> list[DetectorRunResult]:
        cfg = runtime_config.params if runtime_config else self.thresholds.get("purchase_quantity_fluctuation_warning") or {}
        config_warnings = config_warnings or []
        lookback_days = request.lookback_days or request.days
        as_ts = pd.Timestamp(request.as_of_date)
        current_start = as_ts - pd.Timedelta(days=lookback_days)
        previous_start = current_start - pd.Timedelta(days=lookback_days)
        spike_threshold = float(cfg.get("spike_ratio_threshold", 3.0))
        drop_threshold = float(cfg.get("drop_rate_threshold", cfg.get("drop_ratio_threshold", 0.5)))
        results = []
        for (_, _), group in orders.groupby(["org_code", "product_line_code"], dropna=True):
            current = group[(group["order_time"] > current_start) & (group["order_time"] <= as_ts)]
            previous = group[(group["order_time"] > previous_start) & (group["order_time"] <= current_start)]
            current_qty = _sum(current, "purchase_qty")
            previous_qty = _sum(previous, "purchase_qty")
            metrics = {
                "current_qty": current_qty,
                "previous_qty": previous_qty,
                "current_window_start": current_start.date().isoformat(),
                "previous_window_start": previous_start.date().isoformat(),
                "spike_ratio_threshold": spike_threshold,
                "drop_rate_threshold": drop_threshold,
            }
            evidence = [_group_evidence(group)]
            if previous_qty > 0:
                ratio = current_qty / previous_qty
                drop_rate = (previous_qty - current_qty) / previous_qty
                metrics.update({"current_vs_previous_ratio": round(ratio, 4), "drop_rate": round(drop_rate, 4)})
                if drop_rate >= drop_threshold:
                    results.append(self._result(spec, True, min(100, max(45, drop_rate * 100)), 0.65, "SALES_QTY_DROP", metrics, evidence, config_warnings))
                elif ratio >= spike_threshold:
                    results.append(self._result(spec, True, min(100, max(45, ratio * 20)), 0.65, "SALES_QTY_SPIKE", metrics, evidence, config_warnings))
                else:
                    results.append(self._result(spec, False, 0, 0.55, "SALES_QTY_STABLE", metrics, evidence, config_warnings))
            elif current_qty > 0:
                metrics.update({"current_vs_previous_ratio": None, "drop_rate": None})
                results.append(self._result(spec, True, 45, 0.35, "SALES_QTY_FROM_ZERO_BASELINE", metrics, evidence, [*config_warnings, "上一窗口为 0，无法计算稳定倍数，仅作为低置信观察"]))
            else:
                metrics.update({"current_vs_previous_ratio": None, "drop_rate": None})
                results.append(self._result(spec, False, 0, 0.5, "SALES_QTY_NO_ACTIVITY_BOTH_WINDOWS", metrics, evidence, config_warnings))
        return results or [self._result(spec, False, 0, 0.5, "NO_PURCHASE_QTY_FLUCTUATION_FOUND", {}, [], config_warnings)]

    def _frequency_fluctuation(self, spec: DetectorMeta, orders: pd.DataFrame, request: DetectorRunRequest, runtime_config: DetectorRuntimeConfig | None = None, config_warnings: list[str] | None = None) -> list[DetectorRunResult]:
        cfg = runtime_config.params if runtime_config else self.thresholds.get("purchase_frequency_fluctuation_warning") or {}
        config_warnings = config_warnings or []
        lookback_days = request.lookback_days or request.days
        as_ts = pd.Timestamp(request.as_of_date)
        current_start = as_ts - pd.Timedelta(days=lookback_days)
        previous_start = current_start - pd.Timedelta(days=lookback_days)
        spike_threshold = float(cfg.get("spike_ratio_threshold", 2.0))
        drop_threshold = float(cfg.get("drop_rate_threshold", cfg.get("drop_ratio_threshold", 0.5)))
        results = []
        for (_, _), group in orders.groupby(["org_code", "product_line_code"], dropna=True):
            current_count = int(len(group[(group["order_time"] > current_start) & (group["order_time"] <= as_ts)]))
            previous_count = int(len(group[(group["order_time"] > previous_start) & (group["order_time"] <= current_start)]))
            metrics = {
                "current_freq_count": current_count,
                "previous_freq_count": previous_count,
                "current_window_start": current_start.date().isoformat(),
                "previous_window_start": previous_start.date().isoformat(),
                "spike_ratio_threshold": spike_threshold,
                "drop_rate_threshold": drop_threshold,
            }
            evidence = [_group_evidence(group)]
            if previous_count > 0:
                ratio = current_count / previous_count
                drop_rate = (previous_count - current_count) / previous_count
                metrics.update({"current_vs_previous_ratio": round(ratio, 4), "drop_rate": round(drop_rate, 4)})
                if drop_rate >= drop_threshold:
                    results.append(self._result(spec, True, min(100, max(45, drop_rate * 100)), 0.65, "SALES_FREQ_DROP", metrics, evidence, config_warnings))
                elif ratio >= spike_threshold:
                    results.append(self._result(spec, True, min(100, max(45, ratio * 20)), 0.65, "SALES_FREQ_SPIKE", metrics, evidence, config_warnings))
                else:
                    results.append(self._result(spec, False, 0, 0.55, "SALES_FREQ_STABLE", metrics, evidence, config_warnings))
            elif current_count > 0:
                metrics.update({"current_vs_previous_ratio": None, "drop_rate": None})
                results.append(self._result(spec, True, 45, 0.35, "SALES_FREQ_FROM_ZERO_BASELINE", metrics, evidence, [*config_warnings, "上一窗口为 0，无法计算稳定倍数，仅作为低置信观察"]))
            else:
                metrics.update({"current_vs_previous_ratio": None, "drop_rate": None})
                results.append(self._result(spec, False, 0, 0.5, "SALES_FREQ_NO_ACTIVITY_BOTH_WINDOWS", metrics, evidence, config_warnings))
        return results or [self._result(spec, False, 0, 0.5, "NO_PURCHASE_FREQUENCY_FLUCTUATION_FOUND", {}, [], config_warnings)]

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
            related_entities=_related_entities(evidence_items),
            sample_order_ids=_sample_order_ids(evidence_items),
            statistics=metrics,
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


def _sample_order_ids(evidence_items: list[dict[str, Any]]) -> list[str]:
    order_ids: list[str] = []
    for item in evidence_items:
        if item.get("order_id") is not None:
            order_ids.append(str(item["order_id"]))
        for order_id in item.get("sample_order_ids") or []:
            order_ids.append(str(order_id))
    return list(dict.fromkeys(order_ids))[:10]


def _related_entities(evidence_items: list[dict[str, Any]]) -> dict[str, Any]:
    entities: dict[str, set[str]] = {
        "org_codes": set(),
        "product_line_codes": set(),
        "drug_codes": set(),
        "distributors": set(),
        "provinces": set(),
    }
    for item in evidence_items:
        if item.get("org_code") is not None:
            entities["org_codes"].add(str(item["org_code"]))
        if item.get("product_line_code") is not None:
            entities["product_line_codes"].add(str(item["product_line_code"]))
        if item.get("drug_code") is not None:
            entities["drug_codes"].add(str(item["drug_code"]))
        if item.get("distributor_name") is not None:
            entities["distributors"].add(str(item["distributor_name"]))
        if item.get("province") is not None:
            entities["provinces"].add(str(item["province"]))
    return {key: sorted(value) for key, value in entities.items() if value}
