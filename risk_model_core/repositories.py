"""Repository layer for standard risk result batches."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
import json
import os

import pandas as pd

from .manifest import RiskResultManifest, load_manifest
from .schemas import STANDARD_TABLES


class RiskResultRepository(ABC):
    @abstractmethod
    def manifest(self) -> RiskResultManifest:
        raise NotImplementedError

    @abstractmethod
    def load_table(self, name: str) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def list_risk_entities(self, **filters: Any) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def list_rankable_entities(
        self,
        *,
        manufacturer_codes: list[str] | None = None,
        report_month: str | None = None,
        horizon: str | None = None,
        candidate_type: str | list[str] | None = None,
        sort_by: str | list[str] | None = None,
        ascending: bool = False,
        limit: int | None = None,
    ) -> pd.DataFrame:
        """Return sortable result-batch rows within a backend-resolved scope."""
        raise NotImplementedError

    @abstractmethod
    def list_risk_entity_horizon_profiles(
        self,
        risk_entity_id: str | None = None,
        report_month: str | None = None,
        horizon: str | None = None,
        **filters: Any,
    ) -> pd.DataFrame:
        """Return per-horizon result-batch profile rows for frontend switching."""
        raise NotImplementedError

    @abstractmethod
    def get_risk_entity(self, risk_entity_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def list_risk_cards(self, risk_entity_id: str) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def list_evidence(self, risk_card_id: str) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def list_timeline(self, risk_entity_id: str) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def list_hospital_aggregates(self, **filters: Any) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def list_drug_aggregates(self, **filters: Any) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def list_monthly_reports(self, **filters: Any) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def list_proof_cases(self, **filters: Any) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def load_entity_display_lookup(self, **filters: Any) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def list_detector_catalog(self, **filters: Any) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def list_daily_detector_runs(self, **filters: Any) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def list_daily_detector_clues(self, **filters: Any) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def list_high_risk_detector_evidence(self, risk_entity_id: str | None = None, detector_run_id: str | None = None, **filters: Any) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def get_page_payload(self, page_name: str) -> dict[str, Any]:
        raise NotImplementedError


class ParquetRiskResultRepository(RiskResultRepository):
    """Read a standard result batch from parquet, with csv fallback for fixtures."""

    def __init__(self, batch_dir: str | Path):
        self.batch_dir = Path(batch_dir)
        self._manifest = load_manifest(self.batch_dir)

    def manifest(self) -> RiskResultManifest:
        return self._manifest

    def load_table(self, name: str) -> pd.DataFrame:
        if name not in STANDARD_TABLES:
            raise ValueError(f"Unknown standard table: {name}")
        parquet = self.batch_dir / f"{name}.parquet"
        csv = self.batch_dir / f"{name}.csv"
        if parquet.exists():
            return pd.read_parquet(parquet)
        if csv.exists():
            return pd.read_csv(csv)
        return pd.DataFrame()

    def list_risk_entities(self, **filters: Any) -> pd.DataFrame:
        return apply_filters(self.load_table("risk_entities"), filters)

    def list_rankable_entities(
        self,
        *,
        manufacturer_codes: list[str] | None = None,
        report_month: str | None = None,
        horizon: str | None = None,
        candidate_type: str | list[str] | None = None,
        sort_by: str | list[str] | None = None,
        ascending: bool = False,
        limit: int | None = None,
    ) -> pd.DataFrame:
        return select_rankable_entities(
            self.load_table("risk_entities"),
            manufacturer_codes=manufacturer_codes,
            report_month=report_month,
            horizon=horizon,
            candidate_type=candidate_type,
            sort_by=sort_by,
            ascending=ascending,
            limit=limit,
        )

    def list_risk_entity_horizon_profiles(
        self,
        risk_entity_id: str | None = None,
        report_month: str | None = None,
        horizon: str | None = None,
        **filters: Any,
    ) -> pd.DataFrame:
        normalized = dict(filters)
        if risk_entity_id is not None:
            normalized["risk_entity_id"] = risk_entity_id
        if report_month is not None:
            normalized["report_month"] = report_month
        if horizon is not None:
            normalized["horizon"] = horizon
        return apply_filters(self.load_table("risk_entity_horizon_profiles"), normalized)

    def get_risk_entity(self, risk_entity_id: str) -> dict[str, Any] | None:
        df = self.load_table("risk_entities")
        row = df[df["risk_entity_id"].astype(str).eq(str(risk_entity_id))]
        return None if row.empty else row.iloc[0].to_dict()

    def list_risk_cards(self, risk_entity_id: str) -> pd.DataFrame:
        df = self.load_table("risk_cards")
        if df.empty or "risk_entity_id" not in df:
            return df.iloc[0:0].copy()
        return df[df["risk_entity_id"].astype(str).eq(str(risk_entity_id))]

    def list_evidence(self, risk_card_id: str) -> pd.DataFrame:
        df = self.load_table("risk_card_evidence")
        if df.empty or "risk_card_id" not in df:
            return df.iloc[0:0].copy()
        return df[df["risk_card_id"].astype(str).eq(str(risk_card_id))]

    def list_timeline(self, risk_entity_id: str) -> pd.DataFrame:
        df = self.load_table("risk_entity_timeline")
        return df if df.empty else df.query("risk_entity_id == @risk_entity_id")

    def list_hospital_aggregates(self, **filters: Any) -> pd.DataFrame:
        return apply_filters(self.load_table("hospital_aggregates"), filters)

    def list_drug_aggregates(self, **filters: Any) -> pd.DataFrame:
        return apply_filters(self.load_table("drug_aggregates"), filters)

    def list_monthly_reports(self, **filters: Any) -> pd.DataFrame:
        return apply_filters(self.load_table("monthly_reports"), filters)

    def list_proof_cases(self, **filters: Any) -> pd.DataFrame:
        return apply_filters(self.load_table("proof_cases"), filters)

    def load_entity_display_lookup(self, **filters: Any) -> pd.DataFrame:
        return apply_filters(self.load_table("entity_display_lookup"), normalize_entity_display_lookup_filters(filters))

    def list_detector_catalog(self, **filters: Any) -> pd.DataFrame:
        return apply_filters(self.load_table("detector_catalog"), filters)

    def list_daily_detector_runs(self, **filters: Any) -> pd.DataFrame:
        return apply_filters(self.load_table("daily_detector_runs"), filters)

    def list_daily_detector_clues(self, **filters: Any) -> pd.DataFrame:
        return apply_filters(self.load_table("daily_detector_clues"), filters)

    def list_high_risk_detector_evidence(self, risk_entity_id: str | None = None, detector_run_id: str | None = None, **filters: Any) -> pd.DataFrame:
        normalized = dict(filters)
        if risk_entity_id is not None:
            normalized["risk_entity_id"] = risk_entity_id
        if detector_run_id is not None:
            normalized["detector_run_id"] = detector_run_id
        return apply_filters(self.load_table("high_risk_detector_evidence"), normalized)

    def get_page_payload(self, page_name: str) -> dict[str, Any]:
        clean = page_name[:-5] if page_name.endswith(".json") else page_name
        candidates = [
            self.batch_dir / "page_payloads" / f"{clean}.json",
            self.batch_dir / "page_payloads" / f"{clean}_payload.json",
        ]
        for path in candidates:
            if path_exists(path):
                with open(long_path(path), encoding="utf-8") as fh:
                    return json.load(fh)
        raise FileNotFoundError(f"Page payload not found: {page_name}")


class InMemoryRiskResultRepository(RiskResultRepository):
    def __init__(self, manifest: RiskResultManifest, tables: dict[str, pd.DataFrame], payloads: dict[str, dict[str, Any]] | None = None):
        self._manifest = manifest
        self.tables = tables
        self.payloads = payloads or {}

    def manifest(self) -> RiskResultManifest:
        return self._manifest

    def load_table(self, name: str) -> pd.DataFrame:
        return self.tables.get(name, pd.DataFrame()).copy()

    def list_risk_entities(self, **filters: Any) -> pd.DataFrame:
        return apply_filters(self.load_table("risk_entities"), filters)

    def list_rankable_entities(
        self,
        *,
        manufacturer_codes: list[str] | None = None,
        report_month: str | None = None,
        horizon: str | None = None,
        candidate_type: str | list[str] | None = None,
        sort_by: str | list[str] | None = None,
        ascending: bool = False,
        limit: int | None = None,
    ) -> pd.DataFrame:
        return select_rankable_entities(
            self.load_table("risk_entities"),
            manufacturer_codes=manufacturer_codes,
            report_month=report_month,
            horizon=horizon,
            candidate_type=candidate_type,
            sort_by=sort_by,
            ascending=ascending,
            limit=limit,
        )

    def list_risk_entity_horizon_profiles(
        self,
        risk_entity_id: str | None = None,
        report_month: str | None = None,
        horizon: str | None = None,
        **filters: Any,
    ) -> pd.DataFrame:
        normalized = dict(filters)
        if risk_entity_id is not None:
            normalized["risk_entity_id"] = risk_entity_id
        if report_month is not None:
            normalized["report_month"] = report_month
        if horizon is not None:
            normalized["horizon"] = horizon
        return apply_filters(self.load_table("risk_entity_horizon_profiles"), normalized)

    def get_risk_entity(self, risk_entity_id: str) -> dict[str, Any] | None:
        rows = self.list_risk_entities(risk_entity_id=risk_entity_id)
        return None if rows.empty else rows.iloc[0].to_dict()

    def list_risk_cards(self, risk_entity_id: str) -> pd.DataFrame:
        df = self.load_table("risk_cards")
        if df.empty or "risk_entity_id" not in df:
            return df.iloc[0:0].copy()
        return df[df["risk_entity_id"].astype(str).eq(str(risk_entity_id))]

    def list_evidence(self, risk_card_id: str) -> pd.DataFrame:
        df = self.load_table("risk_card_evidence")
        if df.empty or "risk_card_id" not in df:
            return df.iloc[0:0].copy()
        return df[df["risk_card_id"].astype(str).eq(str(risk_card_id))]

    def list_timeline(self, risk_entity_id: str) -> pd.DataFrame:
        df = self.load_table("risk_entity_timeline")
        return df if df.empty else df.query("risk_entity_id == @risk_entity_id")

    def list_hospital_aggregates(self, **filters: Any) -> pd.DataFrame:
        return apply_filters(self.load_table("hospital_aggregates"), filters)

    def list_drug_aggregates(self, **filters: Any) -> pd.DataFrame:
        return apply_filters(self.load_table("drug_aggregates"), filters)

    def list_monthly_reports(self, **filters: Any) -> pd.DataFrame:
        return apply_filters(self.load_table("monthly_reports"), filters)

    def list_proof_cases(self, **filters: Any) -> pd.DataFrame:
        return apply_filters(self.load_table("proof_cases"), filters)

    def load_entity_display_lookup(self, **filters: Any) -> pd.DataFrame:
        return apply_filters(self.load_table("entity_display_lookup"), normalize_entity_display_lookup_filters(filters))

    def list_detector_catalog(self, **filters: Any) -> pd.DataFrame:
        return apply_filters(self.load_table("detector_catalog"), filters)

    def list_daily_detector_runs(self, **filters: Any) -> pd.DataFrame:
        return apply_filters(self.load_table("daily_detector_runs"), filters)

    def list_daily_detector_clues(self, **filters: Any) -> pd.DataFrame:
        return apply_filters(self.load_table("daily_detector_clues"), filters)

    def list_high_risk_detector_evidence(self, risk_entity_id: str | None = None, detector_run_id: str | None = None, **filters: Any) -> pd.DataFrame:
        normalized = dict(filters)
        if risk_entity_id is not None:
            normalized["risk_entity_id"] = risk_entity_id
        if detector_run_id is not None:
            normalized["detector_run_id"] = detector_run_id
        return apply_filters(self.load_table("high_risk_detector_evidence"), normalized)

    def get_page_payload(self, page_name: str) -> dict[str, Any]:
        key = page_name[:-5] if page_name.endswith(".json") else page_name
        if key not in self.payloads:
            raise FileNotFoundError(key)
        return self.payloads[key]


class ClickHouseRiskResultRepository(RiskResultRepository):
    """Reserved repository stub for backend storage integration.

    This repository reads result-batch serving tables only. It must not read raw business/source tables.
    """

    def __init__(self, *_: Any, **__: Any):
        pass

    def manifest(self) -> RiskResultManifest:
        raise NotImplementedError("ClickHouse repository is a storage stub.")

    def load_table(self, name: str) -> pd.DataFrame:
        raise NotImplementedError("ClickHouse repository is a storage stub.")

    def list_risk_entities(self, **filters: Any) -> pd.DataFrame:
        raise NotImplementedError("ClickHouse repository is a storage stub.")

    def list_rankable_entities(
        self,
        *,
        manufacturer_codes: list[str] | None = None,
        report_month: str | None = None,
        horizon: str | None = None,
        candidate_type: str | list[str] | None = None,
        sort_by: str | list[str] | None = None,
        ascending: bool = False,
        limit: int | None = None,
    ) -> pd.DataFrame:
        raise NotImplementedError("ClickHouse repository is a storage stub.")

    def list_risk_entity_horizon_profiles(
        self,
        risk_entity_id: str | None = None,
        report_month: str | None = None,
        horizon: str | None = None,
        **filters: Any,
    ) -> pd.DataFrame:
        raise NotImplementedError("ClickHouse repository is a storage stub.")

    def get_risk_entity(self, risk_entity_id: str) -> dict[str, Any] | None:
        raise NotImplementedError("ClickHouse repository is a storage stub.")

    def list_risk_cards(self, risk_entity_id: str) -> pd.DataFrame:
        raise NotImplementedError("ClickHouse repository is a storage stub.")

    def list_evidence(self, risk_card_id: str) -> pd.DataFrame:
        raise NotImplementedError("ClickHouse repository is a storage stub.")

    def list_timeline(self, risk_entity_id: str) -> pd.DataFrame:
        raise NotImplementedError("ClickHouse repository is a storage stub.")

    def list_hospital_aggregates(self, **filters: Any) -> pd.DataFrame:
        raise NotImplementedError("ClickHouse repository is a storage stub.")

    def list_drug_aggregates(self, **filters: Any) -> pd.DataFrame:
        raise NotImplementedError("ClickHouse repository is a storage stub.")

    def list_monthly_reports(self, **filters: Any) -> pd.DataFrame:
        raise NotImplementedError("ClickHouse repository is a storage stub.")

    def list_proof_cases(self, **filters: Any) -> pd.DataFrame:
        raise NotImplementedError("ClickHouse repository is a storage stub.")

    def load_entity_display_lookup(self, **filters: Any) -> pd.DataFrame:
        raise NotImplementedError("ClickHouse repository is a storage stub.")

    def list_detector_catalog(self, **filters: Any) -> pd.DataFrame:
        raise NotImplementedError("ClickHouse repository is a storage stub.")

    def list_daily_detector_runs(self, **filters: Any) -> pd.DataFrame:
        raise NotImplementedError("ClickHouse repository is a storage stub.")

    def list_daily_detector_clues(self, **filters: Any) -> pd.DataFrame:
        raise NotImplementedError("ClickHouse repository is a storage stub.")

    def list_high_risk_detector_evidence(self, risk_entity_id: str | None = None, detector_run_id: str | None = None, **filters: Any) -> pd.DataFrame:
        raise NotImplementedError("ClickHouse repository is a storage stub.")

    def get_page_payload(self, page_name: str) -> dict[str, Any]:
        raise NotImplementedError("ClickHouse repository is a storage stub.")


def apply_filters(df: pd.DataFrame, filters: dict[str, Any]) -> pd.DataFrame:
    out = df.copy()
    for key, value in filters.items():
        if value is None or key not in out:
            continue
        if isinstance(value, (list, tuple, set)):
            allowed = {str(item) for item in value}
            out = out[out[key].astype(str).isin(allowed)]
        else:
            out = out[out[key].astype(str).eq(str(value))]
    return out


def normalize_entity_display_lookup_filters(filters: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(filters)
    manufacturer_codes = normalized.pop("manufacturer_codes", None)
    if manufacturer_codes is not None:
        normalized["manufacturer_code"] = manufacturer_codes
    return normalized


DEFAULT_RANKABLE_SORT_FIELDS = [
    "business_priority_score",
    "risk_score_display",
    "risk_probability_value",
    "value_at_risk_proxy",
    "recent_order_amount",
    "avg_order_amount",
    "purchase_interval_overdue_score",
    "purchase_frequency_drop_score",
]


def select_rankable_entities(
    df: pd.DataFrame,
    *,
    manufacturer_codes: list[str] | None = None,
    report_month: str | None = None,
    horizon: str | None = None,
    candidate_type: str | list[str] | None = None,
    sort_by: str | list[str] | None = None,
    ascending: bool = False,
    limit: int | None = None,
) -> pd.DataFrame:
    """Filter and sort entity rows for a backend-resolved user scope.

    The model layer intentionally treats ``manufacturer_codes`` as an already
    resolved visibility set from the backend. It does not infer users from
    manufacturers and does not fill a minimum worklist size.
    """
    out = df.copy()
    if out.empty:
        return out
    if manufacturer_codes is not None:
        if not manufacturer_codes:
            return out.iloc[0:0].copy()
        out = out[out["manufacturer_code"].astype(str).isin({str(code) for code in manufacturer_codes})]
    if report_month is not None and "report_month" in out:
        out = out[out["report_month"].astype(str).eq(str(report_month))]
    if horizon is not None:
        horizon_col = "primary_horizon" if "primary_horizon" in out else "horizon"
        if horizon_col in out:
            out = out[out[horizon_col].astype(str).eq(str(horizon))]
    if candidate_type is not None:
        out = out[_candidate_type_mask(out, candidate_type)]

    sort_fields = _rank_sort_fields(out, sort_by)
    if sort_fields:
        out = out.sort_values(sort_fields, ascending=ascending, na_position="last", kind="mergesort")
    if limit is not None:
        out = out.head(max(int(limit), 0))
    return out.reset_index(drop=True)


def _rank_sort_fields(df: pd.DataFrame, sort_by: str | list[str] | None) -> list[str]:
    requested = [sort_by] if isinstance(sort_by, str) else sort_by
    fields = requested or DEFAULT_RANKABLE_SORT_FIELDS
    return [field for field in fields if field in df]


def _candidate_type_mask(df: pd.DataFrame, candidate_type: str | list[str]) -> pd.Series:
    types = [candidate_type] if isinstance(candidate_type, str) else candidate_type
    mask = pd.Series(False, index=df.index)
    for item in types:
        key = str(item).lower()
        if key in {"all", "*"}:
            return pd.Series(True, index=df.index)
        if key in {"one_shot", "oneshot", "new_terminal", "one_shot_attention"}:
            mask |= _truthy(df, "is_one_shot") | _equals_any(df, ["final_candidate_status", "risk_type_label"], "one_shot_attention")
        elif key in {"observation", "observation_only", "watchlist"}:
            mask |= _truthy(df, "is_observation") | _equals_any(df, ["final_candidate_status", "risk_type_label"], "observation_only")
        elif key in {"recurring", "backbone"}:
            mask |= ~(_truthy(df, "is_one_shot") | _truthy(df, "is_observation"))
        else:
            mask |= _equals_any(df, ["candidate_type", "final_candidate_status", "risk_type_label", "review_status"], key)
    return mask


def _truthy(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df:
        return pd.Series(False, index=df.index)
    return df[column].astype(str).str.lower().isin({"true", "1", "yes", "y"})


def _equals_any(df: pd.DataFrame, columns: list[str], value: str) -> pd.Series:
    mask = pd.Series(False, index=df.index)
    for column in columns:
        if column in df:
            mask |= df[column].astype(str).str.lower().eq(value)
    return mask


def long_path(path: Path) -> str:
    resolved = str(path.resolve())
    if os.name == "nt" and not resolved.startswith("\\\\?\\"):
        return "\\\\?\\" + resolved
    return resolved


def path_exists(path: Path) -> bool:
    return os.path.exists(long_path(path))
