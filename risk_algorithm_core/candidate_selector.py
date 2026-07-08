"""Source-aligned M1 candidate policy for monthly risk runs."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


class BoundedCandidateSelector:
    """Select candidates using the verified v2 multi-recall union policy.

    Worklist topN values remain as downstream presentation load controls. They
    do not define the core M1 candidate pool.
    """

    def __init__(self, config: dict):
        self.config = config
        self.policy_pct = float(config.get("candidate_policy_top_pct", 0.10))
        self.policy_name = str(config.get("candidate_policy_name", "multi_recall_union_top10"))
        self.global_cap = int(config.get("global_candidate_cap", 30000))

    def select(self, score_frame: pd.DataFrame, feature_frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        joined = self._join_features(score_frame, feature_frame)
        candidate_parts: list[pd.DataFrame] = []
        report_rows: list[dict[str, Any]] = []
        for (horizon, cutoff), group in joined.groupby(["horizon", "cutoff_month"], dropna=False):
            scored = add_candidate_policy_scores(group.copy(), str(horizon))
            members = candidate_policy_members(scored, pct=self.policy_pct)
            idx = members.get(self.policy_name, members["multi_recall_union_top10"])
            part = scored.loc[idx].copy()
            part["candidate_policy"] = self.policy_name
            part["selection_reason"] = self.policy_name
            candidate_parts.append(part)
            report_rows.append(
                {
                    "horizon": horizon,
                    "cutoff_month": cutoff,
                    "candidate_policy": self.policy_name,
                    "full_universe_rows": len(scored),
                    "candidate_count": len(part),
                    "candidate_rate": len(part) / len(scored) if len(scored) else np.nan,
                    "manufacturer_coverage": int(part["manufacturer_code"].nunique()) if "manufacturer_code" in part else 0,
                }
            )
        candidates = pd.concat(candidate_parts, ignore_index=True) if candidate_parts else pd.DataFrame(columns=joined.columns)
        candidates = candidates.drop_duplicates("candidate_id")
        candidates["candidate_type"] = classify_candidate_type(candidates)
        candidates["display_section"] = candidates["candidate_type"].map(
            {
                "recurring": "recurring_business_priority",
                "one_shot": "one_shot_attention",
                "demand_shape_observation": "demand_shape_observation",
            }
        ).fillna("demand_shape_observation")
        candidates["is_high_risk_candidate"] = (
            candidates["candidate_type"].eq("recurring")
            & candidates.get("probability_display_level", pd.Series("risk_band_only", index=candidates.index)).isin(
                ["probability_allowed", "risk_band_only"]
            )
            & pd.to_numeric(candidates["probability_score"], errors="coerce").ge(0.7)
        )
        selected = build_manufacturer_worklist(candidates, max_per_manufacturer=int(self.config.get("frontend_max_topN_per_manufacturer", 50)))
        selected = selected.sort_values(["probability_score", "business_priority_score"], ascending=[False, False]).head(self.global_cap)
        selected["rank_global"] = range(1, len(selected) + 1)
        selected["rank_per_manufacturer"] = selected.groupby("manufacturer_code").cumcount() + 1
        selected["is_selected_for_frontend"] = True
        selected["selection_caveat"] = "source_aligned_m1_candidate_policy; presentation_user_fill_is_downstream"
        report = pd.DataFrame(report_rows)
        if not selected.empty:
            report = pd.concat(
                [
                    report,
                    pd.DataFrame(
                        [
                            {"metric": "candidate_policy_rows", "value": len(candidates)},
                            {"metric": "selected_candidate_rows", "value": len(selected)},
                            {"metric": "recurring_rows", "value": int(selected["candidate_type"].eq("recurring").sum())},
                            {"metric": "one_shot_rows", "value": int(selected["candidate_type"].eq("one_shot").sum())},
                            {"metric": "observation_rows", "value": int(selected["candidate_type"].eq("demand_shape_observation").sum())},
                        ]
                    ),
                ],
                ignore_index=True,
                sort=False,
            )
        return selected.reset_index(drop=True), report

    def _join_features(self, score_frame: pd.DataFrame, feature_frame: pd.DataFrame) -> pd.DataFrame:
        sidecar_cols = [
            "entity_id",
            "horizon",
            "one_shot_flag",
            "is_one_shot",
            "demand_shape_label",
            "history_sufficiency_flag",
            "probability_display_level",
            "display_mode",
            "value_at_risk_proxy",
            "potential_value_level",
            "one_shot_attention_score",
            "hospital_display_name",
            "drug_display_name",
            "region_code",
            "region_display_name",
            "recency_only_baseline",
            "frequency_decay_baseline",
            "interval_overdue_baseline",
            "hybrid_interval_frequency_score",
            "current_interval_over_median",
            "quantity_ratio",
        ]
        for h in ["H3", "H6", "H12"]:
            col = f"value_at_risk_amount_nonnegative_{h}_asof_cutoff"
            if col in feature_frame.columns:
                sidecar_cols.append(col)
        available = [c for c in sidecar_cols if c in feature_frame.columns]
        joined = score_frame.merge(feature_frame[available], on=["entity_id", "horizon"], how="left")
        joined["probability_score"] = pd.to_numeric(joined["churn_probability_H"], errors="coerce")
        return joined


def add_candidate_policy_scores(df: pd.DataFrame, horizon: str) -> pd.DataFrame:
    out = df.copy()
    out["probability_rank_score"] = percentile_rank(out["probability_score"])
    out["interval_rank_score"] = percentile_rank(out.get("interval_overdue_baseline"))
    out["frequency_rank_score"] = percentile_rank(out.get("frequency_decay_baseline"))
    value_col = f"value_at_risk_amount_nonnegative_{horizon}_asof_cutoff"
    if value_col in out:
        value_rank = percentile_rank(out[value_col])
    else:
        value_rank = percentile_rank(out.get("value_at_risk_proxy"))
    out["business_priority_score"] = out["probability_rank_score"] * value_rank.fillna(0.5)
    return out


def candidate_policy_members(df: pd.DataFrame, *, pct: float = 0.10) -> dict[str, pd.Index]:
    policies = {
        "probability_top10": select_top_pct(df, "probability_rank_score", pct),
        "interval_top10": select_top_pct(df, "interval_rank_score", pct),
        "frequency_top10": select_top_pct(df, "frequency_rank_score", pct),
        "business_priority_top10": select_top_pct(df, "business_priority_score", pct),
    }
    union = pd.Index([])
    for name in ["probability_top10", "interval_top10", "frequency_top10", "business_priority_top10"]:
        union = union.union(policies[name])
    policies["multi_recall_union_top10"] = union
    return policies


def select_top_pct(df: pd.DataFrame, score_col: str, pct: float) -> pd.Index:
    if df.empty or score_col not in df:
        return pd.Index([])
    n = max(1, int(math.ceil(len(df) * pct)))
    return df.sort_values(score_col, ascending=False).head(n).index


def build_manufacturer_worklist(df: pd.DataFrame, *, max_per_manufacturer: int = 50) -> pd.DataFrame:
    rows = []
    if df.empty:
        return df.copy()
    group_cols = ["manufacturer_code", "cutoff_month", "horizon"]
    for _, group in df.groupby(group_cols, dropna=False):
        top = group.sort_values(["is_high_risk_candidate", "probability_score"], ascending=[False, False]).head(
            min(max_per_manufacturer, len(group))
        )
        rows.append(top.copy())
    out = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=df.columns)
    fill = out["candidate_type"].ne("recurring")
    out.loc[fill, "is_high_risk_candidate"] = False
    out.loc[fill, "selection_reason"] = (
        out.loc[fill, "selection_reason"].astype(str) + "|manufacturer_worklist_fill_observation"
    )
    return out


def percentile_rank(values: Any) -> pd.Series:
    if isinstance(values, pd.Series):
        s = pd.to_numeric(values, errors="coerce")
    else:
        s = pd.Series(np.nan)
    if s.notna().sum() == 0:
        return pd.Series(0.0, index=s.index)
    return s.rank(pct=True).fillna(0.0)


def classify_candidate_type(df: pd.DataFrame) -> pd.Series:
    shape = df.get("demand_shape_label", pd.Series("", index=df.index)).astype(str)
    history = df.get("history_sufficiency_flag", pd.Series("", index=df.index)).astype(str)
    one_shot_source = df.get("one_shot_flag", df.get("is_one_shot", pd.Series(False, index=df.index)))
    one_shot = pd.Series(one_shot_source, index=df.index).fillna(False).astype(bool)
    return pd.Series(
        np.select(
            [one_shot, shape.isin(["intermittent", "lumpy", "cold_start"]) | history.eq("history_insufficient")],
            ["one_shot", "demand_shape_observation"],
            default="recurring",
        ),
        index=df.index,
    )
