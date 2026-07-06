#!/usr/bin/env python
"""Run entity_complete_v1 main model ablation."""

from __future__ import annotations

from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from alg.tasks.die_prediction.entity_complete_rebuild import run_entity_complete_main_model_ablation


def main() -> None:
    outputs = run_entity_complete_main_model_ablation(ROOT)
    print("prediction rows:", len(outputs["frame"]))
    print("metric rows:", len(outputs["metrics"]))


if __name__ == "__main__":
    main()

