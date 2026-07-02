"""Read-only audit helpers for alive prediction M1/M2 prototype outputs."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


ENTITY_COLS = ["manufacturer_code", "hospital_code", "drug_group"]
ENTITY_CUTOFF_COLS = ENTITY_COLS + ["cutoff_month"]
ENTITY_CUTOFF_HORIZON_COLS = ENTITY_CUTOFF_COLS + ["horizon"]
HORIZONS = [3, 6, 12]


def load_csv_if_exists(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    return pd.read_csv(path)


def read_md_head(path: Path, max_chars: int = 3000) -> str:
    if not path.exists():
        return "missing"
    return path.read_text(encoding="utf-8", errors="replace")[:max_chars]


def normalize_month_column(df: pd.DataFrame, column: str) -> pd.DataFrame:
    out = df.copy()
    if column in out.columns:
        out[column] = pd.to_datetime(out[column], errors="coerce").dt.to_period("M").astype(str)
    return out


def add_entity_key(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ENTITY_COLS:
        if col not in out.columns:
            out[col] = ""
    out["entity_key"] = out[ENTITY_COLS].astype(str).agg("|".join, axis=1)
    return out


def safe_nunique(df: pd.DataFrame, cols: Iterable[str]) -> int:
    cols = [c for c in cols if c in df.columns]
    if not cols or df.empty:
        return 0
    return int(df[cols].drop_duplicates().shape[0])


def row_decomposition(obs: pd.DataFrame) -> pd.DataFrame:
    """Summarize why demand-shape observation rows expand."""

    if obs is None or obs.empty:
        return pd.DataFrame(
            [
                {"metric": "total_rows", "value": 0},
                {"metric": "unique_entity_count", "value": 0},
                {"metric": "unique_entity_cutoff_count", "value": 0},
                {"metric": "unique_entity_cutoff_horizon_count", "value": 0},
            ]
        )
    work = add_entity_key(normalize_month_column(obs, "cutoff_month"))
    total = len(work)
    entity_count = safe_nunique(work, ENTITY_COLS)
    entity_cutoff_count = safe_nunique(work, ENTITY_CUTOFF_COLS)
    entity_cutoff_horizon_count = safe_nunique(work, ENTITY_CUTOFF_HORIZON_COLS)
    cutoff_count = work["cutoff_month"].nunique(dropna=True) if "cutoff_month" in work.columns else 0
    duplicate_reason = 0
    if set(ENTITY_CUTOFF_HORIZON_COLS + ["observation_reason"]).issubset(work.columns):
        duplicate_reason = int(
            work.groupby(ENTITY_CUTOFF_HORIZON_COLS, dropna=False)["observation_reason"].nunique().gt(1).sum()
        )
    rows = [
        {"metric": "total_rows", "value": total},
        {"metric": "unique_entity_count", "value": entity_count},
        {"metric": "unique_entity_cutoff_count", "value": entity_cutoff_count},
        {"metric": "unique_entity_cutoff_horizon_count", "value": entity_cutoff_horizon_count},
        {"metric": "cutoff_month_count", "value": int(cutoff_count)},
        {"metric": "avg_rows_per_entity", "value": total / entity_count if entity_count else np.nan},
        {
            "metric": "avg_horizons_per_entity_cutoff",
            "value": entity_cutoff_horizon_count / entity_cutoff_count if entity_cutoff_count else np.nan,
        },
        {"metric": "entity_cutoff_horizon_with_multiple_reasons", "value": duplicate_reason},
    ]
    return pd.DataFrame(rows)


def by_cutoff_horizon(obs: pd.DataFrame) -> pd.DataFrame:
    if obs is None or obs.empty:
        return pd.DataFrame(columns=["cutoff_month", "horizon", "row_count", "entity_count"])
    work = add_entity_key(normalize_month_column(obs, "cutoff_month"))
    return (
        work.groupby(["cutoff_month", "horizon"], dropna=False)
        .agg(row_count=("entity_key", "size"), entity_count=("entity_key", "nunique"))
        .reset_index()
        .sort_values(["cutoff_month", "horizon"])
    )


def latest_cutoff_summary(obs: pd.DataFrame) -> pd.DataFrame:
    if obs is None or obs.empty or "cutoff_month" not in obs.columns:
        return pd.DataFrame(columns=["cutoff_month", "horizon", "row_count", "entity_count"])
    work = add_entity_key(normalize_month_column(obs, "cutoff_month"))
    latest = str(work["cutoff_month"].dropna().max())
    part = work[work["cutoff_month"].eq(latest)].copy()
    horizon = (
        part.groupby("horizon", dropna=False)
        .agg(row_count=("entity_key", "size"), entity_count=("entity_key", "nunique"))
        .reset_index()
    )
    total = pd.DataFrame(
        [
            {
                "cutoff_month": latest,
                "horizon": "all",
                "row_count": int(len(part)),
                "entity_count": int(part["entity_key"].nunique()),
            }
        ]
    )
    horizon.insert(0, "cutoff_month", latest)
    return pd.concat([total, horizon], ignore_index=True)


def value_counts_summary(df: pd.DataFrame | None, column: str, *, output_name: str) -> pd.DataFrame:
    if df is None or df.empty or column not in df.columns:
        return pd.DataFrame(columns=[output_name, "row_count", "share"])
    vc = df[column].fillna("__MISSING__").astype(str).value_counts(dropna=False).reset_index()
    vc.columns = [output_name, "row_count"]
    vc["share"] = vc["row_count"] / len(df)
    return vc


def enrich_observation_with_features(obs: pd.DataFrame, features: pd.DataFrame | None) -> pd.DataFrame:
    if obs is None:
        return pd.DataFrame()
    work = normalize_month_column(obs, "cutoff_month")
    if features is None or features.empty:
        return work
    feat = normalize_month_column(features, "cutoff_month")
    if "drug_group_source" not in feat.columns:
        feat["drug_group_source"] = "drug_code"
    join_cols = [c for c in ["manufacturer_code", "hospital_code", "drug_group", "drug_group_source", "cutoff_month"] if c in feat.columns and c in work.columns]
    keep = join_cols + [
        c
        for c in [
            "purchase_count_asof_cutoff",
            "active_month_count_asof_cutoff",
            "months_observed_asof_cutoff",
            "adi_asof_cutoff",
            "cv2_quantity_asof_cutoff",
            "historical_avg_monthly_amount_asof_cutoff",
            "purchase_amount_sum_last_12m_asof_cutoff",
            "purchase_amount_sum_last_6m_asof_cutoff",
            "purchase_amount_sum_last_3m_asof_cutoff",
        ]
        if c in feat.columns
    ]
    return work.merge(feat[keep].drop_duplicates(join_cols), on=join_cols, how="left") if join_cols else work


def history_sufficiency_audit(enriched_obs: pd.DataFrame) -> pd.DataFrame:
    if enriched_obs.empty:
        return pd.DataFrame()
    work = enriched_obs.copy()
    rows: list[dict[str, object]] = []
    for label, group in work.groupby(work.get("demand_shape_label", pd.Series("__MISSING__", index=work.index)).fillna("__MISSING__"), dropna=False):
        row = {"demand_shape_label": label, "row_count": int(len(group)), "entity_count": safe_nunique(group, ENTITY_COLS)}
        for col in ["purchase_count_asof_cutoff", "active_month_count_asof_cutoff", "months_observed_asof_cutoff"]:
            if col in group.columns:
                vals = pd.to_numeric(group[col], errors="coerce")
                row[f"{col}_mean"] = float(vals.mean())
                row[f"{col}_median"] = float(vals.median())
                row[f"{col}_p25"] = float(vals.quantile(0.25))
                row[f"{col}_p75"] = float(vals.quantile(0.75))
                row[f"{col}_missing_rate"] = float(vals.isna().mean())
        if "purchase_count_asof_cutoff" in group.columns:
            row["share_purchase_count_lt_3"] = float(pd.to_numeric(group["purchase_count_asof_cutoff"], errors="coerce").lt(3).mean())
        if "active_month_count_asof_cutoff" in group.columns:
            row["share_active_month_count_lt_2"] = float(pd.to_numeric(group["active_month_count_asof_cutoff"], errors="coerce").lt(2).mean())
        if "adi_asof_cutoff" in group.columns:
            row["adi_missing_rate"] = float(group["adi_asof_cutoff"].isna().mean())
        if "cv2_quantity_asof_cutoff" in group.columns:
            row["cv2_missing_rate"] = float(group["cv2_quantity_asof_cutoff"].isna().mean())
        row["demand_shape_missing_rate"] = float(work.get("demand_shape_label", pd.Series(index=work.index)).isna().mean())
        rows.append(row)
    return pd.DataFrame(rows).sort_values("row_count", ascending=False).reset_index(drop=True)


def _bin_series(series: pd.Series, bins: list[float], labels: list[str]) -> pd.Series:
    return pd.cut(pd.to_numeric(series, errors="coerce"), bins=bins, labels=labels, include_lowest=True)


def add_relative_value_fields(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    horizon = pd.to_numeric(out.get("horizon", pd.Series(np.nan, index=out.index)), errors="coerce")
    monthly = pd.Series(np.nan, index=out.index, dtype="float64")
    fallbacks = [
        ("historical_avg_monthly_amount_asof_cutoff", 1.0),
        ("purchase_amount_sum_last_12m_asof_cutoff", 1 / 12),
        ("purchase_amount_sum_last_6m_asof_cutoff", 1 / 6),
        ("purchase_amount_sum_last_3m_asof_cutoff", 1 / 3),
    ]
    for col, mult in fallbacks:
        if col not in out.columns:
            continue
        vals = pd.to_numeric(out[col], errors="coerce") * mult
        monthly = monthly.fillna(vals)
    out["relative_value_at_risk_H"] = (monthly * horizon).clip(lower=0)
    out["relative_business_priority_score_H"] = (
        pd.to_numeric(out.get("churn_probability_H", pd.Series(np.nan, index=out.index)), errors="coerce")
        * out["relative_value_at_risk_H"]
    )
    return out


def probability_value_audit(enriched_obs: pd.DataFrame) -> pd.DataFrame:
    if enriched_obs.empty:
        return pd.DataFrame()
    work = add_relative_value_fields(enriched_obs)
    rows: list[pd.DataFrame] = []
    group_cols = ["demand_shape_label", "observation_reason"]
    for col, bins, labels in [
        ("churn_probability_H", [0, 0.2, 0.5, 0.75, 0.9, 1.0], ["0-0.2", "0.2-0.5", "0.5-0.75", "0.75-0.9", "0.9-1.0"]),
        ("relative_value_at_risk_H", [-np.inf, 0, 1_000, 10_000, 100_000, np.inf], ["<=0", "0-1k", "1k-10k", "10k-100k", "100k+"]),
        ("relative_business_priority_score_H", [-np.inf, 0, 1_000, 10_000, 100_000, np.inf], ["<=0", "0-1k", "1k-10k", "10k-100k", "100k+"]),
    ]:
        if col not in work.columns:
            continue
        temp = work.copy()
        temp["metric"] = col
        temp["bucket"] = _bin_series(temp[col], bins, labels).astype(str)
        rows.append(
            temp.groupby(group_cols + ["metric", "bucket"], dropna=False)
            .size()
            .reset_index(name="row_count")
        )
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def m1_reference_summary(by_horizon: pd.DataFrame | None, entity: pd.DataFrame | None) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    if by_horizon is not None:
        rows.extend(
            [
                {"metric": "by_horizon_row_count", "value": len(by_horizon)},
                {"metric": "by_horizon_entity_count", "value": safe_nunique(by_horizon, ENTITY_COLS)},
                {"metric": "manufacturer_coverage_by_horizon", "value": by_horizon["manufacturer_code"].nunique() if "manufacturer_code" in by_horizon.columns else 0},
                {"metric": "business_priority_missing_by_horizon", "value": int(by_horizon.get("relative_business_priority_score_H", pd.Series(dtype=float)).isna().sum())},
                {"metric": "probability_missing_by_horizon", "value": int(by_horizon.get("churn_probability_H", pd.Series(dtype=float)).isna().sum())},
                {"metric": "value_missing_by_horizon", "value": int(by_horizon.get("relative_value_at_risk_H", pd.Series(dtype=float)).isna().sum())},
            ]
        )
        for reason, count in by_horizon.get("selection_reason", pd.Series(dtype=object)).fillna("__MISSING__").value_counts().items():
            rows.append({"metric": f"selection_reason:{reason}", "value": int(count)})
        for horizon, count in by_horizon.get("horizon", pd.Series(dtype=object)).value_counts().sort_index().items():
            rows.append({"metric": f"horizon:H{int(horizon)}", "value": int(count)})
    if entity is not None:
        rows.extend(
            [
                {"metric": "entity_level_row_count", "value": len(entity)},
                {"metric": "entity_level_unique_entity_cutoff", "value": safe_nunique(entity, ENTITY_CUTOFF_COLS)},
                {"metric": "entity_level_duplicate_entity_cutoff", "value": int(len(entity) - safe_nunique(entity, ENTITY_CUTOFF_COLS))},
                {"metric": "selected_horizons_multi_horizon_rows", "value": int(entity.get("selected_horizons", pd.Series(dtype=str)).fillna("").str.contains(",").sum())},
            ]
        )
        for horizon, count in entity.get("primary_horizon", pd.Series(dtype=object)).fillna("__MISSING__").value_counts().items():
            rows.append({"metric": f"primary_horizon:{horizon}", "value": int(count)})
    return pd.DataFrame(rows)


def m2_reference_summary(m1_one_shot: pd.DataFrame | None, enriched: pd.DataFrame | None, metrics: pd.DataFrame | None) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    if m1_one_shot is None:
        rows.append({"section": "m1_one_shot", "metric": "status", "value": "missing"})
    else:
        rows.extend(
            [
                {"section": "m1_one_shot", "metric": "row_count", "value": len(m1_one_shot)},
                {"section": "m1_one_shot", "metric": "unique_entity_count", "value": safe_nunique(m1_one_shot, ENTITY_COLS)},
                {"section": "m1_one_shot", "metric": "manufacturer_coverage", "value": m1_one_shot["manufacturer_code"].nunique() if "manufacturer_code" in m1_one_shot.columns else 0},
                {"section": "m1_one_shot", "metric": "drug_group_coverage", "value": m1_one_shot["drug_group"].nunique() if "drug_group" in m1_one_shot.columns else 0},
                {"section": "m1_one_shot", "metric": "contains_churn_probability", "value": any("churn_probability" in c for c in m1_one_shot.columns)},
            ]
        )
    if enriched is None:
        rows.append({"section": "m2_enriched", "metric": "status", "value": "missing"})
    else:
        rows.extend(
            [
                {"section": "m2_enriched", "metric": "row_count", "value": len(enriched)},
                {"section": "m2_enriched", "metric": "contains_churn_probability", "value": any("churn_probability" in c for c in enriched.columns)},
            ]
        )
        for horizon, count in enriched.get("horizon", pd.Series(dtype=object)).fillna("__MISSING__").value_counts().items():
            rows.append({"section": "m2_enriched", "metric": f"horizon:{horizon}", "value": int(count)})
        for policy, count in enriched.get("selected_attention_policy", pd.Series(dtype=object)).fillna("__MISSING__").value_counts().items():
            rows.append({"section": "m2_enriched", "metric": f"selected_attention_policy:{policy}", "value": int(count)})
    if metrics is None:
        rows.append({"section": "m2_metrics", "metric": "status", "value": "missing"})
    else:
        for _, row in metrics.iterrows():
            for metric in ["brier_score", "log_loss", "ece", "auc", "pr_auc"]:
                if metric in metrics.columns:
                    rows.append({"section": "m2_metrics", "metric": f"{row.get('horizon')}:{metric}", "value": row.get(metric)})
    return pd.DataFrame(rows)


def overlap_audit(
    recurring: pd.DataFrame | None,
    observation: pd.DataFrame | None,
    one_shot: pd.DataFrame | None,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    if recurring is not None and not recurring.empty:
        r = add_entity_key(normalize_month_column(recurring, "cutoff_month"))[["entity_key", "cutoff_month"]].drop_duplicates()
        r["in_recurring_business_priority"] = True
        frames.append(r)
    if observation is not None and not observation.empty:
        o = add_entity_key(normalize_month_column(observation, "cutoff_month"))[["entity_key", "cutoff_month"]].drop_duplicates()
        o["in_demand_shape_observation"] = True
        frames.append(o)
    if not frames:
        return pd.DataFrame()
    base = frames[0]
    for frame in frames[1:]:
        base = base.merge(frame, on=["entity_key", "cutoff_month"], how="outer")
    if one_shot is not None and not one_shot.empty:
        one_entities = set(add_entity_key(one_shot)["entity_key"])
        base["in_one_shot_attention"] = base["entity_key"].isin(one_entities)
    else:
        base["in_one_shot_attention"] = False
    for col in ["in_recurring_business_priority", "in_demand_shape_observation"]:
        if col not in base.columns:
            base[col] = False
        base[col] = base[col].where(base[col].notna(), False).astype(bool)
    base["in_one_shot_attention"] = base["in_one_shot_attention"].where(
        base["in_one_shot_attention"].notna(), False
    ).astype(bool)

    def bucket(row: pd.Series) -> str:
        if row["in_recurring_business_priority"]:
            return "recurring_business_priority"
        if row["in_demand_shape_observation"]:
            return "demand_shape_observation"
        if row["in_one_shot_attention"]:
            return "one_shot_attention"
        return "none"

    def suppressed(row: pd.Series) -> str:
        suppressed_sources = []
        if row["in_recurring_business_priority"]:
            if row["in_demand_shape_observation"]:
                suppressed_sources.append("demand_shape_observation")
            if row["in_one_shot_attention"]:
                suppressed_sources.append("one_shot_attention")
        elif row["in_demand_shape_observation"] and row["in_one_shot_attention"]:
            suppressed_sources.append("one_shot_attention")
        return ";".join(suppressed_sources)

    base["recommended_display_bucket"] = base.apply(bucket, axis=1)
    base["suppressed_display_sources"] = base.apply(suppressed, axis=1)
    return base.sort_values(["cutoff_month", "entity_key"]).reset_index(drop=True)


def choose_expansion_reasons(decomp: pd.DataFrame, latest: pd.DataFrame, by_reason: pd.DataFrame, history: pd.DataFrame) -> list[str]:
    metrics = dict(zip(decomp["metric"], decomp["value"])) if not decomp.empty else {}
    reasons = []
    if metrics.get("cutoff_month_count", 0) and metrics.get("cutoff_month_count", 0) > 1:
        reasons.append("A_multi_cutoff_expansion")
    if metrics.get("avg_horizons_per_entity_cutoff", 0) and metrics.get("avg_horizons_per_entity_cutoff", 0) > 1.2:
        reasons.append("B_multi_horizon_expansion")
    if metrics.get("entity_cutoff_horizon_with_multiple_reasons", 0) and metrics.get("entity_cutoff_horizon_with_multiple_reasons", 0) > 0:
        reasons.append("C_multiple_observation_reasons")
    if not by_reason.empty and by_reason["row_count"].max() / max(1, by_reason["row_count"].sum()) > 0.8:
        reasons.append("D_rule_concentrated_or_broad")
    if not history.empty:
        low_hist = history[history["demand_shape_label"].isin(["intermittent", "lumpy"])]
        if "share_purchase_count_lt_3" in low_hist.columns and low_hist["share_purchase_count_lt_3"].max(skipna=True) > 0.3:
            reasons.append("E_history_insufficient_possible")
    if not latest.empty:
        total_latest = latest[latest["horizon"].astype(str).eq("all")]
        if not total_latest.empty and float(total_latest["row_count"].iloc[0]) > 1000:
            reasons.append("F_latest_cutoff_still_large")
    if not reasons:
        reasons.append("G_no_major_expansion_issue_detected")
    return reasons
