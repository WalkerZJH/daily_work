from __future__ import annotations

from collections import Counter
from pathlib import Path
from statistics import mean, median
from typing import Any

import pandas as pd
import yaml

from app.adapters.canonicalize import prepare_canonical_orders
from app.core.config import PROJECT_ROOT
from app.schemas.api import (
    DataSourceRequest,
    PAliveCandidateResult,
    PAliveExperimentConfig,
    PAliveExperimentResponse,
)
from app.schemas.config import AppConfig
from app.services.feature_service import FeatureService

PALIVE_CONFIG_PATH = PROJECT_ROOT / "config" / "palive_experiment.yaml"
PALIVE_MODELS = [
    "interval_survival_proxy",
    "bgnbd_candidate",
    "intermittent_overdue_proxy",
]


class PAliveExperimentService:
    def __init__(
        self,
        app_config: AppConfig,
        config_path: Path = PALIVE_CONFIG_PATH,
    ) -> None:
        self.app_config = app_config
        self.config_path = config_path

    def get_config(self) -> PAliveExperimentConfig:
        with self.config_path.open("r", encoding="utf-8") as file:
            raw = yaml.safe_load(file) or {}
        return PAliveExperimentConfig.model_validate(raw)

    def patch_config(self, patch: dict[str, Any]) -> PAliveExperimentConfig:
        current = self.get_config().model_dump()
        current.update(patch)
        updated = PAliveExperimentConfig.model_validate(current)
        with self.config_path.open("w", encoding="utf-8") as file:
            yaml.safe_dump(updated.model_dump(), file, allow_unicode=True, sort_keys=False)
        return updated

    def run_experiment(
        self,
        source: DataSourceRequest,
        as_of_date,
        enabled_models: list[str] | None = None,
    ) -> PAliveExperimentResponse:
        feature_run = FeatureService(self.app_config).run_preprocess(source, as_of_date)
        return self.run_on_orders(
            feature_run.prepared_orders,
            dataset_name=feature_run.dataset_name,
            as_of_date=as_of_date,
            config=self.get_config(),
            enabled_models=enabled_models,
            snapshot_features={
                snapshot.unit_id: snapshot.features
                for snapshot in feature_run.snapshots
                if snapshot.analysis_grain == "product_line"
            },
        )

    def run_on_orders(
        self,
        orders: pd.DataFrame,
        *,
        dataset_name: str,
        as_of_date,
        config: PAliveExperimentConfig | None = None,
        enabled_models: list[str] | None = None,
        snapshot_features: dict[str, dict[str, Any]] | None = None,
    ) -> PAliveExperimentResponse:
        selected_models = enabled_models or PALIVE_MODELS
        cfg = config or self.get_config()
        prepared = prepare_canonical_orders(
            _bundle_from_orders(orders, dataset_name)
        ) if _needs_canonicalize(orders) else orders.copy()
        prepared["order_time"] = pd.to_datetime(prepared["order_time"], errors="coerce")
        prepared = prepared[prepared["order_time"].notna()]
        prepared = prepared[prepared["order_time"].dt.date <= as_of_date].copy()

        summaries = self._unit_summaries(prepared, as_of_date, snapshot_features or {})
        results: list[PAliveCandidateResult] = []
        for summary in summaries:
            result = self._evaluate_unit(summary, summaries, cfg, selected_models, as_of_date)
            results.append(result)
        warning_summary: Counter[str] = Counter()
        for result in results:
            warning_summary.update(result.warnings)
        return PAliveExperimentResponse(
            dataset_name=dataset_name,
            as_of_date=as_of_date,
            config=cfg,
            unit_count=len(results),
            results=results,
            warning_summary=dict(warning_summary),
        )

    def _unit_summaries(
        self,
        orders: pd.DataFrame,
        as_of_date,
        snapshot_features: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if orders.empty:
            return []
        summaries: list[dict[str, Any]] = []
        group_cols = ["org_code", "product_line_code"]
        for (org_code, product_line_code), group in orders.groupby(group_cols, dropna=True):
            unit_id = f"{org_code}|product_line|{product_line_code}"
            sorted_orders = group.sort_values("order_time")
            purchase_dates = (
                sorted_orders["order_time"].dt.normalize().drop_duplicates().sort_values().tolist()
            )
            intervals = [
                float((purchase_dates[index] - purchase_dates[index - 1]).days)
                for index in range(1, len(purchase_dates))
                if (purchase_dates[index] - purchase_dates[index - 1]).days > 0
            ]
            last_purchase = purchase_dates[-1] if purchase_dates else None
            days_since = (
                float((pd.Timestamp(as_of_date) - last_purchase).days)
                if last_purchase is not None
                else None
            )
            feature = snapshot_features.get(unit_id, {})
            demand_profile = str(feature.get("demand_shape") or _infer_demand_profile(intervals))
            latest = sorted_orders.iloc[-1]
            summaries.append(
                {
                    "analysis_unit_id": unit_id,
                    "org_code": str(org_code),
                    "org_name": _value(latest, "org_name"),
                    "product_line_code": str(product_line_code),
                    "product_line_name": _value(latest, "product_line_name"),
                    "province": _value(latest, "province"),
                    "org_level": _value(latest, "org_level"),
                    "demand_profile": demand_profile,
                    "days_since_last_purchase": days_since,
                    "intervals": intervals,
                    "order_count": int(len(sorted_orders)),
                    "purchase_dates": [date.isoformat() for date in purchase_dates],
                    "snapshot_features": feature,
                }
            )
        return summaries

    def _evaluate_unit(
        self,
        unit: dict[str, Any],
        summaries: list[dict[str, Any]],
        cfg: PAliveExperimentConfig,
        enabled_models: list[str],
        as_of_date,
    ) -> PAliveCandidateResult:
        warnings: list[str] = [
            "PALIVE_EXPERIMENTAL_CANDIDATE",
            "PALIVE_NOT_CALIBRATED_AS_PROBABILITY",
        ]
        intervals = unit["intervals"]
        days_since = unit["days_since_last_purchase"]
        interval_stats = _interval_stats(intervals)

        p_interval = None
        interval_confidence = 0.0
        interval_debug: dict[str, Any] = {}
        if "interval_survival_proxy" in enabled_models:
            p_interval, interval_confidence, interval_debug, interval_warnings = (
                self._interval_survival_proxy(unit, summaries, cfg)
            )
            warnings.extend(interval_warnings)

        p_bgnbd = None
        bgnbd_debug: dict[str, Any] = {}
        if "bgnbd_candidate" in enabled_models:
            p_bgnbd, bgnbd_debug, bgnbd_warnings = self._bgnbd_candidate(unit, cfg)
            warnings.extend(bgnbd_warnings)

        p_intermit = None
        intermit_confidence = 0.0
        intermit_debug: dict[str, Any] = {}
        if "intermittent_overdue_proxy" in enabled_models:
            p_intermit, intermit_confidence, intermit_debug, intermit_warnings = (
                self._intermittent_overdue_proxy(unit, summaries, cfg)
            )
            warnings.extend(intermit_warnings)

        selected_model = "not_available"
        selected_p_alive = None
        confidence = 0.0
        if unit["demand_profile"] in {"intermittent", "lumpy"} and p_intermit is not None:
            selected_model = "intermittent_overdue_proxy"
            selected_p_alive = p_intermit
            confidence = intermit_confidence
            warnings.append("INTERMITTENT_PROFILE_AVOIDS_SIMPLE_TREND_DROP")
        elif p_interval is not None:
            selected_model = "interval_survival_proxy"
            selected_p_alive = p_interval
            confidence = interval_confidence
        elif p_bgnbd is not None:
            selected_model = "bgnbd_candidate"
            selected_p_alive = p_bgnbd
            confidence = min(0.4, interval_confidence)

        if len(intervals) < cfg.min_unit_intervals:
            warnings.append("COLD_START_LOW_CONFIDENCE")
            confidence = min(confidence, cfg.low_confidence_threshold)

        return PAliveCandidateResult(
            analysis_unit_id=unit["analysis_unit_id"],
            org_code=unit["org_code"],
            org_name=unit["org_name"],
            product_line_code=unit["product_line_code"],
            product_line_name=unit["product_line_name"],
            as_of_date=as_of_date,
            demand_profile=unit["demand_profile"],
            days_since_last_purchase=days_since,
            purchase_interval_stats=interval_stats,
            p_alive_proxy_interval=p_interval,
            p_alive_bgnbd=p_bgnbd,
            p_alive_intermit_proxy=p_intermit,
            selected_p_alive=selected_p_alive,
            selected_model_name=selected_model,
            model_confidence=round(float(confidence), 4),
            warnings=sorted(set(warnings)),
            debug_features={
                "interval_survival_proxy": interval_debug,
                "bgnbd_candidate": bgnbd_debug,
                "intermittent_overdue_proxy": intermit_debug,
                "order_count": unit["order_count"],
                "purchase_dates": unit["purchase_dates"],
                "snapshot_features": unit["snapshot_features"],
            },
        )

    def _interval_survival_proxy(
        self,
        unit: dict[str, Any],
        summaries: list[dict[str, Any]],
        cfg: PAliveExperimentConfig,
    ) -> tuple[float | None, float, dict[str, Any], list[str]]:
        warnings: list[str] = []
        days_since = unit["days_since_last_purchase"]
        if days_since is None:
            return None, 0.0, {}, ["NO_PURCHASE_HISTORY"]
        p_unit = _survival_fraction(unit["intervals"], days_since)
        cohort_intervals, cohort_key, cohort_warnings = self._cohort_intervals(unit, summaries, cfg)
        warnings.extend(cohort_warnings)
        p_cohort = _survival_fraction(cohort_intervals, days_since)
        n_intervals = len(unit["intervals"])
        if p_unit is None:
            warnings.append("UNIT_INTERVALS_INSUFFICIENT_USING_COHORT_PRIOR")
            p_unit = p_cohort
        if p_cohort is None:
            warnings.append("COHORT_INTERVALS_INSUFFICIENT")
            p_cohort = p_unit
        if p_unit is None:
            return None, 0.0, {"cohort_key": cohort_key}, warnings
        w = n_intervals / (n_intervals + cfg.interval_prior_k)
        p_alive = w * p_unit + (1 - w) * (p_cohort if p_cohort is not None else p_unit)
        confidence = min(0.9, 0.15 + 0.65 * w + min(len(cohort_intervals), 20) / 100)
        if n_intervals < cfg.min_unit_intervals:
            confidence = min(confidence, cfg.low_confidence_threshold)
        return (
            round(float(_clip01(p_alive)), 4),
            round(float(confidence), 4),
            {
                "d": days_since,
                "p_unit": p_unit,
                "p_cohort": p_cohort,
                "unit_interval_count": n_intervals,
                "cohort_interval_count": len(cohort_intervals),
                "cohort_key": cohort_key,
                "weight_unit_history": w,
            },
            warnings,
        )

    def _cohort_intervals(
        self,
        unit: dict[str, Any],
        summaries: list[dict[str, Any]],
        cfg: PAliveExperimentConfig,
    ) -> tuple[list[float], dict[str, Any], list[str]]:
        warnings: list[str] = []
        levels = [
            ("strict", ["product_line_code", "org_level", "province", "demand_profile"]),
            ("product_province", ["product_line_code", "province"]),
            ("product_line", ["product_line_code"]),
            ("global", []),
        ]
        for name, keys in levels:
            intervals: list[float] = []
            for other in summaries:
                if other["analysis_unit_id"] == unit["analysis_unit_id"]:
                    continue
                if all(other.get(key) == unit.get(key) for key in keys):
                    intervals.extend(other["intervals"])
            if len(intervals) >= cfg.min_cohort_intervals or name == "global":
                if name != "strict":
                    warnings.append(f"COHORT_PRIOR_FALLBACK_{name.upper()}")
                return intervals, {"level": name, "keys": keys}, warnings
        return [], {"level": "none", "keys": []}, ["COHORT_PRIOR_NOT_AVAILABLE"]

    def _bgnbd_candidate(
        self,
        unit: dict[str, Any],
        cfg: PAliveExperimentConfig,
    ) -> tuple[float | None, dict[str, Any], list[str]]:
        warnings = ["BGNBD_CANDIDATE_NOT_CALIBRATED"]
        if unit["order_count"] < cfg.bgnbd_min_orders:
            return (
                None,
                {"order_count": unit["order_count"], "min_orders": cfg.bgnbd_min_orders},
                warnings + ["BGNBD_INSUFFICIENT_HISTORY"],
            )
        try:
            import lifetimes  # type: ignore  # noqa: F401
        except Exception:
            return (
                None,
                {"dependency": "lifetimes"},
                warnings + ["BGNBD_DEPENDENCY_NOT_AVAILABLE"],
            )
        return (
            None,
            {"dependency": "lifetimes", "fit_attempted": False},
            warnings + ["BGNBD_FIT_NOT_ENABLED_IN_EXPERIMENT"],
        )

    def _intermittent_overdue_proxy(
        self,
        unit: dict[str, Any],
        summaries: list[dict[str, Any]],
        cfg: PAliveExperimentConfig,
    ) -> tuple[float | None, float, dict[str, Any], list[str]]:
        warnings: list[str] = []
        days_since = unit["days_since_last_purchase"]
        if days_since is None:
            return None, 0.0, {}, ["NO_PURCHASE_HISTORY"]
        intervals = unit["intervals"]
        if not intervals:
            cohort_intervals, cohort_key, cohort_warnings = self._cohort_intervals(unit, summaries, cfg)
            warnings.extend(cohort_warnings)
            intervals = cohort_intervals
            warnings.append("INTERMITTENT_USING_COHORT_PRIOR")
        else:
            cohort_key = {"level": "unit", "keys": ["analysis_unit_id"]}
        if not intervals:
            return None, 0.0, {"cohort_key": cohort_key}, warnings + ["INTERMITTENT_PRIOR_NOT_AVAILABLE"]
        expected_interval = float(mean(intervals))
        overdue_line = expected_interval * cfg.intermittent_overdue_multiplier
        p_alive = 1.0 / (1.0 + max(0.0, days_since - expected_interval) / max(overdue_line, 1.0))
        confidence = 0.25 + min(len(intervals), 10) / 25
        if unit["demand_profile"] not in {"intermittent", "lumpy"}:
            confidence = min(confidence, 0.45)
        if len(unit["intervals"]) < cfg.min_unit_intervals:
            confidence = min(confidence, cfg.low_confidence_threshold)
        return (
            round(float(_clip01(p_alive)), 4),
            round(float(min(confidence, 0.8)), 4),
            {
                "method": "croston_sba_inspired_interval_fallback",
                "expected_interval": expected_interval,
                "overdue_line": overdue_line,
                "cohort_key": cohort_key,
                "interval_count_used": len(intervals),
            },
            warnings,
        )


def _interval_stats(intervals: list[float]) -> dict[str, Any]:
    if not intervals:
        return {"count": 0}
    return {
        "count": len(intervals),
        "mean": round(float(mean(intervals)), 4),
        "median": round(float(median(intervals)), 4),
        "min": round(float(min(intervals)), 4),
        "max": round(float(max(intervals)), 4),
    }


def _survival_fraction(intervals: list[float], days_since: float) -> float | None:
    if not intervals:
        return None
    return sum(interval >= days_since for interval in intervals) / len(intervals)


def _infer_demand_profile(intervals: list[float]) -> str:
    if len(intervals) < 2:
        return "unknown"
    avg = mean(intervals)
    if avg <= 35:
        return "smooth"
    if avg <= 75:
        return "erratic"
    return "intermittent"


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _value(row: pd.Series, key: str) -> str | None:
    value = row.get(key)
    if pd.isna(value):
        return None
    return str(value)


def _needs_canonicalize(orders: pd.DataFrame) -> bool:
    return "order_time" not in orders.columns or "purchase_qty" not in orders.columns


def _bundle_from_orders(orders: pd.DataFrame, dataset_name: str):
    from app.adapters.base import DatasetBundle

    return DatasetBundle(
        dataset_name=dataset_name,
        orders=orders,
        drugs=pd.DataFrame(),
        orgs=pd.DataFrame(),
        product_line_mapping=pd.DataFrame(),
    )
