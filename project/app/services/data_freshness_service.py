from __future__ import annotations

import os
from datetime import date, timedelta

from dotenv import load_dotenv
from sqlalchemy import Column, DateTime, MetaData, String, Table, create_engine, func, select
from sqlalchemy.exc import SQLAlchemyError

from app.adapters.sql_table_adapter import DEFAULT_ORDER_TABLE_NAME
from app.core.config import PROJECT_ROOT
from app.core.errors import DatasetLoadError
from app.schemas.api import DatabaseFreshnessRequest, DatabaseFreshnessResponse


class DataFreshnessService:
    def check(self, request: DatabaseFreshnessRequest) -> DatabaseFreshnessResponse:
        load_dotenv(PROJECT_ROOT / ".env", override=False)
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise DatasetLoadError("DATABASE_URL is not configured for database source.")
        date_to = request.date_to or request.as_of_date or date.today()
        date_from = request.date_from or (date_to - timedelta(days=request.days))
        try:
            engine = create_engine(database_url)
        except (ImportError, ModuleNotFoundError) as exc:
            raise DatasetLoadError(
                "Database driver is not installed for the configured DATABASE_URL."
            ) from exc
        except SQLAlchemyError as exc:
            raise DatasetLoadError("Failed to create database engine from DATABASE_URL.") from exc

        table_name = os.getenv("ORDER_TABLE_NAME") or DEFAULT_ORDER_TABLE_NAME
        metadata = MetaData()
        table = Table(
            table_name,
            metadata,
            Column("采购时间", DateTime),
            Column("企业编码", String),
            Column("省", String),
            Column("省编码", String),
        )
        query = select(func.max(table.c["采购时间"]), func.count()).where(
            table.c["采购时间"] >= date_from,
            table.c["采购时间"] <= date_to,
        )
        if request.enterprise_code:
            query = query.where(table.c["企业编码"] == request.enterprise_code)
        if request.province:
            query = query.where(table.c["省"] == request.province)
        if request.province_code:
            query = query.where(table.c["省编码"] == request.province_code)
        try:
            with engine.connect() as conn:
                max_order_time, row_count = conn.execute(query).one()
        except SQLAlchemyError as exc:
            raise DatasetLoadError(
                f"Unable to read freshness from source table {table_name}; query is read-only."
            ) from exc
        warning_summary = {}
        if int(row_count or 0) == 0:
            warning_summary["DATABASE_FRESHNESS_QUERY_RETURNED_EMPTY"] = 1
        return DatabaseFreshnessResponse(
            max_order_time=max_order_time.isoformat() if max_order_time is not None else None,
            row_count=int(row_count or 0),
            date_from=date_from,
            date_to=date_to,
            warning_summary=warning_summary,
        )
