"""Export the existing cleaned order chain into the strict Daily Detector contract."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid

import pandas as pd

from risk_algorithm_core.detector_input import (
    CLEANED_DETECTOR_INPUT_STAGE,
    classify_detector_order_eligibility,
    validate_cleaned_detector_orders,
)
from risk_result_contracts import write_production_parquet


DEFAULT_CLEANED_ORDERS = Path(
    "algo_main/data/entity_complete_v2_coverage_expansion/03_cleaned/bs_agent_dingdan_clean.parquet"
)
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export cleaned, fact-only Daily Detector input.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--input-batch-id", required=True)
    parser.add_argument("--cleaned-orders", default=str(DEFAULT_CLEANED_ORDERS))
    args = parser.parse_args(argv)
    result = export_cleaned_detector_input(
        cleaned_orders_path=args.cleaned_orders,
        output_dir=args.output_dir,
        input_batch_id=args.input_batch_id,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


def export_cleaned_detector_input(
    *,
    cleaned_orders_path: str | Path,
    output_dir: str | Path,
    input_batch_id: str,
) -> dict[str, object]:
    """Publish an immutable batch from one self-contained cleaned Parquet."""
    target = Path(output_dir)
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite cleaned Detector input batch: {target}")
    clean_path = Path(cleaned_orders_path)
    if not clean_path.exists():
        raise FileNotFoundError(clean_path)

    clean = pd.read_parquet(clean_path)
    if clean["row_uid"].isna().any() or clean["row_uid"].astype(str).duplicated().any():
        raise ValueError("Cleaned orders row_uid must be non-null and unique")
    required_clean = {
        "row_uid", "order_detail_id", "purchase_time", "manufacturer_code", "hospital_code",
        "drug_code", "purchase_unit", "raw_sensitive_purchase_price",
        "raw_sensitive_purchase_quantity", "raw_sensitive_purchase_amount", "order_status_raw",
        "order_status_norm", "order_phase_code", "order_terminal_flag", "order_failure_flag",
        "needs_manual_review",
    }
    missing_clean = required_clean.difference(clean.columns)
    if missing_clean:
        raise ValueError(
            "Cleaned source is incomplete; rebuild the cleaning Parquet before Detector export. "
            f"Missing: {sorted(missing_clean)}"
        )
    clean = clean.copy()
    clean["row_uid"] = clean["row_uid"].astype(str)

    orders = pd.DataFrame(
        {
            "row_uid": clean["row_uid"],
            "order_id": clean["order_detail_id"].astype("string"),
            "order_date": pd.to_datetime(clean["purchase_time"], errors="coerce"),
            "manufacturer_code": clean["manufacturer_code"].astype("string"),
            "hospital_code": clean["hospital_code"].astype("string"),
            "drug_code": clean["drug_code"].astype("string"),
            "order_quantity": pd.to_numeric(clean["raw_sensitive_purchase_quantity"], errors="coerce"),
            "order_amount": pd.to_numeric(clean["raw_sensitive_purchase_amount"], errors="coerce"),
            "purchase_unit": clean["purchase_unit"].astype("string"),
            "purchase_unit_price": pd.to_numeric(clean["raw_sensitive_purchase_price"], errors="coerce"),
            "order_status_raw": clean["order_status_raw"].astype("string"),
            "order_status": clean["order_status_norm"].astype("string"),
            "order_phase_code": pd.to_numeric(clean["order_phase_code"], errors="coerce").astype("Int64"),
            "order_terminal_flag": pd.to_numeric(clean["order_terminal_flag"], errors="coerce").astype("Int64"),
            "order_failure_flag": pd.to_numeric(clean["order_failure_flag"], errors="coerce").astype("Int64"),
            "needs_manual_review": clean["needs_manual_review"].fillna(False).astype(bool),
        }
    )
    validate_cleaned_detector_orders(orders)
    decisions = classify_detector_order_eligibility(orders)
    generated_at = datetime.now(timezone.utc).isoformat()
    source_cleaned_orders_sha256 = _sha256_file(clean_path)
    # Keep the temporary path short on Windows. The Parquet writer adds its own
    # temporary filename, so embedding the descriptive final batch id here can
    # exceed the legacy path limit before the atomic rename.
    staging_root = target.parent.parent / ".clean_input_staging"
    staging = staging_root / uuid.uuid4().hex
    staging.mkdir(parents=True, exist_ok=False)
    try:
        write_production_parquet(orders, staging / "orders.parquet")
        write_production_parquet(decisions, staging / "order_eligibility_audit.parquet")
        manifest = {
            "input_batch_id": str(input_batch_id),
            "raw_batch_id": str(input_batch_id),
            "input_stage": CLEANED_DETECTOR_INPUT_STAGE,
            "source_system": "existing_cleaned_order_chain",
            "table_format": "parquet",
            "data_as_of_date": orders["order_date"].max().date().isoformat(),
            "table_paths": {
                "orders": "orders.parquet",
                "order_eligibility_audit": "order_eligibility_audit.parquet",
            },
            "cleaning_contract": {
                "version": "cleaned_detector_input_v1",
                "cleaned_orders_path": str(clean_path).replace("\\", "/"),
                "cleaned_orders_sha256": source_cleaned_orders_sha256,
                "cleaned_orders_rows": len(clean),
                "canonical_status_mapping_applied": True,
                "direct_purchase_unit_price_only": True,
                "purchase_unit_from_cleaned_orders": True,
                "raw_business_measure_fallback_allowed": False,
                "clickhouse_direct_read_allowed": False,
            },
            "schema_profile": {"orders_columns": list(orders.columns), "orders_rows": len(orders)},
            "audit": {
                "eligible_rows": int(decisions["detector_order_eligible"].sum()),
                "excluded_rows": int((~decisions["detector_order_eligible"]).sum()),
                "purchase_unit_missing_rows": int(orders["purchase_unit"].isna().sum()),
                "purchase_unit_price_missing_rows": int(orders["purchase_unit_price"].isna().sum()),
                "purchase_unit_price_nonpositive_rows": int(orders["purchase_unit_price"].fillna(0).le(0).sum()),
            },
            "generated_at": generated_at,
        }
        (staging / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(staging, target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {
        "input_batch_id": input_batch_id,
        "output_dir": str(target).replace("\\", "/"),
        "orders_rows": len(orders),
        "eligible_rows": int(decisions["detector_order_eligible"].sum()),
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
