from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/v1", tags=["internal-runtime-profile"])


@router.get("/runtime-profile")
def runtime_profile(
    report_month: str | None = Query(default=None),
) -> dict[str, Any]:
    batch_dir = _batch_dir(report_month)
    if batch_dir is None or not (batch_dir / "manifest.json").exists():
        return {
            "ready": False,
            "visibility": "internal_diagnostics_only",
            "report_month": report_month,
            "runtime_profile": {},
            "warnings": ["RUNTIME_PROFILE_NOT_AVAILABLE"],
        }
    manifest = json.loads((batch_dir / "manifest.json").read_text(encoding="utf-8"))
    return {
        "ready": True,
        "visibility": "internal_diagnostics_only",
        "report_month": manifest.get("report_month"),
        "batch_id": manifest.get("result_batch_id") or manifest.get("batch_id"),
        "runtime_profile": dict(manifest.get("runtime_profile_summary") or {}),
        "warnings": [],
    }


def _batch_dir(report_month: str | None) -> Path | None:
    batch_root = os.getenv("RISK_RESULT_BATCH_ROOT")
    if batch_root:
        root = Path(batch_root)
        if report_month:
            candidates = sorted((root / f"report_month={report_month}").glob("batch_id=*/manifest.json"))
        else:
            candidates = sorted(root.glob("report_month=*/batch_id=*/manifest.json"))
        return candidates[-1].parent if candidates else None
    batch_dir = os.getenv("RISK_RESULT_BATCH_DIR")
    return Path(batch_dir) if batch_dir else None
