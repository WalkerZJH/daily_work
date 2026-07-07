"""Bounded worklist candidate selection."""

from __future__ import annotations

import pandas as pd


class BoundedCandidateSelector:
    def __init__(self, config: dict):
        self.config = config
        self.default_topn = int(config.get("frontend_default_topN_per_manufacturer", 20))
        self.one_shot_topn = int(config.get("one_shot_topN_per_manufacturer", 20))
        self.observation_topn = int(config.get("observation_topN_per_manufacturer", 20))
        self.global_cap = int(config.get("global_candidate_cap", 30000))

    def select(self, score_frame: pd.DataFrame, feature_frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        feature_columns = [
            "entity_id",
            "horizon",
            "is_one_shot",
            "demand_shape_label",
            "history_sufficiency_flag",
            "value_at_risk_proxy",
            "potential_value_level",
            "one_shot_attention_score",
            "hospital_display_name",
            "drug_display_name",
            "region_code",
            "region_display_name",
        ]
        joined = score_frame.merge(
            feature_frame[[col for col in feature_columns if col in feature_frame.columns]],
            on=["entity_id", "horizon"],
            how="left",
        )
        selected_parts = [
            self._top_per_manufacturer(
                joined[(~joined["is_one_shot"].fillna(False)) & joined["history_sufficiency_flag"].ne("history_insufficient")],
                self.default_topn,
                "recurring_priority_topN",
                "recurring",
            ),
            self._top_per_manufacturer(
                joined[joined["is_one_shot"].fillna(False)],
                self.one_shot_topn,
                "one_shot_attention_topN",
                "one_shot",
            ),
            self._top_per_manufacturer(
                joined[joined["demand_shape_label"].isin(["intermittent", "lumpy"])],
                self.observation_topn,
                "observation_topN",
                "observation",
            ),
        ]
        selected = pd.concat(selected_parts, ignore_index=True).drop_duplicates("candidate_id")
        selected = selected.sort_values(["churn_probability_H", "value_at_risk_proxy"], ascending=[False, False]).head(self.global_cap)
        selected["rank_global"] = range(1, len(selected) + 1)
        selected["is_selected_for_frontend"] = True
        selected["is_high_risk_candidate"] = selected["candidate_type"].eq("recurring")
        selected["selection_caveat"] = "bounded_monthly_worklist_not_full_universe"
        report = pd.DataFrame(
            [
                {"metric": "selected_candidate_rows", "value": len(selected)},
                {"metric": "recurring_rows", "value": int(selected["candidate_type"].eq("recurring").sum())},
                {"metric": "one_shot_rows", "value": int(selected["candidate_type"].eq("one_shot").sum())},
                {"metric": "observation_rows", "value": int(selected["candidate_type"].eq("observation").sum())},
            ]
        )
        return selected.reset_index(drop=True), report

    def _top_per_manufacturer(self, df: pd.DataFrame, topn: int, reason: str, candidate_type: str) -> pd.DataFrame:
        if df.empty:
            return df.copy()
        out = df.sort_values(["manufacturer_code", "churn_probability_H", "value_at_risk_proxy"], ascending=[True, False, False]).copy()
        out["rank_per_manufacturer"] = out.groupby("manufacturer_code").cumcount() + 1
        out = out[out["rank_per_manufacturer"] <= topn].copy()
        out["candidate_type"] = candidate_type
        out["selection_reason"] = reason
        out["display_section"] = {
            "recurring": "risk_worklist",
            "one_shot": "new_terminal_attention",
            "observation": "observation_watchlist",
        }[candidate_type]
        return out
