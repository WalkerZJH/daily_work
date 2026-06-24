from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import Column, MetaData, String, Table, create_engine, inspect, select
from sqlalchemy.exc import SQLAlchemyError

from app.adapters.base import BaseSourceAdapter
from app.adapters.canonicalize import (
    RAW_ORDER_COLUMN_MAP,
    canonicalize_order_dataframe,
    derive_drugs_from_orders,
    derive_orgs_from_orders,
    derive_product_line_mapping_from_orders,
)
from app.core.config import PROJECT_ROOT
from app.core.errors import DatasetLoadError

DEFAULT_ORDER_TABLE_NAME = "BS_Agent_DingDan"
REQUIRED_RAW_COLUMNS = [
    "采购时间",
    "药品编码",
    "医疗机构编码",
    "采购数量",
    "采购价(元)",
]


@dataclass(frozen=True)
class QuerySpec:
    table_name: str
    selected_columns: list[str]
    filters: dict[str, Any]
    row_limit: int | None


class SQLTableSourceAdapter(BaseSourceAdapter):
    def __init__(
        self,
        *,
        dataset_name: str | None = None,
        as_of_date: date | None = None,
        enterprise_code: str | None = None,
        province: str | None = None,
        province_code: str | None = None,
        row_limit: int | None = None,
        table_name: str | None = None,
    ) -> None:
        load_dotenv(PROJECT_ROOT / ".env", override=False)
        self._dataset_name = dataset_name or f"database:{table_name or self._table_name_from_env()}"
        self._table_name = table_name or self._table_name_from_env()
        self._as_of_date = as_of_date
        self._enterprise_code = enterprise_code
        self._province = province
        self._province_code = province_code
        self._row_limit = row_limit
        self._orders: pd.DataFrame | None = None

    @property
    def dataset_name(self) -> str:
        return self._dataset_name

    @staticmethod
    def _table_name_from_env() -> str:
        return os.getenv("ORDER_TABLE_NAME") or DEFAULT_ORDER_TABLE_NAME

    @staticmethod
    def projection_columns(available_columns: set[str] | None = None) -> list[str]:
        columns = list(RAW_ORDER_COLUMN_MAP.keys())
        if available_columns is not None:
            columns = [column for column in columns if column in available_columns]
        return columns

    def build_query_spec(self, available_columns: set[str] | None = None) -> QuerySpec:
        selected_columns = self.projection_columns(available_columns)
        filters: dict[str, Any] = {}
        if self._as_of_date is not None:
            filters["采购时间"] = self._as_of_date
        if self._enterprise_code:
            filters["企业编码"] = self._enterprise_code
        if self._province:
            filters["省"] = self._province
        if self._province_code:
            filters["省编码"] = self._province_code
        return QuerySpec(
            table_name=self._table_name,
            selected_columns=selected_columns,
            filters=filters,
            row_limit=self._row_limit,
        )

    def load_orders(self) -> pd.DataFrame:
        if self._orders is not None:
            return self._orders.copy()

        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise DatasetLoadError("DATABASE_URL is not configured for database source.")

        try:
            engine = create_engine(database_url)
        except (ImportError, ModuleNotFoundError) as exc:
            raise DatasetLoadError(
                "Database driver is not installed for the configured DATABASE_URL. "
                "Install the matching optional dependency, for example project[mssql] for SQL Server."
            ) from exc
        except SQLAlchemyError as exc:
            raise DatasetLoadError("Failed to create database engine from DATABASE_URL.") from exc

        try:
            inspector = inspect(engine)
            available_columns = {column["name"] for column in inspector.get_columns(self._table_name)}
        except (ImportError, ModuleNotFoundError) as exc:
            raise DatasetLoadError(
                "Database driver is not installed for the configured DATABASE_URL. "
                "Install the matching optional dependency, for example project[mssql] for SQL Server."
            ) from exc
        except SQLAlchemyError as exc:
            raise DatasetLoadError(
                f"Unable to inspect source table {self._table_name}; check DATABASE_URL and table access."
            ) from exc

        missing_required = [column for column in REQUIRED_RAW_COLUMNS if column not in available_columns]
        if missing_required:
            raise DatasetLoadError(
                "Source table is missing required columns: " + ", ".join(missing_required)
            )

        spec = self.build_query_spec(available_columns)
        if not spec.selected_columns:
            raise DatasetLoadError("No mapped columns are available in source table.")

        metadata = MetaData()
        table = Table(
            self._table_name,
            metadata,
            *(Column(column, String) for column in spec.selected_columns),
        )
        query = select(*(table.c[column] for column in spec.selected_columns))
        if self._as_of_date is not None and "采购时间" in table.c:
            query = query.where(table.c["采购时间"] <= self._as_of_date)
        if self._enterprise_code and "企业编码" in table.c:
            query = query.where(table.c["企业编码"] == self._enterprise_code)
        if self._province and "省" in table.c:
            query = query.where(table.c["省"] == self._province)
        if self._province_code and "省编码" in table.c:
            query = query.where(table.c["省编码"] == self._province_code)
        if self._row_limit:
            query = query.limit(self._row_limit)

        try:
            raw = pd.read_sql(query, engine)
        except SQLAlchemyError as exc:
            raise DatasetLoadError(
                f"Unable to read source table {self._table_name}; query is read-only and projected."
            ) from exc

        self._orders = canonicalize_order_dataframe(raw)
        return self._orders.copy()

    def load_drugs(self) -> pd.DataFrame:
        return derive_drugs_from_orders(self.load_orders())

    def load_orgs(self) -> pd.DataFrame:
        return derive_orgs_from_orders(self.load_orders())

    def load_product_line_mapping(self) -> pd.DataFrame:
        return derive_product_line_mapping_from_orders(self.load_orders())
