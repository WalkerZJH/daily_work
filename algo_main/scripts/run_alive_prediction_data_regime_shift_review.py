#!/usr/bin/env python
"""Review 2024 alive-prediction data regime shift / coverage expansion."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_alive_prediction_feature_stability_v1 as feature_stability
import run_alive_prediction_probability_consolidation as consolidation
import run_alive_prediction_small_model_experiments as small


OUTPUT_DIR = ROOT / "reports/alive_prediction_data_regime_shift_review"
KEY_COLS = ["manufacturer_code", "hospital_code", "drug_group"]
HORIZONS = [3, 6, 12]


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def markdown_table(df: pd.DataFrame) -> str:
    return small.dataframe_to_markdown(df, index=False)


def cutoff_periods(df: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(df["cutoff_month"]).dt.to_period("M")


def entity_key_frame(df: pd.DataFrame) -> pd.DataFrame:
    return df[KEY_COLS].astype(str)


def entity_keys(df: pd.DataFrame) -> set[tuple[str, str, str]]:
    if df.empty:
        return set()
    return set(map(tuple, entity_key_frame(df).to_numpy()))


def entity_count(df: pd.DataFrame) -> int:
    return len(entity_keys(df))


def recurring_only(df: pd.DataFrame) -> pd.DataFrame:
    return small.split_scopes(df)["recurring_only"].copy()


def bucket_age(months: pd.Series) -> pd.Series:
    bins = [-np.inf, 6, 12, 24, 60, np.inf]
    labels = ["0-6", "7-12", "13-24", "25-60", "60+"]
    return pd.cut(pd.to_numeric(months, errors="coerce"), bins=bins, labels=labels).astype("string").fillna("__MISSING__")


def first_seen_period(values: pd.Series) -> pd.Series:
    periods = pd.to_datetime(values, errors="coerce").dt.to_period("M")
    labels = pd.Series("__MISSING__", index=values.index, dtype="string")
    labels[periods < pd.Period("2022-01", freq="M")] = "before_2022"
    labels[(periods >= pd.Period("2022-01", freq="M")) & (periods <= pd.Period("2022-12", freq="M"))] = "2022"
    labels[(periods >= pd.Period("2023-01", freq="M")) & (periods <= pd.Period("2023-12", freq="M"))] = "2023"
    labels[(periods >= pd.Period("2024-01", freq="M")) & (periods <= pd.Period("2024-12", freq="M"))] = "2024"
    labels[(periods >= pd.Period("2025-01", freq="M")) & (periods <= pd.Period("2025-12", freq="M"))] = "2025"
    return labels


def regime(values: pd.Series) -> pd.Series:
    periods = pd.to_datetime(values, errors="coerce").dt.to_period("M")
    labels = pd.Series("__MISSING__", index=values.index, dtype="string")
    labels[periods <= pd.Period("2023-12", freq="M")] = "pre_expansion"
    labels[(periods >= pd.Period("2024-01", freq="M")) & (periods <= pd.Period("2024-12", freq="M"))] = "transition_2024"
    labels[periods >= pd.Period("2025-01", freq="M")] = "post_expansion_candidate"
    return labels


def load_data(config: dict[str, Any]) -> pd.DataFrame:
    df = consolidation.load_feature_data(config)
    return feature_stability.add_stability_features(df)


def entity_inflow_decomposition(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    work["_cutoff_period"] = cutoff_periods(work)
    rows: list[dict[str, Any]] = []
    previous_recurring: set[tuple[str, str, str]] = set()
    previous_one_shot: set[tuple[str, str, str]] = set()
    seen_before: set[tuple[str, str, str]] = set()
    for cutoff in sorted(work["_cutoff_period"].dropna().unique()):
        cutoff_df = work[work["_cutoff_period"].eq(cutoff)]
        recurring_df = cutoff_df[cutoff_df["recurring_candidate_flag"].astype(bool)].copy()
        current_recurring = entity_keys(recurring_df)
        current_all = entity_keys(cutoff_df)
        current_one_shot = entity_keys(cutoff_df[cutoff_df.get("one_shot_flag", False).astype(bool)])
        new_entities = current_recurring - seen_before
        one_shot_to_recurring = (current_recurring - previous_recurring) & previous_one_shot
        returning_entities = (current_recurring - previous_recurring) - new_entities - one_shot_to_recurring
        old_recurring = current_recurring & previous_recurring
        total = len(current_recurring)
        rows.append(
            {
                "cutoff_month": str(cutoff),
                "recurring_entity_count": total,
                "new_entity_count": len(new_entities),
                "returning_entity_count": len(returning_entities),
                "one_shot_to_recurring_count": len(one_shot_to_recurring),
                "old_recurring_count": len(old_recurring),
                "share_new_entity": len(new_entities) / total if total else np.nan,
                "share_returning_entity": len(returning_entities) / total if total else np.nan,
                "share_one_shot_to_recurring": len(one_shot_to_recurring) / total if total else np.nan,
                "share_old_recurring": len(old_recurring) / total if total else np.nan,
                "approximation_note": "returning_entity includes prior monitorable non-recurring and possible gap-return entities; exact gap-out state is not separately materialized in this artifact",
            }
        )
        previous_recurring = current_recurring
        previous_one_shot = current_one_shot
        seen_before |= current_all
    return pd.DataFrame(rows)


def label_rate_by_entity_age(df: pd.DataFrame) -> pd.DataFrame:
    work = recurring_only(df)
    work["entity_age_bucket"] = bucket_age(work["months_observed_asof_cutoff"])
    work["_cutoff_period"] = cutoff_periods(work)
    rows: list[dict[str, Any]] = []
    for (cutoff, age_bucket), part in work.groupby(["_cutoff_period", "entity_age_bucket"], dropna=False, sort=True):
        for horizon in HORIZONS:
            label_col = f"label_die_H{horizon}"
            rows.append(
                {
                    "cutoff_month": str(cutoff),
                    "horizon": horizon,
                    "entity_age_bucket": str(age_bucket),
                    "row_count": int(len(part)),
                    "entity_count": entity_count(part),
                    "positive_rate": float(part[label_col].mean()) if len(part) else np.nan,
                    "mean_months_observed": float(pd.to_numeric(part["months_observed_asof_cutoff"], errors="coerce").mean()) if len(part) else np.nan,
                    "mean_purchase_count": float(pd.to_numeric(part["purchase_count_asof_cutoff"], errors="coerce").mean()) if len(part) else np.nan,
                    "mean_active_month_count": float(pd.to_numeric(part["active_month_count_asof_cutoff"], errors="coerce").mean()) if len(part) else np.nan,
                }
            )
    return pd.DataFrame(rows)


def label_rate_by_first_seen(df: pd.DataFrame) -> pd.DataFrame:
    work = recurring_only(df)
    work["first_seen_period"] = first_seen_period(work["first_purchase_month_asof_cutoff"])
    work["_cutoff_period"] = cutoff_periods(work)
    rows: list[dict[str, Any]] = []
    for (cutoff, first_seen), part in work.groupby(["_cutoff_period", "first_seen_period"], dropna=False, sort=True):
        for horizon in HORIZONS:
            label_col = f"label_die_H{horizon}"
            rows.append(
                {
                    "cutoff_month": str(cutoff),
                    "horizon": horizon,
                    "first_seen_period": str(first_seen),
                    "row_count": int(len(part)),
                    "entity_count": entity_count(part),
                    "positive_rate": float(part[label_col].mean()) if len(part) else np.nan,
                }
            )
    return pd.DataFrame(rows)


def demand_shape_by_regime(df: pd.DataFrame) -> pd.DataFrame:
    work = recurring_only(df)
    work["regime"] = regime(work["cutoff_month"])
    work["demand_shape_label"] = work["demand_shape_label"].astype("string").fillna("__MISSING__")
    rows: list[dict[str, Any]] = []
    for regime_name, regime_df in work.groupby("regime", dropna=False, sort=True):
        total = len(regime_df)
        for shape, part in regime_df.groupby("demand_shape_label", dropna=False, sort=True):
            row = {
                "regime": str(regime_name),
                "demand_shape_label": str(shape),
                "row_count": int(len(part)),
                "entity_count": entity_count(part),
                "share": len(part) / total if total else np.nan,
            }
            for horizon in HORIZONS:
                row[f"positive_rate_H{horizon}"] = float(part[f"label_die_H{horizon}"].mean()) if len(part) else np.nan
            rows.append(row)
    return pd.DataFrame(rows)


def purchase_month_max() -> pd.Period | None:
    fact_path = ROOT / "data/04_facts/alive_prediction/fact_purchase_event__drug_code.parquet"
    if not fact_path.exists():
        return None
    events = pd.read_parquet(fact_path, columns=["purchase_month"])
    if events.empty:
        return None
    return pd.to_datetime(events["purchase_month"]).dt.to_period("M").max()


def label_window_closure_check(df: pd.DataFrame) -> pd.DataFrame:
    max_purchase = purchase_month_max()
    available_cutoffs = set(cutoff_periods(df).dropna().unique())
    observed_min = min(available_cutoffs) if available_cutoffs else pd.Period("2020-01", freq="M")
    observed_max = max(available_cutoffs) if available_cutoffs else pd.Period("2024-12", freq="M")
    check_cutoffs = list(pd.period_range(observed_min, max(observed_max, pd.Period("2025-12", freq="M")), freq="M"))
    rows: list[dict[str, Any]] = []
    for cutoff in check_cutoffs:
        for horizon in HORIZONS:
            label_end = cutoff + horizon
            closed = bool(max_purchase is not None and label_end <= max_purchase)
            feature_available = cutoff in available_cutoffs
            rows.append(
                {
                    "cutoff_month": str(cutoff),
                    "horizon": horizon,
                    "label_window_end": str(label_end),
                    "data_purchase_month_max": str(max_purchase) if max_purchase is not None else "",
                    "label_window_closed": closed,
                    "usable_for_label_rate_conclusion": bool(closed and feature_available),
                    "feature_cutoff_available": feature_available,
                    "note": "" if feature_available else "feature/label cutoff not materialized; cannot use for label-rate conclusion",
                }
            )
    return pd.DataFrame(rows)


def write_regime_split_recommendation(
    inflow: pd.DataFrame,
    age_rates: pd.DataFrame,
    first_seen_rates: pd.DataFrame,
    demand_shape: pd.DataFrame,
    closure: pd.DataFrame,
) -> None:
    transition = inflow[inflow["cutoff_month"].between("2024-01", "2024-12")].copy()
    shares = transition[
        ["share_new_entity", "share_returning_entity", "share_one_shot_to_recurring", "share_old_recurring"]
    ].mean(numeric_only=True)
    post = closure[closure["cutoff_month"].str.startswith("2025")]
    h12_2025_closed = bool(post[post["horizon"].eq(12)]["usable_for_label_rate_conclusion"].any()) if not post.empty else False
    lines = [
        "# Regime Split Recommendation",
        "",
        "This is a data regime shift review, not a new model experiment.",
        "",
        "## Answers",
        "1. The 2024 difference is better described as a data regime shift / coverage expansion than ordinary behavioral drift alone.",
        "2. Do not delete pre-2024 data. It remains useful as old-regime history and for relative features, but should be interpreted with a regime flag in validation.",
        "3. Do not blindly train only on the most recent two years yet. 2024 is a transition regime and stable post-expansion labels are not yet materialized in this feature table.",
        "4. Training only on 2024-2025 would face H12 label-closure limits, fewer closed post-expansion samples, and insufficient stable new-regime validation.",
        "5. Do not switch the main model to weekly grain just to increase sample count. Weekly grain is better reserved for line refresh cadence and lead-time analysis.",
        "6. Recommended strategy: keep pre-2024, mark 2024 as transition, prefer relative features like frequency_decay_v1, and run post-expansion calibration/validation after 2025/2026 labels are closed and materialized.",
        "",
        "## 2024 Inflow Share Means",
        markdown_table(shares.reset_index().rename(columns={"index": "component", 0: "mean_share"})),
        "",
        f"2025 H12 usable for label-rate conclusion: `{str(h12_2025_closed).lower()}`. This is false when either the label window is not closed or 2025 feature/label cutoffs are not materialized.",
    ]
    write_text(OUTPUT_DIR / "regime_split_recommendation.md", "\n".join(lines))


def write_notebook_update_note() -> None:
    lines = [
        "# Notebook Update Note",
        "",
        "The model-selection story notebook should include section `4.1 2024 数据采集覆盖扩张解释` after the temporal drift section.",
        "",
        "Required interpretation:",
        "- recurring entity count grows rapidly in 2024.",
        "- label positive rate drops in early 2024 and rises again in late 2024.",
        "- A plausible business explanation is stricter online hospital purchasing requirements, which increased order collection coverage.",
        "- The issue should be described as data regime shift / coverage expansion, not only generic behavior drift.",
        "- Do not delete old data directly.",
        "- Treat 2024 as a transition regime and validate/calibrate on stable post-expansion years after labels close.",
    ]
    write_text(OUTPUT_DIR / "notebook_update_note.md", "\n".join(lines))


def write_summary(
    inflow: pd.DataFrame,
    age_rates: pd.DataFrame,
    first_seen_rates: pd.DataFrame,
    demand_shape: pd.DataFrame,
    closure: pd.DataFrame,
) -> None:
    transition = inflow[inflow["cutoff_month"].between("2024-01", "2024-12")].copy()
    inflow_mean = transition[
        [
            "share_new_entity",
            "share_returning_entity",
            "share_one_shot_to_recurring",
            "share_old_recurring",
        ]
    ].mean(numeric_only=True)
    main_component = inflow_mean.idxmax() if not inflow_mean.empty else "unknown"
    first_2024 = first_seen_rates[
        first_seen_rates["cutoff_month"].between("2024-01", "2024-12")
        & first_seen_rates["first_seen_period"].eq("2024")
    ]
    all_2024 = first_seen_rates[first_seen_rates["cutoff_month"].between("2024-01", "2024-12")]
    first_2024_rate = first_2024.groupby("horizon")["positive_rate"].mean(numeric_only=True).reset_index()
    all_2024_rate = all_2024.groupby("horizon")["positive_rate"].mean(numeric_only=True).reset_index()
    late_age = age_rates[age_rates["cutoff_month"].between("2024-09", "2024-12")]
    early_age = age_rates[age_rates["cutoff_month"].between("2024-01", "2024-04")]
    closure_2025 = closure[closure["cutoff_month"].str.startswith("2025")]
    lines = [
        "# 2024 Data Regime Shift Review Summary",
        "",
        "This report reframes the prior temporal drift finding as a likely 2024 data regime shift / collection coverage expansion. It does not retrain models and does not change `probability_candidate_v1`.",
        "",
        "## Core Findings",
        f"- Main 2024 recurring-pool component by average share: `{main_component}`.",
        "- 2024 recurring entity growth is not just ordinary behavior drift; it is consistent with a broader monitored sample-pool expansion.",
        "- 2024 positive-rate movement should be read together with first-seen period and entity age; early-2024 lower rates are plausibly linked to newly covered or shorter-history entities entering the monitored pool.",
        "- Late-2024 positive-rate rebound is compatible with cohort aging and base-rate normalization after transition, but this remains an observational diagnosis.",
        "- 2025/post-expansion label-rate conclusions require both closed label windows and materialized feature/label cutoffs.",
        "",
        "## 2024 Entity Inflow Mean Shares",
        markdown_table(inflow_mean.reset_index().rename(columns={"index": "component", 0: "mean_share"})),
        "",
        "## First-Seen 2024 Mean Positive Rate",
        markdown_table(first_2024_rate),
        "",
        "## All 2024 Mean Positive Rate",
        markdown_table(all_2024_rate),
        "",
        "## Early 2024 Age-Bucket Label Rate Sample",
        markdown_table(early_age.head(20)),
        "",
        "## Late 2024 Age-Bucket Label Rate Sample",
        markdown_table(late_age.head(20)),
        "",
        "## Demand Shape by Regime",
        markdown_table(demand_shape),
        "",
        "## 2025 Closure Check Sample",
        markdown_table(closure_2025.head(36)),
        "",
        "## Decisions",
        "- Do not delete pre-2024 data.",
        "- Keep 2024 as transition regime in interpretation.",
        "- Keep `probability_candidate_v1 = logistic_regression + frequency_decay_v1 + raw` unchanged.",
        "- Do not switch the main model to weekly grain at this stage.",
        "- Next validation should use post-expansion years once labels close and feature/label artifacts are materialized.",
    ]
    write_text(OUTPUT_DIR / "data_regime_shift_summary.md", "\n".join(lines))


def run_review() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    config = small.read_yaml(ROOT / "configs/experiments/alive_prediction_small_models.yaml")
    df = load_data(config)
    inflow = entity_inflow_decomposition(df)
    age_rates = label_rate_by_entity_age(df)
    first_seen_rates = label_rate_by_first_seen(df)
    demand_shape = demand_shape_by_regime(df)
    closure = label_window_closure_check(df)

    inflow.to_csv(OUTPUT_DIR / "cutoff_entity_inflow_decomposition.csv", index=False, encoding="utf-8-sig")
    age_rates.to_csv(OUTPUT_DIR / "cutoff_label_rate_by_entity_age.csv", index=False, encoding="utf-8-sig")
    first_seen_rates.to_csv(OUTPUT_DIR / "cutoff_label_rate_by_first_seen_period.csv", index=False, encoding="utf-8-sig")
    demand_shape.to_csv(OUTPUT_DIR / "demand_shape_by_regime.csv", index=False, encoding="utf-8-sig")
    closure.to_csv(OUTPUT_DIR / "label_window_closure_check.csv", index=False, encoding="utf-8-sig")
    write_regime_split_recommendation(inflow, age_rates, first_seen_rates, demand_shape, closure)
    write_notebook_update_note()
    write_summary(inflow, age_rates, first_seen_rates, demand_shape, closure)


def main() -> int:
    run_review()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
