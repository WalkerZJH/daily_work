"""Source-aligned M1 candidate policy for monthly risk runs."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


class BoundedCandidateSelector:
    """Build the complete recurring candidate universe.

    Ranking features are retained for downstream ordering and diagnostics. No
    probability threshold, recall policy, manufacturer cap, or global cap is
    allowed to decide whether a recurring entity is persisted.
    """

    def __init__(self, config: dict):
        self.config = config
        # Kept as compatibility metadata for old manifests. They are not
        # consulted by the production candidate selection path.
        self.policy_pct = float(config.get("candidate_policy_top_pct", 0.10))
        self.policy_name = str(config.get("candidate_policy_name", "multi_recall_union_top10"))

    def select(self, score_frame: pd.DataFrame, feature_frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        joined = self._join_features(score_frame, feature_frame)
        joined["candidate_type"] = classify_candidate_type(
            joined,
            max_monitor_gap_months=int(self.config.get("max_monitor_gap_months", 12)),
        )
        all_seen_rows = int(feature_frame.attrs.get("all_seen_entity_count", len(feature_frame.drop_duplicates("entity_id")) if "entity_id" in feature_frame else len(feature_frame)))
        unmonitorable_rows = int(feature_frame.attrs.get("unmonitorable_entity_count", 0))
        one_shot_rows = int(feature_frame.attrs.get("one_shot_entity_count", joined["candidate_type"].eq("one_shot").sum()))
        recurring_rows = int(feature_frame.attrs.get("recurring_entity_count", joined["candidate_type"].eq("recurring").sum()))
        joined = joined[joined["candidate_type"].eq("recurring")].copy()
        candidate_parts: list[pd.DataFrame] = []
        report_rows: list[dict[str, Any]] = []
        for (horizon, cutoff), group in joined.groupby(["horizon", "cutoff_month"], dropna=False):
            scored = add_candidate_policy_scores(group.copy(), str(horizon))
            part = scored.copy()
            part["candidate_policy"] = "full_recurring_universe"
            part["selection_reason"] = "recurring_eligible"
            candidate_parts.append(part)
            report_rows.append(
                {
                    "horizon": horizon,
                    "cutoff_month": cutoff,
                    "candidate_policy": "full_recurring_universe",
                    "full_universe_rows": len(scored),
                    "candidate_count": len(part),
                    "candidate_rate": 1.0 if len(scored) else np.nan,
                    "manufacturer_coverage": int(part["manufacturer_code"].nunique()) if "manufacturer_code" in part else 0,
                }
            )
        candidates = pd.concat(candidate_parts, ignore_index=True) if candidate_parts else pd.DataFrame(columns=joined.columns)
        candidates = candidates.drop_duplicates("candidate_id")
        candidates["display_section"] = candidates["candidate_type"].map(
            {
                "recurring": "recurring_business_priority",
                "one_shot": "one_shot_attention",
            }
        ).fillna("recurring_business_priority")
        candidates["is_high_risk_candidate"] = (
            candidates["candidate_type"].eq("recurring")
            & candidates.get("probability_display_level", pd.Series("risk_band_only", index=candidates.index)).isin(
                ["probability_allowed", "risk_band_only"]
            )
            & pd.to_numeric(candidates["probability_score"], errors="coerce").ge(0.7)
        )
        selected = candidates.copy()
        sort_columns = [column for column in ["probability_score", "business_priority_score", "candidate_id"] if column in selected.columns]
        if sort_columns:
            selected = selected.sort_values(
                sort_columns,
                ascending=[False] * (len(sort_columns) - (1 if "candidate_id" in sort_columns else 0))
                + ([True] if "candidate_id" in sort_columns else []),
                na_position="last",
                kind="mergesort",
            )
        selected["rank_global"] = range(1, len(selected) + 1)
        selected["rank_per_manufacturer"] = selected.groupby("manufacturer_code").cumcount() + 1
        selected["is_selected_for_frontend"] = True
        selected["selection_caveat"] = "full_recurring_universe;_top_n_is_presentation_only"
        report = pd.DataFrame(report_rows)
        if not selected.empty:
            report = pd.concat(
                [
                    report,
                    pd.DataFrame(
                        [
                            {"metric": "candidate_policy_rows", "value": len(candidates)},
                            {"metric": "selected_candidate_rows", "value": len(selected)},
                            {"metric": "all_seen_purchase_relationship_rows", "value": all_seen_rows},
                            {"metric": "unmonitorable_rows", "value": unmonitorable_rows},
                            {"metric": "one_shot_rows", "value": one_shot_rows},
                            {"metric": "recurring_rows", "value": recurring_rows},
                            {"metric": "selected_recurring_rows", "value": int(selected["candidate_type"].eq("recurring").sum())},
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
            "sample_class",
            "active_month_count_asof_cutoff",
            "months_since_last_purchase_asof_cutoff",
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
    return out


def percentile_rank(values: Any) -> pd.Series:
    if isinstance(values, pd.Series):
        s = pd.to_numeric(values, errors="coerce")
    else:
        s = pd.Series(np.nan)
    if s.notna().sum() == 0:
        return pd.Series(0.0, index=s.index)
    return s.rank(pct=True).fillna(0.0)


def classify_candidate_type(df: pd.DataFrame, *, max_monitor_gap_months: int = 12) -> pd.Series:
    if "sample_class" in df:
        values = df["sample_class"].astype(str)
        return values.where(values.isin(["unmonitorable", "one_shot", "recurring"]), "recurring")
    months_since = pd.to_numeric(df.get("months_since_last_purchase_asof_cutoff"), errors="coerce")
    active_months = pd.to_numeric(df.get("active_month_count_asof_cutoff"), errors="coerce")
    if active_months.notna().any():
        if active_months.lt(1).any():
            raise ValueError("active_month_count_asof_cutoff must be >= 1 for all seen purchase relationships.")
        return pd.Series(
            np.select(
                [
                    months_since.gt(max_monitor_gap_months),
                    active_months.eq(1),
                    active_months.ge(2),
                ],
                ["unmonitorable", "one_shot", "recurring"],
                default="recurring",
            ),
            index=df.index,
        )
    one_shot_source = df.get("one_shot_flag", df.get("is_one_shot", pd.Series(False, index=df.index)))
    one_shot = pd.Series(one_shot_source, index=df.index).fillna(False).astype(bool)
    return pd.Series(
        np.select(
            [one_shot],
            ["one_shot"],
            default="recurring",
        ),
        index=df.index,
    )
