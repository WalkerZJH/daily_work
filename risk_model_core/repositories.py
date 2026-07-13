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
    def manifest_context(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def list_available_report_contexts(self) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def resolve_report_context(
        self,
        requested_report_month: str | None = None,
        requested_run_date: str | None = None,
        requested_horizon: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def list_available_observation_contexts(self, batch_root: str | Path | None = None) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def resolve_observation_context(
        self,
        observation_date: str | None = None,
        requested_report_month: str | None = None,
        requested_detector_run_date: str | None = None,
        requested_horizon: str | None = None,
        batch_root: str | Path | None = None,
        manual_report_month: bool = False,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def open_probability_repository(self, context: dict[str, Any]) -> "ParquetRiskResultRepository":
        raise NotImplementedError

    @abstractmethod
    def open_detector_repository(self, context: dict[str, Any]) -> "ParquetRiskResultRepository":
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

    def manifest_context(self) -> dict[str, Any]:
        path = self.batch_dir / "report_context.json"
        if path_exists(path):
            with open(long_path(path), encoding="utf-8") as fh:
                return json.load(fh)
        return build_manifest_context(self.batch_dir, self._manifest.raw, self.list_daily_detector_runs())

    def list_available_report_contexts(self) -> pd.DataFrame:
        for path in available_context_candidates(self.batch_dir):
            if not path_exists(path):
                continue
            if path.suffix == ".json":
                data = json.loads(Path(path).read_text(encoding="utf-8"))
                rows = data.get("contexts", data if isinstance(data, list) else [data])
                return pd.DataFrame(rows)
            return pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
        return pd.DataFrame([available_context_row(self.manifest_context(), self.batch_dir)])

    def resolve_report_context(
        self,
        requested_report_month: str | None = None,
        requested_run_date: str | None = None,
        requested_horizon: str | None = None,
    ) -> dict[str, Any]:
        return resolve_report_context_from_rows(
            self.list_available_report_contexts(),
            requested_report_month=requested_report_month,
            requested_run_date=requested_run_date,
            requested_horizon=requested_horizon,
        )

    def list_available_observation_contexts(self, batch_root: str | Path | None = None) -> pd.DataFrame:
        root = Path(batch_root) if batch_root is not None else infer_batch_root(self.batch_dir)
        for path in [
            root / "available_observation_contexts.parquet",
            root / "available_observation_contexts.csv",
            root / "available_observation_contexts.json",
        ]:
            if not path_exists(path):
                continue
            if path.suffix == ".json":
                with open(long_path(path), encoding="utf-8") as fh:
                    data = json.load(fh)
                rows = data.get("contexts", data if isinstance(data, list) else [data])
                return pd.DataFrame(rows)
            return pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
        return pd.DataFrame()

    def resolve_observation_context(
        self,
        observation_date: str | None = None,
        requested_report_month: str | None = None,
        requested_detector_run_date: str | None = None,
        requested_horizon: str | None = None,
        batch_root: str | Path | None = None,
        manual_report_month: bool = False,
    ) -> dict[str, Any]:
        return resolve_observation_context_from_rows(
            self.list_available_observation_contexts(batch_root=batch_root),
            observation_date=observation_date,
            requested_report_month=requested_report_month,
            requested_detector_run_date=requested_detector_run_date,
            requested_horizon=requested_horizon,
            manual_report_month=manual_report_month,
        )

    def open_probability_repository(self, context: dict[str, Any]) -> "ParquetRiskResultRepository":
        if not context.get("probability_batch_available"):
            raise FileNotFoundError("Probability batch is unavailable for this observation context.")
        return ParquetRiskResultRepository(str(context["probability_batch_dir"]))

    def open_detector_repository(self, context: dict[str, Any]) -> "ParquetRiskResultRepository":
        if not context.get("detector_run_available"):
            raise FileNotFoundError("Detector run is unavailable for this observation context.")
        return ParquetRiskResultRepository(str(context["probability_batch_dir"]))

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

    def manifest_context(self) -> dict[str, Any]:
        return build_manifest_context(Path("."), self._manifest.raw, self.list_daily_detector_runs())

    def list_available_report_contexts(self) -> pd.DataFrame:
        return pd.DataFrame([available_context_row(self.manifest_context(), Path("."))])

    def resolve_report_context(
        self,
        requested_report_month: str | None = None,
        requested_run_date: str | None = None,
        requested_horizon: str | None = None,
    ) -> dict[str, Any]:
        return resolve_report_context_from_rows(
            self.list_available_report_contexts(),
            requested_report_month=requested_report_month,
            requested_run_date=requested_run_date,
            requested_horizon=requested_horizon,
        )

    def list_available_observation_contexts(self, batch_root: str | Path | None = None) -> pd.DataFrame:
        context = available_context_row(self.manifest_context(), Path("."))
        context["observation_date"] = context.get("run_date", "")
        context["probability_report_month"] = context.get("report_month", "")
        context["probability_batch_id"] = context.get("batch_id", "")
        context["probability_batch_dir"] = context.get("batch_dir", "")
        context["probability_batch_available"] = True
        context["detector_run_date"] = context.get("run_date", "")
        context["detector_run_id"] = ""
        context["detector_run_available"] = False
        context["context_status"] = "detector_run_unavailable"
        context["manual_selection_required"] = True
        context["available_report_months"] = context.get("report_month", "")
        context["available_detector_run_dates"] = ""
        return pd.DataFrame([context])

    def resolve_observation_context(
        self,
        observation_date: str | None = None,
        requested_report_month: str | None = None,
        requested_detector_run_date: str | None = None,
        requested_horizon: str | None = None,
        batch_root: str | Path | None = None,
        manual_report_month: bool = False,
    ) -> dict[str, Any]:
        return resolve_observation_context_from_rows(
            self.list_available_observation_contexts(batch_root=batch_root),
            observation_date=observation_date,
            requested_report_month=requested_report_month,
            requested_detector_run_date=requested_detector_run_date,
            requested_horizon=requested_horizon,
            manual_report_month=manual_report_month,
        )

    def open_probability_repository(self, context: dict[str, Any]) -> "ParquetRiskResultRepository":
        raise NotImplementedError("In-memory contexts cannot open parquet repositories.")

    def open_detector_repository(self, context: dict[str, Any]) -> "ParquetRiskResultRepository":
        raise NotImplementedError("In-memory contexts cannot open parquet repositories.")

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

    def manifest_context(self) -> dict[str, Any]:
        raise NotImplementedError("ClickHouse repository is a storage stub.")

    def list_available_report_contexts(self) -> pd.DataFrame:
        raise NotImplementedError("ClickHouse repository is a storage stub.")

    def resolve_report_context(
        self,
        requested_report_month: str | None = None,
        requested_run_date: str | None = None,
        requested_horizon: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError("ClickHouse repository is a storage stub.")

    def list_available_observation_contexts(self, batch_root: str | Path | None = None) -> pd.DataFrame:
        raise NotImplementedError("ClickHouse repository is a storage stub.")

    def resolve_observation_context(
        self,
        observation_date: str | None = None,
        requested_report_month: str | None = None,
        requested_detector_run_date: str | None = None,
        requested_horizon: str | None = None,
        batch_root: str | Path | None = None,
        manual_report_month: bool = False,
    ) -> dict[str, Any]:
        raise NotImplementedError("ClickHouse repository is a storage stub.")

    def open_probability_repository(self, context: dict[str, Any]) -> "ParquetRiskResultRepository":
        raise NotImplementedError("ClickHouse repository is a storage stub.")

    def open_detector_repository(self, context: dict[str, Any]) -> "ParquetRiskResultRepository":
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


def build_manifest_context(batch_dir: Path, manifest: dict[str, Any], detector_runs: pd.DataFrame | None = None) -> dict[str, Any]:
    detector_run_dates: list[str] = []
    if detector_runs is not None and not detector_runs.empty and "run_date" in detector_runs:
        detector_run_dates = sorted({str(value) for value in detector_runs["run_date"].dropna()})
    run_date = str(manifest.get("run_date") or manifest.get("report_date") or "")
    return {
        "batch_id": str(manifest.get("result_batch_id") or manifest.get("batch_id") or ""),
        "batch_dir": str(batch_dir),
        "report_type": str(manifest.get("report_type") or ""),
        "report_month": str(manifest.get("report_month") or ""),
        "report_date": str(manifest.get("report_date") or ""),
        "score_as_of_date": str(manifest.get("score_as_of_date") or manifest.get("cutoff_date") or ""),
        "run_date": run_date,
        "detector_run_dates": detector_run_dates,
        "available_horizons": [str(item) for item in manifest.get("available_horizons", [])],
        "primary_horizon": str(manifest.get("primary_horizon") or ""),
        "detector_config_version": str(manifest.get("detector_config_version") or ""),
        "fact_mode_ready": bool(manifest.get("fact_mode_ready", False)),
        "raw_orders_mode_ready": bool(manifest.get("raw_orders_mode_ready", False)),
        "conditional_fact_mode_ready": bool(manifest.get("conditional_fact_mode_ready", False)),
        "ready_for_frontend_date_resolution": True,
        "caveats": list(manifest.get("caveats") or []),
    }


def available_context_row(context: dict[str, Any], batch_dir: Path) -> dict[str, Any]:
    return {
        "batch_id": context.get("batch_id", ""),
        "batch_dir": str(context.get("batch_dir") or batch_dir),
        "report_month": context.get("report_month", ""),
        "report_date": context.get("report_date", ""),
        "score_as_of_date": context.get("score_as_of_date", ""),
        "run_date": context.get("run_date", ""),
        "detector_run_date": ";".join(str(item) for item in context.get("detector_run_dates", [])),
        "primary_horizon": context.get("primary_horizon", ""),
        "available_horizons": ";".join(str(item) for item in context.get("available_horizons", [])),
        "detector_config_version": context.get("detector_config_version", ""),
        "risk_entity_count": "",
        "daily_detector_clue_count": "",
        "source_type": "formal_result_batch",
        "ready_status": "conditional_fact_mode_ready" if context.get("conditional_fact_mode_ready") else "unknown",
        "caveat": "; ".join(str(item) for item in context.get("caveats", [])),
    }


def available_context_candidates(batch_dir: Path) -> list[Path]:
    roots = [batch_dir.parent.parent, batch_dir.parent, batch_dir]
    paths: list[Path] = []
    for root in roots:
        paths.extend(
            [
                root / "available_report_contexts.parquet",
                root / "available_report_contexts.csv",
                root / "available_report_contexts.json",
            ]
        )
    return paths


def infer_batch_root(batch_dir: Path) -> Path:
    if batch_dir.parent.name.startswith("report_month="):
        return batch_dir.parent.parent
    return batch_dir


def resolve_report_context_from_rows(
    contexts: pd.DataFrame,
    *,
    requested_report_month: str | None = None,
    requested_run_date: str | None = None,
    requested_horizon: str | None = None,
) -> dict[str, Any]:
    if contexts.empty:
        return {
            "ready": False,
            "requested_report_month": requested_report_month,
            "effective_report_month": None,
            "requested_run_date": requested_run_date,
            "effective_run_date": None,
            "requested_horizon": requested_horizon,
            "effective_horizon": None,
            "date_resolution_status": "no_available_batch",
            "batch_id": None,
            "batch_dir": None,
            "available_report_months": [],
            "available_run_dates": [],
            "available_horizons": [],
            "is_exact_match": False,
            "fallback_used": False,
            "warnings": ["No available result batch."],
            "caveats": [],
        }

    rows = contexts.copy()
    rows["_report_month"] = rows.get("report_month", "").astype(str)
    rows["_run_date"] = rows.get("run_date", "").astype(str)
    rows = rows.sort_values(["_report_month", "_run_date"], ascending=[False, False], kind="mergesort").reset_index(drop=True)
    available_report_months = sorted({str(value) for value in rows["_report_month"] if str(value)}, reverse=True)
    available_run_dates = sorted({str(value) for value in rows["_run_date"] if str(value)}, reverse=True)

    matches = rows
    if requested_report_month is not None:
        matches = matches[matches["_report_month"].eq(str(requested_report_month))]
    if requested_run_date is not None:
        matches = matches[matches["_run_date"].eq(str(requested_run_date))]

    exact = not matches.empty
    selected = matches.iloc[0] if exact else rows.iloc[0]
    available_horizons = split_context_values(selected.get("available_horizons", ""))
    primary_horizon = str(selected.get("primary_horizon") or (available_horizons[0] if available_horizons else ""))
    if requested_horizon is not None and str(requested_horizon) in available_horizons:
        effective_horizon = str(requested_horizon)
    else:
        effective_horizon = primary_horizon

    status = "exact_match" if exact else "fallback_to_latest_available"
    warnings: list[str] = []
    if requested_report_month is not None and str(requested_report_month) not in available_report_months:
        status = "fallback_to_latest_report_month" if requested_run_date is None else "fallback_to_latest_available"
        warnings.append("Requested report_month is unavailable; using latest available report_month.")
    if requested_run_date is not None and str(requested_run_date) not in available_run_dates:
        status = "fallback_to_latest_available"
        warnings.append("Requested run_date is unavailable; using latest available run_date.")
    if requested_horizon is not None and str(requested_horizon) not in available_horizons:
        warnings.append("Requested horizon is unavailable; using primary horizon.")

    return {
        "ready": True,
        "requested_report_month": requested_report_month,
        "effective_report_month": str(selected.get("report_month") or ""),
        "requested_run_date": requested_run_date,
        "effective_run_date": str(selected.get("run_date") or ""),
        "requested_horizon": requested_horizon,
        "effective_horizon": effective_horizon,
        "date_resolution_status": status,
        "batch_id": str(selected.get("batch_id") or ""),
        "batch_dir": str(selected.get("batch_dir") or ""),
        "available_report_months": available_report_months,
        "available_run_dates": available_run_dates,
        "available_horizons": available_horizons,
        "is_exact_match": exact,
        "fallback_used": not exact,
        "warnings": warnings,
        "caveats": split_context_values(selected.get("caveat", "")),
    }


def split_context_values(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    text = str(value)
    if not text:
        return []
    return [part.strip() for part in text.split(";") if part.strip()]


def resolve_observation_context_from_rows(
    contexts: pd.DataFrame,
    *,
    observation_date: str | None = None,
    requested_report_month: str | None = None,
    requested_detector_run_date: str | None = None,
    requested_horizon: str | None = None,
    manual_report_month: bool = False,
) -> dict[str, Any]:
    obs_date = str(observation_date or pd.Timestamp.today().date().isoformat())
    expected_probability_month = previous_complete_month(obs_date)
    probability_month = str(requested_report_month) if manual_report_month and requested_report_month else expected_probability_month
    detector_run_date = str(requested_detector_run_date or obs_date)
    requested_horizon = str(requested_horizon) if requested_horizon is not None else None
    if contexts.empty:
        return {
            "ready": False,
            "observation_date": obs_date,
            "requested_observation_date": observation_date,
            "effective_observation_date": obs_date,
            "expected_probability_report_month": expected_probability_month,
            "effective_probability_report_month": None,
            "probability_report_month": probability_month,
            "probability_batch_id": None,
            "probability_batch_dir": None,
            "probability_batch_available": False,
            "detector_run_date": detector_run_date,
            "detector_run_id": None,
            "detector_run_available": False,
            "context_status": "no_available_context",
            "manual_selection_required": True,
            "manual_report_month": manual_report_month,
            "available_report_months": [],
            "available_detector_run_dates": [],
            "requested_horizon": requested_horizon,
            "effective_horizon": None,
            "warnings": ["No available observation context registry."],
            "caveats": [],
        }

    rows = contexts.copy()
    for column in [
        "observation_date",
        "probability_report_month",
        "detector_run_date",
        "available_report_months",
        "available_detector_run_dates",
        "available_horizons",
        "caveat",
    ]:
        if column not in rows:
            rows[column] = ""
    available_report_months = sorted(
        {str(value) for value in rows["probability_report_month"].dropna() if str(value)},
        reverse=True,
    )
    available_detector_run_dates = sorted(
        {
            str(value)
            for value in rows["detector_run_date"].dropna()
            if str(value) and _boolish(rows.loc[rows["detector_run_date"].astype(str).eq(str(value)), "detector_run_available"].iloc[0])
        },
        reverse=True,
    )
    explicit = rows[rows["observation_date"].astype(str).eq(obs_date)]
    if not explicit.empty:
        selected = explicit.iloc[0]
    else:
        candidates = rows[rows["probability_report_month"].astype(str).eq(probability_month)]
        selected = candidates.iloc[0] if not candidates.empty else rows.iloc[0]

    probability_rows = rows[rows["probability_report_month"].astype(str).eq(probability_month)]
    probability_available = bool(not probability_rows.empty and _boolish(probability_rows.iloc[0].get("probability_batch_available", False)))
    detector_rows = rows[
        rows["detector_run_date"].astype(str).eq(detector_run_date)
        & rows["probability_report_month"].astype(str).eq(probability_month)
    ]
    detector_available = bool(not detector_rows.empty and _boolish(detector_rows.iloc[0].get("detector_run_available", False)))
    if probability_available and detector_available:
        status = "ready"
        manual = False
    elif probability_available:
        status = "detector_run_unavailable"
        manual = True
    else:
        status = "EXPECTED_MONTH_BATCH_UNAVAILABLE"
        manual = True

    source = detector_rows.iloc[0] if not detector_rows.empty else (probability_rows.iloc[0] if not probability_rows.empty else selected)
    effective_probability_month = str(source.get("probability_report_month") or "") if probability_available else None
    horizons = split_context_values(source.get("available_horizons", ""))
    primary_horizon = str(source.get("primary_horizon") or (horizons[0] if horizons else ""))
    effective_horizon = requested_horizon if requested_horizon in horizons else primary_horizon
    warnings: list[str] = []
    if not probability_available:
        warnings.append(
            f"Observation date {obs_date} expects probability report month {probability_month}, "
            "but that formal monthly batch is unavailable; do not fallback to an older month silently."
        )
    if probability_available and not detector_available:
        warnings.append("Detector run date is unavailable; do not substitute another run date silently.")
    if requested_horizon is not None and requested_horizon not in horizons:
        warnings.append("Requested horizon is unavailable; using primary horizon.")

    return {
        "ready": status == "ready",
        "observation_date": obs_date,
        "requested_observation_date": observation_date,
        "effective_observation_date": obs_date,
        "expected_probability_report_month": expected_probability_month,
        "effective_probability_report_month": effective_probability_month,
        "probability_report_month": probability_month,
        "probability_batch_id": str(source.get("probability_batch_id") or "") if probability_available else None,
        "probability_batch_dir": str(source.get("probability_batch_dir") or "") if probability_available else None,
        "probability_batch_available": probability_available,
        "detector_run_date": detector_run_date,
        "detector_run_id": str(source.get("detector_run_id") or ""),
        "detector_run_available": detector_available,
        "context_status": status,
        "manual_selection_required": manual,
        "manual_report_month": manual_report_month,
        "available_report_months": available_report_months,
        "available_detector_run_dates": available_detector_run_dates,
        "requested_horizon": requested_horizon,
        "effective_horizon": effective_horizon,
        "warnings": warnings,
        "caveats": split_context_values(source.get("caveat", "")),
    }


def previous_complete_month(date_text: str) -> str:
    current = pd.Timestamp(date_text).date().replace(day=1)
    previous = current - pd.Timedelta(days=1)
    return previous.strftime("%Y-%m")


def _boolish(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


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
