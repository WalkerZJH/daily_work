#!/usr/bin/env python
"""Generate alive prediction L2/L3 algorithm alignment design v1."""

from __future__ import annotations

from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from alg.tasks.die_prediction.l2_l3_design import write_l2_l3_design


def main() -> None:
    result = write_l2_l3_design(ROOT)
    print(f"output_dir={result['output_dir']}")
    print(f"fdr_eligible={','.join(result['fdr_eligible'])}")
    print(f"corroboration_only={','.join(result['corroboration_only'])}")
    print(f"interface_only={','.join(result['interface_only'])}")
    print(f"risk_count={result['risk_count']}")


if __name__ == "__main__":
    main()
