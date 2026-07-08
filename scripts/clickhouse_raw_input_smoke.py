"""Probe ClickHouse raw input mapping and optional write permission."""

from __future__ import annotations

from pathlib import Path
import datetime as dt
import json
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from risk_algorithm_core.clickhouse_io import ClickHouseHttpClient
from risk_algorithm_core.clickhouse_result_writer import write_dataframe_to_clickhouse_or_fallback
from risk_algorithm_core.raw_input import build_raw_input_validation_report, read_raw_input_batch

RAW_BATCH_DIR = ROOT / "configs" / "risk_algorithm_core" / "clickhouse_raw_input_batch"
SCHEMA_MAPPING = ROOT / "configs" / "risk_algorithm_core" / "schema_mapping.clickhouse_drug_purchase_orders.yaml"
REPORT_DIR = ROOT / "algo_main" / "reports" / "entity_complete_v2_coverage_expansion" / "24_clickhouse_raw_input_integration"
DATA_DIR = ROOT / "algo_main" / "data" / "entity_complete_v2_coverage_expansion" / "15_clickhouse_raw_input_integration"


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    client = ClickHouseHttpClient(timeout=120)
    manifest = json.loads((RAW_BATCH_DIR / "manifest.json").read_text(encoding="utf-8"))
    source_table = str(manifest["source_table"])

    describe = client.query_df(f"DESCRIBE TABLE {source_table}")
    describe.to_csv(REPORT_DIR / "clickhouse_source_schema_inventory.csv", index=False)
    _write_schema_md(describe, source_table)

    batch = read_raw_input_batch(RAW_BATCH_DIR, SCHEMA_MAPPING)
    validation = build_raw_input_validation_report(batch.tables)
    validation.to_csv(REPORT_DIR / "clickhouse_raw_input_validation_report.csv", index=False)
    summary = _raw_summary(batch.tables)
    (REPORT_DIR / "clickhouse_raw_input_read_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    for table_name in ["orders", "drug_master", "hospital_master", "manufacturer_master"]:
        frame = batch.tables.get(table_name, pd.DataFrame())
        frame.head(200).to_csv(DATA_DIR / f"{table_name}_sample.csv", index=False)

    probe = pd.DataFrame(
        [
            {
                "probe_id": f"probe_{dt.datetime.now(dt.UTC).strftime('%Y%m%d%H%M%S')}",
                "probe_status": "write_probe",
                "created_at": dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M:%S"),
            }
        ]
    )
    probe_table = "risk_algorithm_core_write_probe"
    try:
        client.query_text(
            "CREATE TABLE IF NOT EXISTS risk_algorithm_core_write_probe "
            "(probe_id String, probe_status String, created_at DateTime) "
            "ENGINE = MergeTree ORDER BY probe_id"
        )
    except Exception:
        pass
    write_status = write_dataframe_to_clickhouse_or_fallback(
        probe,
        table_name=probe_table,
        fallback_dir=DATA_DIR / "clickhouse_write_fallback",
        client=client,
    )
    (REPORT_DIR / "clickhouse_write_probe_status.md").write_text(_write_status_md(write_status), encoding="utf-8")
    _write_field_mapping_report()
    print(json.dumps({"summary": summary, "write_status": write_status}, ensure_ascii=False, indent=2))
    return 0


def _raw_summary(tables: dict[str, pd.DataFrame]) -> dict[str, object]:
    orders = tables["orders"]
    return {
        "orders_rows": int(len(orders)),
        "order_date_min": str(pd.to_datetime(orders["order_date"], errors="coerce").min()),
        "order_date_max": str(pd.to_datetime(orders["order_date"], errors="coerce").max()),
        "manufacturer_count": int(orders["manufacturer_code"].nunique()),
        "hospital_count": int(orders["hospital_code"].nunique()),
        "drug_count": int(orders["drug_code"].nunique()),
        "drug_master_rows": int(len(tables.get("drug_master", pd.DataFrame()))),
        "hospital_master_rows": int(len(tables.get("hospital_master", pd.DataFrame()))),
        "manufacturer_master_rows": int(len(tables.get("manufacturer_master", pd.DataFrame()))),
    }


def _write_schema_md(describe: pd.DataFrame, source_table: str) -> None:
    columns = "\n".join(f"- `{row['name']}`: `{row['type']}` - {row.get('comment', '')}" for _, row in describe.iterrows())
    (REPORT_DIR / "clickhouse_source_schema_inventory.md").write_text(
        "\n".join(
            [
                "# ClickHouse Source Schema Inventory",
                "",
                f"- source_table: `{source_table}`",
                f"- column_count: {len(describe)}",
                "",
                "## Columns",
                columns,
            ]
        ),
        encoding="utf-8",
    )


def _write_field_mapping_report() -> None:
    rows = [
        ("order_id", "order_detail_id", "high", "line-level order detail id"),
        ("order_date", "purchase_time", "high", "primary purchase timestamp; filters sentinel 1900"),
        ("manufacturer_code", "manufacturer_code", "high", "same semantic code"),
        ("manufacturer_display_name", "manufacturer_name", "high", "display dimension"),
        ("hospital_code", "hospital_code", "high", "same semantic code"),
        ("hospital_name", "hospital_name", "high", "display dimension"),
        ("drug_code", "drug_code", "high", "same semantic code"),
        ("drug_name", "generic_name", "medium", "uses generic name; brand_name is optional display context"),
        ("order_quantity", "purchase_quantity", "high", "purchase-side quantity"),
        ("order_amount", "purchase_amount", "high", "purchase-side amount"),
        ("distributor_code", "delivery_enterprise_code", "high", "delivery enterprise code"),
        ("delivery_date", "delivery_time", "low", "many 1970 sentinel values; detector remains disabled"),
        ("arrival_date", "received_time", "low", "many 1970 sentinel values; detector remains disabled"),
        ("region_code", "province_code", "high", "business region uses province-level code"),
        ("region_name", "province", "high", "business region uses province-level name"),
        ("product_line_name", "drug_category", "low", "display fallback only; not portfolio mapping"),
    ]
    frame = pd.DataFrame(rows, columns=["standard_field", "clickhouse_field", "confidence", "note"])
    frame.to_csv(REPORT_DIR / "clickhouse_field_mapping_review.csv", index=False)
    lines = ["| standard_field | clickhouse_field | confidence | note |", "|---|---|---|---|"]
    for _, row in frame.iterrows():
        lines.append(f"| {row['standard_field']} | {row['clickhouse_field']} | {row['confidence']} | {row['note']} |")
    (REPORT_DIR / "clickhouse_field_mapping_review.md").write_text("\n".join(lines), encoding="utf-8")


def _write_status_md(status: dict[str, object]) -> str:
    return "\n".join(
        [
            "# ClickHouse Write Probe Status",
            "",
            f"- write_status: `{status.get('write_status')}`",
            f"- clickhouse_table: `{status.get('clickhouse_table')}`",
            f"- row_count: `{status.get('row_count')}`",
            f"- fallback_path: `{status.get('fallback_path')}`",
            f"- error: `{status.get('error')}`",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
