from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage A monthly prediction boundary.")
    parser.add_argument("--report-month", required=True)
    parser.add_argument("--model-artifact-id", required=True)
    parser.add_argument("--output-root", default="data/project_result_batches")
    parser.add_argument("--parent-batch")
    parser.add_argument("--reason", default="")
    parser.add_argument("--force-repredict", action="store_true")
    args = parser.parse_args(argv)
    if not args.force_repredict:
        print(
            json.dumps(
                {
                    "stage": "monthly_prediction",
                    "status": "blocked",
                    "reason": "Monthly prediction is intentionally not executed without --force-repredict.",
                    "report_month": args.report_month,
                    "model_artifact_id": args.model_artifact_id,
                    "output_root": args.output_root,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    raise NotImplementedError(
        "Monthly prediction execution must be wired to the formal runner in a dedicated task; "
        "this boundary prevents implicit load_current_model_artifact() and accidental historical overwrite."
    )


if __name__ == "__main__":
    raise SystemExit(main())
