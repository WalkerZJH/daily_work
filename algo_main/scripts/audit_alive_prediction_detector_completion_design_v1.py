#!/usr/bin/env python
"""Generate M4 detector completion feasibility and design audit."""

from __future__ import annotations

from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from alg.tasks.die_prediction.detector_completion_design import write_detector_completion_audit


def main() -> None:
    result = write_detector_completion_audit(ROOT)
    print(f"output_dir={result['output_dir']}")
    print(f"detector_gap_matrix_rows={result['matrix_rows']}")
    print(f"implement_now={','.join(result['implement_now'])}")
    print(f"design_first={','.join(result['design_first'])}")
    print(f"interface_only={','.join(result['interface_only'])}")
    print(f"skip_current_stage={','.join(result['skip_current_stage'])}")


if __name__ == "__main__":
    main()
