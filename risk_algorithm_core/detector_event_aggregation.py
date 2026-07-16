"""Entity-level, cross-day aggregation of immutable Daily Detector hit facts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd


ENTITY_COLUMNS = ["manufacturer_code", "hospital_code", "drug_code"]
EVENT_KEY_COLUMNS = [*ENTITY_COLUMNS, "observation_date", "detector_id"]
AGGREGATE_KEY_COLUMNS = ["observation_date", *ENTITY_COLUMNS]
DETECTOR_EVENT_AGGREGATE_COLUMNS = [
    "detector_event_aggregate_id",
    "observation_date",
    *ENTITY_COLUMNS,
    "current_detector_count",
    "current_detector_ids",
    "cumulative_hit_count",
    "cumulative_hit_day_count",
    "historical_detector_ids",
    "first_hit_date",
    "last_hit_date",
    "aggregation_schema_version",
    "generated_at",
]
AGGREGATION_SCHEMA_VERSION = "detector_event_aggregation_v1"
DetectorEventAggregationState = dict[tuple[str, str, str], dict[str, Any]]


def build_detector_event_aggregates(
    detector_results: pd.DataFrame,
    *,
    generated_at: str | None = None,
) -> pd.DataFrame:
    """Collapse hit facts to one row per entity/date without losing source events."""
    events = _normalize_hit_events(detector_results)
    if events.empty:
        return pd.DataFrame(columns=DETECTOR_EVENT_AGGREGATE_COLUMNS)

    entity_date = [*ENTITY_COLUMNS, "observation_date"]
    events = events.sort_values([*ENTITY_COLUMNS, "observation_date", "detector_id"], kind="mergesort")
    events["_cumulative_hit_count"] = events.groupby(ENTITY_COLUMNS, sort=False).cumcount() + 1

    current = (
        events.groupby(entity_date, sort=False)
        .agg(
            current_detector_count=("detector_id", "nunique"),
            current_detector_ids=("detector_id", _joined_detector_ids),
            cumulative_hit_count=("_cumulative_hit_count", "max"),
        )
        .reset_index()
        .sort_values([*ENTITY_COLUMNS, "observation_date"], kind="mergesort")
    )
    current["cumulative_hit_day_count"] = current.groupby(ENTITY_COLUMNS, sort=False).cumcount() + 1
    current["first_hit_date"] = current.groupby(ENTITY_COLUMNS, sort=False)["observation_date"].transform("min")
    # Aggregate rows exist only on hit days, so the current row is the latest hit through that date.
    current["last_hit_date"] = current["observation_date"]

    first_by_detector = (
        events.groupby([*ENTITY_COLUMNS, "detector_id"], sort=False)["observation_date"]
        .min()
        .unstack("detector_id")
    )
    current = current.join(first_by_detector, on=ENTITY_COLUMNS)
    detector_ids = sorted(str(value) for value in events["detector_id"].unique())
    current["historical_detector_ids"] = ""
    for detector_id in detector_ids:
        first_date = current[detector_id].astype("string")
        active = first_date.notna() & first_date.le(current["observation_date"].astype("string"))
        current.loc[active, "historical_detector_ids"] += f"{detector_id}|"
    current["historical_detector_ids"] = current["historical_detector_ids"].str.rstrip("|")
    current = current.drop(columns=detector_ids)

    current["detector_event_aggregate_id"] = (
        current["observation_date"].astype(str)
        + "|"
        + current["manufacturer_code"].astype(str)
        + "|"
        + current["hospital_code"].astype(str)
        + "|"
        + current["drug_code"].astype(str)
    )
    current["aggregation_schema_version"] = AGGREGATION_SCHEMA_VERSION
    current["generated_at"] = generated_at or datetime.now(timezone.utc).isoformat()
    return current[DETECTOR_EVENT_AGGREGATE_COLUMNS].sort_values(
        ["observation_date", *ENTITY_COLUMNS], kind="mergesort"
    ).reset_index(drop=True)


def update_detector_event_aggregates(
    detector_results: pd.DataFrame,
    state: DetectorEventAggregationState,
    *,
    generated_at: str,
) -> pd.DataFrame:
    """Aggregate one observation date and update keyed cross-day counters in place."""
    events = _normalize_hit_events(detector_results)
    if events.empty:
        return pd.DataFrame(columns=DETECTOR_EVENT_AGGREGATE_COLUMNS)
    observation_dates = sorted(events["observation_date"].unique())
    if len(observation_dates) != 1:
        raise ValueError(f"Streaming Detector aggregation requires one date, got {observation_dates}")
    observation_date = str(observation_dates[0])
    daily = (
        events.groupby(ENTITY_COLUMNS, sort=True)["detector_id"]
        .agg(_joined_detector_ids)
        .reset_index(name="current_detector_ids")
    )
    rows: list[dict[str, Any]] = []
    for row in daily.itertuples(index=False):
        key = tuple(str(getattr(row, column)) for column in ENTITY_COLUMNS)
        current_ids = _split_detector_ids(row.current_detector_ids)
        entry = state.get(key)
        if entry is None:
            entry = {
                "cumulative_hit_count": 0,
                "cumulative_hit_day_count": 0,
                "historical_detector_ids": set(),
                "first_hit_date": observation_date,
            }
            state[key] = entry
        entry["cumulative_hit_count"] += len(current_ids)
        entry["cumulative_hit_day_count"] += 1
        entry["historical_detector_ids"].update(current_ids)
        manufacturer_code, hospital_code, drug_code = key
        rows.append({
            "detector_event_aggregate_id": (
                f"{observation_date}|{manufacturer_code}|{hospital_code}|{drug_code}"
            ),
            "observation_date": observation_date,
            "manufacturer_code": manufacturer_code,
            "hospital_code": hospital_code,
            "drug_code": drug_code,
            "current_detector_count": len(current_ids),
            "current_detector_ids": "|".join(sorted(current_ids)),
            "cumulative_hit_count": entry["cumulative_hit_count"],
            "cumulative_hit_day_count": entry["cumulative_hit_day_count"],
            "historical_detector_ids": "|".join(sorted(entry["historical_detector_ids"])),
            "first_hit_date": entry["first_hit_date"],
            "last_hit_date": observation_date,
            "aggregation_schema_version": AGGREGATION_SCHEMA_VERSION,
            "generated_at": generated_at,
        })
    return pd.DataFrame(rows, columns=DETECTOR_EVENT_AGGREGATE_COLUMNS)


def validate_detector_event_aggregates(frame: pd.DataFrame) -> dict[str, Any]:
    missing = [column for column in DETECTOR_EVENT_AGGREGATE_COLUMNS if column not in frame]
    if missing:
        raise ValueError(f"Detector event aggregate columns missing: {missing}")
    if frame.duplicated(AGGREGATE_KEY_COLUMNS).any():
        raise ValueError("Detector event aggregate key is not unique")
    if frame.empty:
        return {
            "engineering_gate_status": "passed_empty",
            "row_count": 0,
            "entity_count": 0,
            "observation_date_count": 0,
        }

    current_ids = frame["current_detector_ids"].map(_split_detector_ids)
    historical_ids = frame["historical_detector_ids"].map(_split_detector_ids)
    expected_counts = current_ids.map(len)
    actual_counts = pd.to_numeric(frame["current_detector_count"], errors="raise").astype(int)
    if not expected_counts.eq(actual_counts).all() or actual_counts.lt(1).any():
        raise ValueError("current_detector_count does not match current_detector_ids")
    if any(not current.issubset(history) for current, history in zip(current_ids, historical_ids)):
        raise ValueError("Current Detector ids must be a subset of historical Detector ids")

    ordered = frame.sort_values([*ENTITY_COLUMNS, "observation_date"], kind="mergesort")
    for column in ["cumulative_hit_count", "cumulative_hit_day_count"]:
        values = pd.to_numeric(ordered[column], errors="raise")
        if values.groupby([ordered[name] for name in ENTITY_COLUMNS]).diff().fillna(0).lt(0).any():
            raise ValueError(f"{column} must be monotonic for each entity")
    return {
        "engineering_gate_status": "passed",
        "row_count": int(len(frame)),
        "entity_count": int(frame[ENTITY_COLUMNS].drop_duplicates().shape[0]),
        "observation_date_count": int(frame["observation_date"].nunique()),
        "event_count": int(pd.to_numeric(frame["current_detector_count"], errors="coerce").sum()),
        "max_current_detector_count": int(actual_counts.max()),
        "max_cumulative_hit_count": int(pd.to_numeric(frame["cumulative_hit_count"]).max()),
    }


def _normalize_hit_events(frame: pd.DataFrame) -> pd.DataFrame:
    required = [*EVENT_KEY_COLUMNS, "hit_flag"]
    missing = [column for column in required if column not in frame]
    if missing:
        raise ValueError(f"Detector result event columns missing: {missing}")
    events = frame.loc[frame["hit_flag"].fillna(False).astype(bool), required].copy()
    for column in EVENT_KEY_COLUMNS:
        events[column] = events[column].astype("string").fillna("").str.strip()
    if events[EVENT_KEY_COLUMNS].eq("").any(axis=None):
        raise ValueError("Detector hit event contains a blank event-key value")
    return events.drop_duplicates(EVENT_KEY_COLUMNS, keep="last").reset_index(drop=True)


def _joined_detector_ids(values: pd.Series) -> str:
    return "|".join(sorted(set(values.astype(str))))


def _split_detector_ids(value: Any) -> set[str]:
    return {item for item in str(value or "").split("|") if item}
