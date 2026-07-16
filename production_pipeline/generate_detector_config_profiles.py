"""Generate explicit manufacturer-specific Daily Detector config profiles."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import uuid

from risk_algorithm_core.detector_config import load_daily_detector_config
from risk_algorithm_core.detector_config_profiles import build_manufacturer_config_profiles
from risk_algorithm_core.detector_input import load_cleaned_detector_orders
from risk_result_contracts import write_production_parquet


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate manufacturer-specific Detector config profiles.")
    parser.add_argument("--cleaned-input-batch", required=True)
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--detector-config", default="configs/risk_algorithm_core/daily_detector_rules.yaml")
    parser.add_argument("--detector-id", action="append", dest="detector_ids")
    args = parser.parse_args(argv)
    manifest, orders = load_cleaned_detector_orders(args.cleaned_input_batch)
    config = load_daily_detector_config(args.detector_config)
    profiles = build_manufacturer_config_profiles(
        orders["manufacturer_code"].dropna().astype(str).unique(),
        config,
        detector_ids=args.detector_ids,
        calibration_batch_id=manifest.input_batch_id,
    )
    target = Path(args.output_path)
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite Detector config profiles: {target}")
    staging_root = target.parent / ".config_staging"
    staging_root.mkdir(parents=True, exist_ok=True)
    staging = staging_root / f"{uuid.uuid4().hex}.parquet"
    try:
        write_production_parquet(profiles, staging)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, target)
    except Exception:
        staging.unlink(missing_ok=True)
        raise
    finally:
        if staging_root.exists() and not any(staging_root.iterdir()):
            shutil.rmtree(staging_root, ignore_errors=True)
    print(
        json.dumps(
            {
                "output_path": str(target).replace("\\", "/"),
                "profile_count": len(profiles),
                "manufacturer_count": int(profiles["manufacturer_code"].nunique()),
                "detector_count": int(profiles["detector_id"].nunique()),
                "business_approval_status": "pending",
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
