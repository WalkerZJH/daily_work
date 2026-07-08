"""Raw input batch readers for monthly risk algorithm runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json

import pandas as pd

from .clickhouse_io import ClickHouseHttpClient
from .schema_mapping import SchemaMapping, apply_schema_mapping, ensure_columns, load_schema_mapping


ORDER_REQUIRED_COLUMNS = ["order_date", "manufacturer_code", "hospital_code", "drug_code", "order_quantity", "order_amount"]
OPTIONAL_TABLES = [
    "drug_master",
    "hospital_master",
    "manufacturer_master",
    "distributor_master",
    "org_scope",
    "product_line_mapping",
    "price_reference",
    "delivery_events",
    "fact_entity_month",
    "entity_purchase_sequence",
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
    """Read raw/source business tables from ClickHouse for algorithm-core runs."""

    def __init__(self, connection_url: str | None = None, client: Any | None = None):
        self.connection_url = connection_url
        self.client = client or ClickHouseHttpClient()

    def read(self, manifest: RawInputManifest, table_name: str) -> pd.DataFrame:
        query = _clickhouse_query_for_table(manifest, table_name)
        if not query:
            return pd.DataFrame()
        return self.client.query_df(query)


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
    reader: RawTableReader
    if manifest.source_system.lower() == "clickhouse" or manifest.table_format.lower() == "clickhouse":
        reader = ClickHouseRawTableReader()
    else:
        reader = LocalRawTableReader(raw_batch_dir)
    tables: dict[str, pd.DataFrame] = {}
    for table_name in ["orders", *OPTIONAL_TABLES]:
        df = reader.read(manifest, table_name)
        df = apply_schema_mapping(df, table_name, mapping)
        tables[table_name] = df
    validate_raw_tables(tables)
    return RawInputBatch(manifest=manifest, tables=tables)


def _clickhouse_query_for_table(manifest: RawInputManifest, table_name: str) -> str:
    queries = manifest.raw.get("table_queries", {})
    template = queries.get(table_name)
    table = manifest.table_paths.get(table_name)
    if not template:
        if not table:
            return ""
        template = "SELECT * FROM {table} {limit_clause}"
    row_limit = manifest.raw.get("row_limit")
    limit_clause = f"LIMIT {int(row_limit)}" if row_limit not in {None, "", 0, "0"} else ""
    values = {
        "table": str(table),
        "database": str(manifest.raw.get("database") or ""),
        "from_date": str(manifest.raw.get("from_date") or "1971-01-01"),
        "to_date": str(manifest.raw.get("to_date") or manifest.data_as_of_date or "2100-01-01"),
        "limit_clause": limit_clause,
    }
    return template.format(**values)


def validate_raw_tables(tables: dict[str, pd.DataFrame]) -> None:
    orders = tables.get("orders", pd.DataFrame())
    if orders.empty:
        raise ValueError("orders table is required and cannot be empty.")
    ensure_columns(orders, ORDER_REQUIRED_COLUMNS, "orders")
    report = build_raw_input_validation_report(tables)
    bad = report[report["status"].eq("fail")]
    if not bad.empty:
        raise ValueError("raw input validation failed: " + "; ".join(bad["message"].astype(str).head(5)))


def build_raw_input_validation_report(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    orders = tables.get("orders", pd.DataFrame())
    rows: list[dict[str, Any]] = []
    rows.append({"check_name": "orders_non_empty", "status": "pass" if not orders.empty else "fail", "invalid_count": 0 if not orders.empty else 1, "message": "" if not orders.empty else "orders table is empty"})
    missing = [col for col in ORDER_REQUIRED_COLUMNS if col not in orders.columns]
    rows.append({"check_name": "orders_required_columns", "status": "pass" if not missing else "fail", "invalid_count": len(missing), "message": ",".join(missing)})
    if orders.empty or missing:
        return pd.DataFrame(rows)
    order_date = pd.to_datetime(orders["order_date"], errors="coerce")
    rows.append({"check_name": "order_date_parse", "status": "pass" if not order_date.isna().any() else "fail", "invalid_count": int(order_date.isna().sum()), "message": "invalid order_date rows"})
    for col in ["manufacturer_code", "hospital_code", "drug_code"]:
        blank = orders[col].isna() | orders[col].astype(str).str.strip().eq("")
        rows.append({"check_name": f"{col}_not_blank", "status": "pass" if not blank.any() else "fail", "invalid_count": int(blank.sum()), "message": f"blank {col}"})
    for col in ["order_quantity", "order_amount"]:
        numeric = pd.to_numeric(orders[col], errors="coerce")
        invalid = numeric.isna()
        if col == "order_quantity":
            invalid = invalid | (numeric <= 0)
        rows.append({"check_name": f"{col}_numeric", "status": "pass" if not invalid.any() else "warn", "invalid_count": int(invalid.sum()), "message": f"invalid {col}"})
    return pd.DataFrame(rows)
