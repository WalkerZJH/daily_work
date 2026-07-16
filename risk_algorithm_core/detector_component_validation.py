"""Pre-publish engineering gate for one immutable Detector component."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .detector_results import DETECTOR_TABLES


FORBIDDEN_CAUSAL_TEXT = (
    "竞品替代已确认",
    "价格竞争已发生",
    "配送商责任",
    "已经流失",
)


def validate_detector_component_tables(
    tables: dict[str, pd.DataFrame],
    *,
    detector_id: str,
    observation_date: str,
) -> dict[str, Any]:
    missing_tables = sorted(set(DETECTOR_TABLES) - set(tables))
    if missing_tables:
        raise ValueError(f"Detector component is missing tables: {missing_tables}")
    schema_errors: dict[str, list[str]] = {}
    for name, required in DETECTOR_TABLES.items():
        missing = sorted(set(required) - set(tables[name].columns))
        if missing:
            schema_errors[name] = missing
    if schema_errors:
        raise ValueError(f"Detector component schema gate failed: {schema_errors}")

    results = tables["daily_detector_results"]
    clues = tables["daily_detector_clues"]
    profiles = tables["detector_config_profiles"]
    snapshots = tables["detector_run_config_snapshot"]
    if results.empty:
        raise ValueError(f"Detector component {detector_id} produced no evaluation rows")
    if results["detector_result_id"].astype(str).duplicated().any():
        raise ValueError("Detector result ids must be unique within a component")
    if set(results["detector_id"].astype(str)) != {detector_id}:
        raise ValueError("Detector component contains another detector_id")
    if set(results["observation_date"].astype(str)) != {observation_date}:
        raise ValueError("Detector component contains another observation_date")
    if results["eligibility_status"].astype(str).eq("config_missing").any():
        raise ValueError("Detector component cannot publish config_missing evaluations")
    if results["config_id"].astype(str).eq("").any() or results["config_hash"].astype(str).eq("").any():
        raise ValueError("Every Detector result must retain config_id and config_hash")
    if not clues.empty and not clues["hit_flag"].fillna(False).all():
        raise ValueError("daily_detector_clues must contain hit rows only")
    if not set(clues.get("detector_clue_id", pd.Series(dtype=str)).astype(str)).issubset(
        set(results["detector_result_id"].astype(str))
    ):
        raise ValueError("Every clue must reference a result row in the same component")

    result_manufacturers = set(results["manufacturer_code"].astype(str))
    profile_manufacturers = set(profiles["manufacturer_code"].astype(str))
    snapshot_manufacturers = set(snapshots["manufacturer_code"].astype(str))
    if result_manufacturers != profile_manufacturers or result_manufacturers != snapshot_manufacturers:
        raise ValueError("Result, config profile, and run snapshot manufacturer scopes differ")
    combined_text = "\n".join(
        results.get("evidence_text", pd.Series(dtype=str)).fillna("").astype(str).tolist()
        + results.get("caveat", pd.Series(dtype=str)).fillna("").astype(str).tolist()
    )
    forbidden_found = [text for text in FORBIDDEN_CAUSAL_TEXT if text in combined_text]
    if forbidden_found:
        raise ValueError(f"Detector component contains forbidden causal claims: {forbidden_found}")

    return {
        "engineering_gate_status": "passed",
        "config_policy_status": "admin_only_read_only",
        "detector_id": detector_id,
        "observation_date": observation_date,
        "result_count": int(len(results)),
        "clue_count": int(len(clues)),
        "manufacturer_count": int(len(result_manufacturers)),
        "config_profile_count": int(len(profiles)),
        "config_missing_count": 0,
        "forbidden_causal_claim_count": 0,
    }
