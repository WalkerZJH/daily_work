#!/usr/bin/env python
"""Run entity_complete_v1 fact, feature, and label build."""

from __future__ import annotations

from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from alg.tasks.die_prediction.entity_complete_rebuild import run_entity_complete_feature_build


def main() -> None:
    print("building entity_complete_v1 facts/features/labels with monthly cutoffs...")
    outputs = run_entity_complete_feature_build(ROOT)
    print("fact rows:", len(outputs["purchase_events"]))
    print("feature rows:", len(outputs["features"]))
    print("label rows:", len(outputs["labels"]))


if __name__ == "__main__":
    main()
