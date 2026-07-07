"""Raw input batch readers for monthly risk algorithm runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json

import pandas as pd

from .schema_mapping import SchemaMapping, apply_schema_mapping, ensure_columns, load_schema_mapping


ORDER_REQUIRED_COLUMNS = ["order_date", "manufacturer_code", "hospital_code", "drug_code"]
OPTIONAL_TABLES = [
    "drug_master",
    "hospital_master",
    "manufacturer_master",
    "distributor_master",
    "org_scope",
    "product_line_mapping",
    "price_reference",
    "delivery_events",
]


@dataclass(frozen=True, slots=True)
class RawInputManifest:
    raw_batch_id: str
    source_system: str
    data_as_of_date: str
    table_format: str
    table_paths: dict[str, str]
    raw: dict[str, Any]


@dataclass(slots=True)
class RawInputBatch:
    manifest: RawInputManifest
    tables: dict[str, pd.DataFrame]


class RawTableReader:
    def read(self, manifest: RawInputManifest, table_name: str) -> pd.DataFrame:
        raise NotImplementedError


class LocalRawTableReader(RawTableReader):
    def __init__(self, batch_dir: str | Path):
        self.batch_dir = Path(batch_dir)

    def read(self, manifest: RawInputManifest, table_name: str) -> pd.DataFrame:
        raw_path = manifest.table_paths.get(table_name) or f"{table_name}.{manifest.table_format}"
        path = self.batch_dir / raw_path
        if not path.exists():
            return pd.DataFrame()
        if path.suffix.lower() == ".parquet":
            return pd.read_parquet(path)
        if path.suffix.lower() == ".csv":
            return pd.read_csv(path)
        raise ValueError(f"Unsupported raw table format: {path}")


class SqlRawTableReader(RawTableReader):
    """Read-only SQL interface placeholder for future raw table extraction."""

    def __init__(self, connection_url: str | None = None):
        self.connection_url = connection_url

    def read(self, manifest: RawInputManifest, table_name: str) -> pd.DataFrame:
        raise NotImplementedError("SQL raw reader interface is reserved; use local raw batch in this stage.")


class ClickHouseRawTableReader(RawTableReader):
    """Read-only ClickHouse interface placeholder for future raw table extraction."""

    def __init__(self, connection_url: str | None = None):
        self.connection_url = connection_url

    def read(self, manifest: RawInputManifest, table_name: str) -> pd.DataFrame:
        raise NotImplementedError("ClickHouse raw reader interface is reserved; use local raw batch in this stage.")


def load_raw_manifest(raw_batch_dir: str | Path) -> RawInputManifest:
    data = json.loads((Path(raw_batch_dir) / "manifest.json").read_text(encoding="utf-8"))
    table_paths = {str(k): str(v) for k, v in data.get("table_paths", {}).items()}
    table_format = str(data.get("table_format") or "csv")
    return RawInputManifest(
        raw_batch_id=str(data.get("raw_batch_id") or Path(raw_batch_dir).name),
        source_system=str(data.get("source_system") or "local_batch"),
        data_as_of_date=str(data.get("data_as_of_date") or ""),
        table_format=table_format,
        table_paths=table_paths,
        raw=data,
    )


def read_raw_input_batch(raw_batch_dir: str | Path, schema_mapping_path: str | Path | None = None) -> RawInputBatch:
    manifest = load_raw_manifest(raw_batch_dir)
    mapping = load_schema_mapping(schema_mapping_path)
    reader = LocalRawTableReader(raw_batch_dir)
    tables: dict[str, pd.DataFrame] = {}
    for table_name in ["orders", *OPTIONAL_TABLES]:
        df = reader.read(manifest, table_name)
        df = apply_schema_mapping(df, table_name, mapping)
        tables[table_name] = df
    validate_raw_tables(tables)
    return RawInputBatch(manifest=manifest, tables=tables)


def validate_raw_tables(tables: dict[str, pd.DataFrame]) -> None:
    orders = tables.get("orders", pd.DataFrame())
    if orders.empty:
        raise ValueError("orders table is required and cannot be empty.")
    ensure_columns(orders, ORDER_REQUIRED_COLUMNS, "orders")
