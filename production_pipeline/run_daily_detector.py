from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

import pandas as pd

from .common import require_batch_dir
from risk_algorithm_core.daily_detector_runner import build_daily_detector_tables
from risk_result_contracts import write_production_parquet


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage B daily detector boundary.")
    parser.add_argument("--batch-dir", required=True)
    parser.add_argument("--observation-date", required=True)
    args = parser.parse_args(argv)
    batch_dir = require_batch_dir(args.batch_dir)
    snapshot = batch_dir / "detector_input_snapshot.parquet"
    if not snapshot.exists():
        print(
            json.dumps(
                {
                    "stage": "daily_detector",
                    "status": "blocked",
                    "reason": "DETECTOR_INPUT_SNAPSHOT_MISSING",
                    "missing_input": str(snapshot).replace("\\", "/"),
                    "allowed_outputs": [
                        "detector_catalog.parquet",
                        "daily_detector_runs.parquet",
                        "daily_detector_clues.parquet",
                        "high_risk_detector_evidence.parquet",
                        "detector stage metadata",
                    ],
                    "forbidden_calls": [
                        "ArtifactRiskScorer.score",
                        "load_current_model_artifact",
                        "BoundedCandidateSelector.select",
                        "MonthlyRiskRunner.run",
                    ],
                    "observation_date": args.observation_date,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    snapshot_frame = pd.read_parquet(snapshot)
    tables = build_daily_detector_tables(
        risk_entities=pd.DataFrame(),
        scan_features=snapshot_frame,
        report_month=_report_month(args.observation_date),
        run_date=args.observation_date,
        source_raw_batch_id="detector_input_snapshot",
        source_result_batch_id="",
    )
    for table_name, frame in tables.items():
        write_production_parquet(frame, batch_dir / f"{table_name}.parquet")
    manifest_path = batch_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["detector_tables"] = {name: f"{name}.parquet" for name in tables}
    manifest["detector_default_scope"] = "independent_detector_batch"
    manifest["detector_score_probability_interpretation"] = "detector_score_is_not_probability"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"stage": "daily_detector", "status": "completed", "observation_date": args.observation_date, "clue_count": len(tables["daily_detector_clues"])}, ensure_ascii=False))
    return 0


def _report_month(observation_date: str) -> str:
    current = datetime.fromisoformat(observation_date).date().replace(day=1)
    previous = current.replace(day=1) - pd.Timedelta(days=1)
    return previous.strftime("%Y-%m")


if __name__ == "__main__":
    raise SystemExit(main())
