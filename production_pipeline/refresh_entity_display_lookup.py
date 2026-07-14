from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from risk_result_contracts import write_production_parquet

from .common import read_parquet_table, require_batch_dir


IMMUTABLE_TABLES = [
    "risk_entities",
    "risk_entity_horizon_profiles",
    "monthly_reports",
    "daily_detector_runs",
    "daily_detector_clues",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage C display lookup refresh boundary.")
    parser.add_argument("--batch-dir", required=True)
    args = parser.parse_args(argv)
    batch_dir = require_batch_dir(args.batch_dir)
    before = {name: sha256(batch_dir / f"{name}.parquet") for name in IMMUTABLE_TABLES}
    lookup = read_parquet_table(batch_dir, "entity_display_lookup")
    write_production_parquet(lookup, batch_dir / "entity_display_lookup.parquet")
    after = {name: sha256(batch_dir / f"{name}.parquet") for name in IMMUTABLE_TABLES}
    changed = [name for name in IMMUTABLE_TABLES if before[name] != after[name]]
    if changed:
        raise RuntimeError(f"Display lookup refresh modified immutable tables: {changed}")
    payload = {
        "stage": "entity_display_lookup",
        "status": "ok",
        "batch_dir": str(batch_dir).replace("\\", "/"),
        "row_count": int(len(lookup)),
        "immutable_hashes_unchanged": True,
        "forbidden_calls": [
            "ArtifactRiskScorer.score",
            "load_current_model_artifact",
            "BoundedCandidateSelector.select",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    metadata_path = batch_dir / "entity_display_lookup_refresh_status.json"
    metadata_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
