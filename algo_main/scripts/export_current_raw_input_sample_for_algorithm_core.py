#!/usr/bin/env python
"""Inspect whether current workspace can export a raw input batch for risk_algorithm_core.

This is an algo_main-side helper only. The independent risk_algorithm_core package
must not import or depend on this script.
"""

from __future__ import annotations

from pathlib import Path
import json


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = REPO_ROOT / "algo_main" / "reports" / "entity_complete_v2_coverage_expansion" / "17_risk_algorithm_core_extraction" / "current_raw_input_adapter_status.md"


def main() -> int:
    candidate_paths = [
        REPO_ROOT / "algo_main" / "data" / "entity_complete_v2_coverage_expansion" / "03_cleaned" / "bs_agent_dingdan_model_base.parquet",
        REPO_ROOT / "algo_main" / "data" / "entity_complete_v2_coverage_expansion" / "02_sql_extract" / "manufacturer_complete_orders.parquet",
    ]
    existing = [path for path in candidate_paths if path.exists()]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Current Raw Input Adapter Status",
        "",
        "This helper is intentionally outside `risk_algorithm_core`.",
        "",
        f"candidate_paths_found: {len(existing)}",
    ]
    for path in existing:
        lines.append(f"- {path.relative_to(REPO_ROOT)}")
    if not existing:
        lines.extend(
            [
                "",
                "blocker: no current raw order-level source path was found for automatic export.",
                "action: provide a `risk_raw_input_batch` directory or add a controlled adapter from the approved cleaned order table.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "status: source-like files exist, but this script does not auto-export company data in this stage.",
                "action: use this inventory to implement a controlled one-way export if needed.",
            ]
        )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"status_report": str(REPORT_PATH), "candidate_paths_found": len(existing)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
