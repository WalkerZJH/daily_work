"""Versioned manufacturer-specific configuration profiles for Daily Detector."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from .detector_config import DailyDetectorConfig


DETECTOR_CONFIG_PROFILE_COLUMNS = [
    "config_id",
    "detector_id",
    "detector_version",
    "config_schema_version",
    "manufacturer_code",
    "parameter_scope",
    "effective_from",
    "effective_to",
    "config_payload",
    "config_hash",
    "generation_method",
    "calibration_batch_id",
    "validation_status",
    "business_approval_status",
    "created_at",
    "created_by",
    "status",
]

DETECTOR_RUN_CONFIG_SNAPSHOT_COLUMNS = [
    "run_id",
    "detector_id",
    "manufacturer_code",
    "date_from",
    "date_to",
    "config_id",
    "config_hash",
    "resolved_at",
]

_NON_PAYLOAD_KEYS = {
    "version",
    "enabled",
    "status",
    "method",
    "parameter_scope",
}


def build_manufacturer_config_profiles(
    manufacturer_codes: Iterable[str],
    config: DailyDetectorConfig,
    *,
    detector_ids: Iterable[str] | None = None,
    calibration_batch_id: str | None = None,
    created_by: str = "detector_profile_batch_generator",
    created_at: str | None = None,
) -> pd.DataFrame:
    """Generate explicit profiles without creating a global fallback."""
    selected = list(detector_ids or config.runnable_detector_ids())
    manufacturers = sorted({str(value).strip() for value in manufacturer_codes if str(value).strip()})
    now = created_at or datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    for detector_id in selected:
        detector = config.detectors.get(detector_id)
        if detector is None:
            raise KeyError(f"Unknown detector_id: {detector_id}")
        scope = str(detector.get("parameter_scope") or "manufacturer_specific")
        if scope != "manufacturer_specific":
            raise ValueError(
                f"Batch manufacturer generator only accepts manufacturer_specific detectors: {detector_id}={scope}"
            )
        payload = {key: value for key, value in detector.items() if key not in _NON_PAYLOAD_KEYS}
        payload_text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for manufacturer_code in manufacturers:
            identity = {
                "detector_id": detector_id,
                "detector_version": config.detector_version(detector_id),
                "manufacturer_code": manufacturer_code,
                "effective_from": config.effective_from,
                "config_payload": payload_text,
            }
            config_hash = hashlib.sha256(
                json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest()
            rows.append(
                {
                    "config_id": f"cfg-{config_hash[:20]}",
                    "detector_id": detector_id,
                    "detector_version": config.detector_version(detector_id),
                    "config_schema_version": "detector_config_profile_v1",
                    "manufacturer_code": manufacturer_code,
                    "parameter_scope": scope,
                    "effective_from": config.effective_from,
                    "effective_to": pd.NA,
                    "config_payload": payload_text,
                    "config_hash": config_hash,
                    "generation_method": "copied_template_unapproved",
                    "calibration_batch_id": calibration_batch_id or pd.NA,
                    "validation_status": "engineering_validated",
                    "business_approval_status": "pending",
                    "created_at": now,
                    "created_by": created_by,
                    "status": "active",
                }
            )
    return pd.DataFrame(rows, columns=DETECTOR_CONFIG_PROFILE_COLUMNS)


def load_detector_config_profiles(path: str | Path) -> pd.DataFrame:
    profile_path = Path(path)
    if profile_path.suffix.lower() == ".parquet":
        frame = pd.read_parquet(profile_path)
    elif profile_path.suffix.lower() == ".json":
        frame = pd.DataFrame(json.loads(profile_path.read_text(encoding="utf-8")))
    else:
        raise ValueError("Detector config profiles must be Parquet or JSON")
    missing = set(DETECTOR_CONFIG_PROFILE_COLUMNS).difference(frame.columns)
    if missing:
        raise ValueError(f"Detector config profiles are missing columns: {sorted(missing)}")
    return frame.loc[:, DETECTOR_CONFIG_PROFILE_COLUMNS].copy()


def resolve_detector_config_profiles(
    profiles: pd.DataFrame,
    *,
    detector_id: str,
    manufacturer_codes: Iterable[str],
    observation_date: str,
    expected_parameter_scope: str = "manufacturer_specific",
) -> tuple[pd.DataFrame, list[str]]:
    """Resolve exactly one profile per manufacturer, without implicit fallback."""
    date = pd.Timestamp(observation_date).normalize()
    scoped = profiles.loc[profiles["detector_id"].astype(str).eq(detector_id)].copy()
    scoped = scoped.loc[scoped["parameter_scope"].astype(str).eq(expected_parameter_scope)]
    scoped = scoped.loc[scoped["status"].astype(str).eq("active")]
    scoped = scoped.loc[scoped["validation_status"].astype(str).eq("engineering_validated")]
    start = pd.to_datetime(scoped["effective_from"], errors="coerce").dt.normalize()
    end = pd.to_datetime(scoped["effective_to"], errors="coerce").dt.normalize()
    scoped = scoped.loc[start.le(date) & (end.isna() | end.ge(date))].copy()

    manufacturers = sorted({str(value).strip() for value in manufacturer_codes if str(value).strip()})
    if expected_parameter_scope == "manufacturer_specific":
        scoped = scoped.loc[scoped["manufacturer_code"].astype(str).isin(manufacturers)]
        counts = scoped.groupby(scoped["manufacturer_code"].astype(str), dropna=False).size()
        duplicates = counts[counts.gt(1)]
        if not duplicates.empty:
            raise ValueError(
                "Multiple effective Detector configs resolved for: "
                + ", ".join(f"{code}={count}" for code, count in duplicates.items())
            )
        resolved_codes = set(scoped["manufacturer_code"].astype(str))
        missing = sorted(set(manufacturers) - resolved_codes)
        return scoped.reset_index(drop=True), missing

    if expected_parameter_scope != "global_shared":
        raise ValueError(f"Unknown parameter scope: {expected_parameter_scope}")
    global_rows = scoped.loc[scoped["manufacturer_code"].isna() | scoped["manufacturer_code"].astype(str).eq("")]
    if len(global_rows) != 1:
        raise ValueError(f"global_shared Detector must resolve exactly one profile, got {len(global_rows)}")
    return global_rows.reset_index(drop=True), []


def build_run_config_snapshot(
    resolved: pd.DataFrame,
    *,
    run_id: str,
    observation_date: str,
    resolved_at: str | None = None,
) -> pd.DataFrame:
    timestamp = resolved_at or datetime.now(timezone.utc).isoformat()
    rows = [
        {
            "run_id": run_id,
            "detector_id": row.detector_id,
            "manufacturer_code": row.manufacturer_code,
            "date_from": observation_date,
            "date_to": observation_date,
            "config_id": row.config_id,
            "config_hash": row.config_hash,
            "resolved_at": timestamp,
        }
        for row in resolved.itertuples(index=False)
    ]
    return pd.DataFrame(rows, columns=DETECTOR_RUN_CONFIG_SNAPSHOT_COLUMNS)


def profile_payload_map(resolved: pd.DataFrame) -> dict[str, dict[str, Any]]:
    return {
        str(row.config_id): json.loads(str(row.config_payload))
        for row in resolved.itertuples(index=False)
    }
