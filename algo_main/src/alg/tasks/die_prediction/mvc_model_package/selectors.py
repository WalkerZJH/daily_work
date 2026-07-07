"""Candidate selectors for bounded frontend model packages."""

from __future__ import annotations

import pandas as pd

from .scope_config import FrontendScopeConfig


FRONTEND_ALLOWED_STATUSES = {
    "priority_review",
    "manual_review",
    "observation_only",
    "low_confidence_watch",
    "one_shot_attention",
}


def select_frontend_worklist_candidates(
    inputs: dict[str, pd.DataFrame],
    config: FrontendScopeConfig | None = None,
) -> pd.DataFrame:
    """Return the bounded frontend candidate scope.

    The primary source is M1 manufacturer worklist. This deliberately excludes
    full M5/M7/M4 rows, full one-shot, full observation, and full probability
    gate tables.
    """
    config = config or FrontendScopeConfig()
    worklist = inputs.get("worklist", pd.DataFrame()).copy()
    if worklist.empty:
        return pd.DataFrame(columns=["candidate_id"])

    worklist["candidate_id"] = worklist["candidate_id"].astype(str)
    worklist = worklist.drop_duplicates("candidate_id").copy()

    if "final_candidate_status" in worklist:
        worklist = worklist[worklist["final_candidate_status"].isin(FRONTEND_ALLOWED_STATUSES)]

    if "manufacturer_code" in worklist:
        worklist = _cap_one_shot_and_observation(worklist, config)

    worklist["source_scope"] = "m1_manufacturer_worklist"
    return worklist.reset_index(drop=True)


def _cap_one_shot_and_observation(worklist: pd.DataFrame, config: FrontendScopeConfig) -> pd.DataFrame:
    """Cap broad attention/observation rows per manufacturer while preserving core recurring worklist."""
    if "candidate_type" not in worklist:
        return worklist

    parts: list[pd.DataFrame] = []
    recurring = worklist[~worklist["candidate_type"].isin(["one_shot", "demand_shape_observation"])].copy()
    parts.append(recurring)

    one_shot = worklist[worklist["candidate_type"].eq("one_shot")].copy()
    if not one_shot.empty:
        parts.append(_top_by_manufacturer(one_shot, config.one_shot_topn_per_manufacturer))

    observation = worklist[worklist["candidate_type"].eq("demand_shape_observation")].copy()
    if not observation.empty:
        parts.append(_top_by_manufacturer(observation, config.observation_topn_per_manufacturer))

    out = pd.concat(parts, ignore_index=True) if parts else worklist.iloc[0:0].copy()
    return out.drop_duplicates("candidate_id")


def _top_by_manufacturer(df: pd.DataFrame, n: int) -> pd.DataFrame:
    work = df.copy()
    if "probability_score" in work:
        work["_scope_rank_score"] = pd.to_numeric(work["probability_score"], errors="coerce").fillna(0)
    elif "churn_probability_H" in work:
        work["_scope_rank_score"] = pd.to_numeric(work["churn_probability_H"], errors="coerce").fillna(0)
    else:
        work["_scope_rank_score"] = 0
    work = work.sort_values(["manufacturer_code", "_scope_rank_score"], ascending=[True, False])
    return work.groupby("manufacturer_code", group_keys=False).head(n).drop(columns=["_scope_rank_score"], errors="ignore")

