#!/usr/bin/env python
"""Run business detector adaptation over the bounded frontend worklist package."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from alg.tasks.die_prediction.mvc_model_package.business_detector_adaptation import run_business_detector_adaptation  # noqa: E402


def main() -> None:
    result = run_business_detector_adaptation(ROOT)
    print("batch_id:", result["batch_id"])
    print("batch_dir:", result["batch_dir"])
    print("counts:", result["counts"])
    print("detector_gate_rows:", result["detector_gate_rows"])
    print("disabled_detector_notes:", result["disabled_detector_notes"])


if __name__ == "__main__":
    main()

