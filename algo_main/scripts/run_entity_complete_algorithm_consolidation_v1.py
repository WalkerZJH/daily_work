from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from alg.tasks.die_prediction.entity_complete_algorithm_consolidation import (  # noqa: E402
    run_entity_complete_algorithm_consolidation,
)


def main() -> None:
    run_entity_complete_algorithm_consolidation(ROOT)


if __name__ == "__main__":
    main()
