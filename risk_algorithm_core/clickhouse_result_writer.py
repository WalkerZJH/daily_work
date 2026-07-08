"""Optional ClickHouse result write helpers with local fallback."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json

import pandas as pd

from .clickhouse_io import ClickHouseHttpClient


def write_dataframe_to_clickhouse_or_fallback(
    frame: pd.DataFrame,
    *,
    table_name: str,
    fallback_dir: str | Path,
    client: Any | None = None,
) -> dict[str, Any]:
    fallback = Path(fallback_dir)
    fallback.mkdir(parents=True, exist_ok=True)
    client = client or ClickHouseHttpClient()
    status: dict[str, Any] = {
        "clickhouse_table": table_name,
        "row_count": int(len(frame)),
        "write_status": "unknown",
        "fallback_path": "",
        "error": "",
    }
    try:
        client.write_dataframe(table_name, frame)
        status["write_status"] = "clickhouse"
    except Exception as exc:  # fallback is intentional for unknown write permissions.
        fallback_path = fallback / f"{table_name}.csv"
        frame.to_csv(fallback_path, index=False)
        status.update(
            {
                "write_status": "fallback_csv",
                "fallback_path": str(fallback_path),
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
    status_path = fallback / f"{table_name}_write_status.json"
    status_path.write_text(json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")
    return status
