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

    def get_risk_entity(self, risk_entity_id: str) -> dict[str, Any] | None:
        df = self.load_table("risk_entities")
        row = df[df["risk_entity_id"].astype(str).eq(str(risk_entity_id))]
        return None if row.empty else row.iloc[0].to_dict()

    def list_risk_cards(self, risk_entity_id: str) -> pd.DataFrame:
        return self.load_table("risk_cards").query("risk_entity_id == @risk_entity_id")

    def list_evidence(self, risk_card_id: str) -> pd.DataFrame:
        return self.load_table("risk_card_evidence").query("risk_card_id == @risk_card_id")

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

    def get_risk_entity(self, risk_entity_id: str) -> dict[str, Any] | None:
        rows = self.list_risk_entities(risk_entity_id=risk_entity_id)
        return None if rows.empty else rows.iloc[0].to_dict()

    def list_risk_cards(self, risk_entity_id: str) -> pd.DataFrame:
        return self.load_table("risk_cards").query("risk_entity_id == @risk_entity_id")

    def list_evidence(self, risk_card_id: str) -> pd.DataFrame:
        return self.load_table("risk_card_evidence").query("risk_card_id == @risk_card_id")

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

    def get_page_payload(self, page_name: str) -> dict[str, Any]:
        key = page_name[:-5] if page_name.endswith(".json") else page_name
        if key not in self.payloads:
            raise FileNotFoundError(key)
        return self.payloads[key]


class ClickHouseRiskResultRepository(RiskResultRepository):
    """Reserved repository stub for backend storage integration."""

    def __init__(self, *_: Any, **__: Any):
        pass

    def manifest(self) -> RiskResultManifest:
        raise NotImplementedError("ClickHouse repository is a storage stub.")

    def load_table(self, name: str) -> pd.DataFrame:
        raise NotImplementedError("ClickHouse repository is a storage stub.")

    def list_risk_entities(self, **filters: Any) -> pd.DataFrame:
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

    def get_page_payload(self, page_name: str) -> dict[str, Any]:
        raise NotImplementedError("ClickHouse repository is a storage stub.")


def apply_filters(df: pd.DataFrame, filters: dict[str, Any]) -> pd.DataFrame:
    out = df.copy()
    for key, value in filters.items():
        if value is None or key not in out:
            continue
        out = out[out[key].astype(str).eq(str(value))]
    return out


def long_path(path: Path) -> str:
    resolved = str(path.resolve())
    if os.name == "nt" and not resolved.startswith("\\\\?\\"):
        return "\\\\?\\" + resolved
    return resolved


def path_exists(path: Path) -> bool:
    return os.path.exists(long_path(path))
