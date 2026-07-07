#!/usr/bin/env python
"""Extract the MVC-facing risk model package and page payloads."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from alg.tasks.die_prediction.mvc_model_package.pipeline import run_mvc_model_package  # noqa: E402


def main() -> None:
    result = run_mvc_model_package(ROOT)
    print("batch_id:", result["batch_id"])
    print("batch_dir:", result["batch_dir"])
    print("counts:", result["counts"])
    print("unsafe_frontend_text_count:", result["unsafe_frontend_text_count"])


if __name__ == "__main__":
    main()
