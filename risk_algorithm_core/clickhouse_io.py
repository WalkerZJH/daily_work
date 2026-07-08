"""Small ClickHouse HTTP helpers for algorithm-core raw/result integration."""

from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json
import os

import pandas as pd


def load_dotenv(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


@dataclass(frozen=True, slots=True)
class ClickHouseConnection:
    host: str
    port: int
    database: str
    user: str
    password: str
    protocol: str = "http"

    @classmethod
    def from_env(cls, env_path: str | Path = ".env") -> "ClickHouseConnection":
        load_dotenv(env_path)
        return cls(
            host=os.environ["CLICKHOUSE_HOST"],
            port=int(os.environ.get("CLICKHOUSE_PORT", "8123")),
            database=os.environ["CLICKHOUSE_DATABASE"],
            user=os.environ["CLICKHOUSE_USER"],
            password=os.environ["CLICKHOUSE_PASSWORD"],
            protocol=os.environ.get("CLICKHOUSE_PROTOCOL", "http"),
        )


class ClickHouseHttpClient:
    def __init__(self, connection: ClickHouseConnection | None = None, *, timeout: int = 120):
        self.connection = connection or ClickHouseConnection.from_env()
        self.timeout = timeout

    def query_text(self, sql: str) -> str:
        request = Request(self._url(), data=sql.encode("utf-8"), method="POST")
        with urlopen(request, timeout=self.timeout) as response:
            return response.read().decode("utf-8")

    def query_df(self, sql: str) -> pd.DataFrame:
        query = sql if " FORMAT " in sql.upper() else f"{sql} FORMAT JSONEachRow"
        text = self.query_text(query)
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
        return pd.DataFrame(rows)

    def write_dataframe(self, table_name: str, frame: pd.DataFrame) -> None:
        if frame.empty:
            return
        payload = "\n".join(json.dumps(_json_record(row), ensure_ascii=False) for row in frame.to_dict(orient="records"))
        self.query_text(f"INSERT INTO {table_name} FORMAT JSONEachRow\n{payload}")

    def _url(self) -> str:
        conn = self.connection
        return f"{conn.protocol}://{conn.host}:{conn.port}/?" + urlencode(
            {"database": conn.database, "user": conn.user, "password": conn.password}
        )


def dataframe_from_csv_text(text: str) -> pd.DataFrame:
    return pd.read_csv(StringIO(text))


def _json_record(row: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in row.items():
        if value is None:
            clean[key] = None
            continue
        try:
            if pd.isna(value):
                clean[key] = None
                continue
        except (TypeError, ValueError):
            pass
        clean[key] = value
    return clean
