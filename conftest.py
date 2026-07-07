"""Repository-level pytest path setup.

This lets root-level pytest runs collect both independent root packages and the
legacy algo_main test suite, which expects algo_main/src on sys.path.
"""

from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parent
ALGO_SRC = REPO_ROOT / "algo_main" / "src"

for path in [REPO_ROOT, ALGO_SRC]:
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)
