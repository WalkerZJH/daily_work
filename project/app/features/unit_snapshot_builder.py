from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from statistics import mean, median
from typing import Any

import pandas as pd

from app.features.feature_definitions import MODEL_FEATURE_COLUMNS
from app.features.label_builder import filter_effective_purchases


@dataclass(frozen=True)
class UnitSnapshotBuilderConfig:
    feature_windows: tuple[int, ...] = (30, 90, 180, 365)


class UnitSnapshotBuilder:
    def __init__(self, config: UnitSnapshotBuilderConfig | None = None) -> None:
        self.config = config or UnitSnapshotBuilderConfig()

    def build_current_snapshot(self, orders: pd.DataFrame, as_of_date: date) -> pd.DataFrame:
        units = self._units_available_before(orders, as_of_date)
        return self.build_for_units(orders, units, as_of_date)

    def build_for_units(
        self,
        orders: pd.DataFrame,
        units: pd.DataFrame,
        origin_date: date,
    ) -> pd.DataFrame:
        prepared = orders.copy()
        prepared["order_time"] = pd.to_datetime(prepared["order_time"], errors="coerce")
        prepared = prepared[prepared["order_time"].notna()]
        prepared = filter_effective_purchases(prepared)
        historical = prepared[prepared["order_time"].dt.date <= origin_date].copy()
        rows: list[dict[str, Any]] = []
        for _, unit in units.iterrows():
            org_code = str(unit["org_code"])
            product_line_code = str(unit["product_line_code"])
            scoped = historical[
                (historical["org_code"].astype(str) == org_code)
                & (historical["product_line_code"].astype(str) == product_line_code)
            ].copy()
            if scoped.empty:
                continue
            rows.append(self._build_row(scoped, org_code, product_line_code, origin_date))
        return pd.DataFrame(rows)

    def _units_available_before(self, orders: pd.DataFrame, origin_date: date) -> pd.DataFrame:
        frame = orders.copy()
        frame["order_time"] = pd.to_datetime(frame["order_time"], errors="coerce")
        frame = frame[frame["order_time"].notna()]
        frame = filter_effective_purchases(frame)
        frame = frame[frame["order_time"].dt.date <= origin_date]
        if frame.empty:
            return pd.DataFrame(columns=["org_code", "product_line_code"])
        return frame[["org_code", "product_line_code"]].dropna().drop_duplicates()

    def _build_row(
        self,
        scoped: pd.DataFrame,
        org_code: str,
        product_line_code: str,
        origin_date: date,
    ) -> dict[str, Any]:
        scoped = scoped.sort_values("order_time")
        latest = scoped.iloc[-1]
        first_ts = pd.Timestamp(scoped["order_time"].min())
        last_ts = pd.Timestamp(scoped["order_time"].max())
        intervals = _intervals(scoped)
        med_interval = _safe_median(intervals)
        mean_interval = _safe_mean(intervals)
        std_interval = float(pd.Series(intervals).std()) if len(intervals) >= 2 else None
        mad_interval = _mad(intervals)
        last_interval = intervals[-1] if intervals else None
        days_since = float((pd.Timestamp(origin_date) - last_ts.normalize()).days)
        interval_z = (
            (days_since - mean_interval) / std_interval
            if mean_interval is not None and std_interval not in {None, 0}
            else None
        )
        overdue_ratio = days_since / med_interval if med_interval not in {None, 0} else None

        row: dict[str, Any] = {
            "analysis_unit_id": f"{org_code}|product_line|{product_line_code}",
            "org_code": org_code,
            "org_name": _value(latest, "org_name"),
            "product_line_code": product_line_code,
            "product_line_name": _value(latest, "product_line_name"),
            "origin_date": origin_date,
            "province": _value(latest, "province"),
            "city": _value(latest, "city"),
            "county": _value(latest, "county"),
            "org_level": _value(latest, "org_level"),
            "org_level_detail": _value(latest, "org_level_detail"),
            "manufacturer_code": _value(latest, "manufacturer_code"),
            "manufacturer_name": _value(latest, "manufacturer_name"),
            "days_since_last_purchase": days_since,
            "first_purchase_days_ago": float((pd.Timestamp(origin_date) - first_ts.normalize()).days),
            "median_interval_days": med_interval,
            "mean_interval_days": mean_interval,
            "std_interval_days": std_interval,
            "mad_interval_days": mad_interval,
            "last_interval_days": last_interval,
            "interval_z_score": interval_z,
            "overdue_ratio": overdue_ratio,
        }
        row.update(self._window_features(scoped, origin_date))
        row.update(self._demand_shape(scoped, origin_date))
        for column in MODEL_FEATURE_COLUMNS:
            row.setdefault(column, None)
        return row

    def _window_features(self, scoped: pd.DataFrame, origin_date: date) -> dict[str, Any]:
        features: dict[str, Any] = {}
        origin = pd.Timestamp(origin_date)
        for window in self.config.feature_windows:
            start = origin - pd.Timedelta(days=window)
            current = scoped[(scoped["order_time"] > start) & (scoped["order_time"] <= origin)]
            suffix = f"{window}d"
            features[f"purchase_count_{suffix}"] = int(len(current))
            features[f"qty_{suffix}"] = _sum(current, "purchase_qty")
            features[f"amount_{suffix}"] = _sum(current, "purchase_amount")
        recent_90 = scoped[(scoped["order_time"] > origin - pd.Timedelta(days=90)) & (scoped["order_time"] <= origin)]
        base_365 = scoped[(scoped["order_time"] > origin - pd.Timedelta(days=365)) & (scoped["order_time"] <= origin - pd.Timedelta(days=90))]
        features["active_days_365d"] = int(
            scoped[scoped["order_time"] > origin - pd.Timedelta(days=365)]["order_time"].dt.date.nunique()
        )
        features["qty_recent_vs_base_ratio"] = _ratio(_sum(recent_90, "purchase_qty"), _sum(base_365, "purchase_qty"))
        features["amount_recent_vs_base_ratio"] = _ratio(
            _sum(recent_90, "purchase_amount"), _sum(base_365, "purchase_amount")
        )
        features["freq_30d"] = _count_window(scoped, origin, 30) / 30
        features["freq_90d"] = _count_window(scoped, origin, 90) / 90
        features["freq_recent_vs_base_ratio"] = _ratio(_count_window(scoped, origin, 90), _count_between(scoped, origin - pd.Timedelta(days=365), origin - pd.Timedelta(days=90)))
        features["sku_count_90d"] = _sku_count(recent_90)
        recent_365 = scoped[(scoped["order_time"] > origin - pd.Timedelta(days=365)) & (scoped["order_time"] <= origin)]
        features["sku_count_365d"] = _sku_count(recent_365)
        features["sku_shrink_ratio"] = _ratio(features["sku_count_365d"] - features["sku_count_90d"], features["sku_count_365d"])
        price_90 = pd.to_numeric(recent_90.get("comparable_unit_price"), errors="coerce") if "comparable_unit_price" in recent_90 else pd.Series(dtype=float)
        price_base = pd.to_numeric(base_365.get("comparable_unit_price"), errors="coerce") if "comparable_unit_price" in base_365 else pd.Series(dtype=float)
        features["avg_comparable_unit_price_90d"] = _series_mean(price_90)
        features["min_comparable_unit_price_90d"] = _series_min(price_90)
        features["max_comparable_unit_price_90d"] = _series_max(price_90)
        features["price_recent_vs_base_ratio"] = _ratio(_series_mean(price_90), _series_mean(price_base))
        features["delivery_rate_90d"] = _ratio(_sum(recent_90, "delivery_qty"), _sum(recent_90, "purchase_qty"))
        features["receipt_rate_90d"] = _ratio(_sum(recent_90, "receipt_qty"), _sum(recent_90, "purchase_qty"))
        features["delivery_delay_median"] = _delivery_delay_median(recent_90)
        status = recent_90.get("order_status", pd.Series(dtype=str)).fillna("").astype(str)
        features["refusal_status_count_90d"] = int(status.str.contains("拒绝|退货|无法配送|缺货|驳回", regex=True).sum())
        return features

    def _demand_shape(self, scoped: pd.DataFrame, origin_date: date) -> dict[str, Any]:
        origin = pd.Timestamp(origin_date)
        start = origin - pd.Timedelta(days=365)
        frame = scoped[(scoped["order_time"] > start) & (scoped["order_time"] <= origin)]
        if frame.empty:
            return {"adi": None, "cv2": None, "demand_profile": "unknown"}
        monthly = frame.set_index("order_time")["purchase_qty"].resample("MS").sum()
        months = pd.date_range(start=start.to_period("M").to_timestamp(), end=origin.to_period("M").to_timestamp(), freq="MS")
        monthly = monthly.reindex(months, fill_value=0)
        nonzero = monthly[monthly > 0]
        if len(nonzero) < 2:
            return {"adi": None, "cv2": None, "demand_profile": "unknown"}
        adi = float(len(monthly) / len(nonzero))
        avg = float(nonzero.mean())
        cv2 = 0.0 if avg == 0 else float((nonzero.std(ddof=0) / avg) ** 2)
        if adi < 1.32 and cv2 < 0.49:
            profile = "smooth"
        elif adi < 1.32:
            profile = "erratic"
        elif cv2 < 0.49:
            profile = "intermittent"
        else:
            profile = "lumpy"
        return {"adi": adi, "cv2": cv2, "demand_profile": profile}


def _intervals(scoped: pd.DataFrame) -> list[float]:
    dates = scoped["order_time"].dt.normalize().drop_duplicates().sort_values().tolist()
    return [float((dates[i] - dates[i - 1]).days) for i in range(1, len(dates)) if (dates[i] - dates[i - 1]).days > 0]


def _safe_mean(values: list[float]) -> float | None:
    return float(mean(values)) if values else None


def _safe_median(values: list[float]) -> float | None:
    return float(median(values)) if values else None


def _mad(values: list[float]) -> float | None:
    if not values:
        return None
    med = median(values)
    return float(median([abs(value - med) for value in values]))


def _value(row: pd.Series, key: str) -> Any:
    value = row.get(key)
    return None if pd.isna(value) else value


def _sum(frame: pd.DataFrame, column: str) -> float | None:
    if column not in frame.columns or frame.empty:
        return None
    series = pd.to_numeric(frame[column], errors="coerce")
    return float(series.sum()) if series.notna().any() else None


def _ratio(numerator: float | int | None, denominator: float | int | None) -> float | None:
    if numerator is None or denominator in {None, 0}:
        return None
    return float(numerator) / float(denominator)


def _count_window(scoped: pd.DataFrame, origin: pd.Timestamp, days: int) -> int:
    return int(len(scoped[(scoped["order_time"] > origin - pd.Timedelta(days=days)) & (scoped["order_time"] <= origin)]))


def _count_between(scoped: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> int:
    return int(len(scoped[(scoped["order_time"] > start) & (scoped["order_time"] <= end)]))


def _sku_count(frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    if "spec" in frame.columns:
        return int((frame["drug_code"].astype(str) + "|" + frame["spec"].fillna("").astype(str)).nunique())
    return int(frame["drug_code"].astype(str).nunique())


def _series_mean(series: pd.Series) -> float | None:
    clean = series.dropna()
    return float(clean.mean()) if not clean.empty else None


def _series_min(series: pd.Series) -> float | None:
    clean = series.dropna()
    return float(clean.min()) if not clean.empty else None


def _series_max(series: pd.Series) -> float | None:
    clean = series.dropna()
    return float(clean.max()) if not clean.empty else None


def _delivery_delay_median(frame: pd.DataFrame) -> float | None:
    if frame.empty or "delivery_time" not in frame.columns:
        return None
    delivery = pd.to_datetime(frame["delivery_time"], errors="coerce")
    order = pd.to_datetime(frame["order_time"], errors="coerce")
    delays = (delivery - order).dt.days.dropna()
    return float(delays.median()) if not delays.empty else None
