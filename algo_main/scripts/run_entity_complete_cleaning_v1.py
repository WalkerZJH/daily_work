#!/usr/bin/env python
"""Run entity_complete_v1 cleaning."""

from __future__ import annotations

from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from alg.tasks.die_prediction.entity_complete_rebuild import run_entity_complete_cleaning


def main() -> None:
    outputs = run_entity_complete_cleaning(ROOT)
    print("clean rows:", len(outputs["clean"]))
    print("model_base rows:", len(outputs["model_base"]))
    print("audit rows:", len(outputs["audit"]))


if __name__ == "__main__":
    main()

