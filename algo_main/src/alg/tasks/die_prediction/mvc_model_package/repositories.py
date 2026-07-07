"""Repository interfaces for MVC risk result batches."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
import json

import pandas as pd


class RiskResultRepository(ABC):
    @abstractmethod
    def load_table(self, name: str) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def save_table(self, name: str, table: pd.DataFrame) -> None:
        raise NotImplementedError

    @abstractmethod
    def save_json(self, relative_path: str, payload: dict[str, Any]) -> None:
        raise NotImplementedError


class ParquetRiskResultRepository(RiskResultRepository):
    def __init__(self, batch_dir: str | Path):
        self.batch_dir = Path(batch_dir)
        self.batch_dir.mkdir(parents=True, exist_ok=True)

    def load_table(self, name: str) -> pd.DataFrame:
        return pd.read_parquet(self.batch_dir / f"{name}.parquet")

    def save_table(self, name: str, table: pd.DataFrame) -> None:
        table.to_parquet(self.batch_dir / f"{name}.parquet", index=False)

    def save_json(self, relative_path: str, payload: dict[str, Any]) -> None:
        path = self.batch_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class ClickHouseRiskResultRepository(RiskResultRepository):
    """Reserved repository stub. Implement after backend storage is selected."""

    def __init__(self, *_: Any, **__: Any):
        pass

    def load_table(self, name: str) -> pd.DataFrame:
        raise NotImplementedError("ClickHouse repository is reserved for a later backend integration stage.")

    def save_table(self, name: str, table: pd.DataFrame) -> None:
        raise NotImplementedError("ClickHouse repository is reserved for a later backend integration stage.")

    def save_json(self, relative_path: str, payload: dict[str, Any]) -> None:
        raise NotImplementedError("ClickHouse repository is reserved for a later backend integration stage.")
