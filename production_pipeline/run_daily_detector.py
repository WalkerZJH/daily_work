from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from .common import require_batch_dir


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
    raise NotImplementedError("Detector snapshot execution will be implemented after the snapshot schema is frozen.")


if __name__ == "__main__":
    raise SystemExit(main())
