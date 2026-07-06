#!/usr/bin/env python
"""Build row-level M-module closure outputs for entity_complete_v2."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from alg.tasks.die_prediction.entity_complete_m_module_closure import (  # noqa: E402
    run_entity_complete_m_module_closure,
)


def main() -> None:
    result = run_entity_complete_m_module_closure(ROOT)
    print("status:", result.get("status"))


if __name__ == "__main__":
    main()
