#!/usr/bin/env python
"""Run M2 one-shot repeat propensity prototype.

The script reads existing facts and the M1 one-shot attention table, trains
temporary in-memory regularized logistic regression models, and writes only
prototype/report outputs under reports/alive_prediction_one_shot_repeat_v1/.
It does not persist models or full prediction artifacts.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[0]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from alg.tasks.die_prediction.one_shot_repeat import (
    HORIZONS,
    OneShotRepeatConfig,
    add_group_prior_features,
    build_attention_scores,
    build_first_purchase_samples,
    build_group_prior_report,
    build_static_explanations,
    closed_horizon_samples,
    compute_ece,
    empty_similarity_group_report,
    make_long_enriched_output,
    model_feature_columns,
    temporal_train_test_split,
)

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


FACT_PATH = ROOT / "data/04_facts/alive_prediction/fact_purchase_event__drug_code.parquet"
M1_ONE_SHOT_PATH = ROOT / "reports/alive_prediction_candidate_pool_v1/one_shot_attention_candidates.csv"
OUTPUT_DIR = ROOT / "reports/alive_prediction_one_shot_repeat_v1"
CONFIG = OneShotRepeatConfig()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def markdown_table(df: pd.DataFrame, *, max_rows: int = 20) -> str:
    if df.empty:
        return "_No rows._"
    return df.head(max_rows).to_markdown(index=False)


def one_hot_encoder() -> OneHotEncoder:
    try:
        return OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:
        return OneHotEncoder(handle_unknown="ignore", sparse=False)


def fit_logistic_model(train: pd.DataFrame, *, horizon: int) -> tuple[Pipeline | None, str, list[str], list[str]]:
    label_col = f"label_repeat_H{horizon}"
    numeric_cols, categorical_cols = model_feature_columns(train, horizon)
    if train.empty:
        return None, "empty_train", numeric_cols, categorical_cols
    if train[label_col].nunique(dropna=True) < 2:
        return None, "single_class_train", numeric_cols, categorical_cols
    transformers = []
    if numeric_cols:
        transformers.append(
            (
                "num",
                Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]),
                numeric_cols,
            )
        )
    if categorical_cols:
        transformers.append(
            (
                "cat",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", one_hot_encoder()),
                    ]
                ),
                categorical_cols,
            )
        )
    if not transformers:
        return None, "no_usable_features", numeric_cols, categorical_cols
    model = Pipeline(
        [
            ("preprocess", ColumnTransformer(transformers=transformers, remainder="drop")),
            ("model", LogisticRegression(max_iter=500, solver="lbfgs", class_weight="balanced")),
        ]
    )
    model.fit(train[numeric_cols + categorical_cols], train[label_col].astype(int))
    return model, "", numeric_cols, categorical_cols


def predict_with_fallback(
    model: Pipeline | None,
    frame: pd.DataFrame,
    *,
    horizon: int,
    numeric_cols: list[str],
    categorical_cols: list[str],
) -> np.ndarray:
    fallback_col = f"global_repeat_prior_H{horizon}"
    fallback = pd.to_numeric(frame.get(fallback_col, pd.Series(0.5, index=frame.index)), errors="coerce").fillna(0.5)
    if model is None:
        return fallback.to_numpy(dtype=float)
    try:
        return np.clip(model.predict_proba(frame[numeric_cols + categorical_cols])[:, 1], 0.0, 1.0)
    except Exception:
        return fallback.to_numpy(dtype=float)


def metric_row(
    train: pd.DataFrame,
    test: pd.DataFrame,
    y_prob: np.ndarray,
    *,
    horizon: int,
    fallback_used: bool,
    skip_reason: str,
) -> dict[str, Any]:
    label_col = f"label_repeat_H{horizon}"
    y = test[label_col].astype(int).to_numpy() if label_col in test.columns and not test.empty else np.array([])
    row: dict[str, Any] = {
        "horizon": f"H{horizon}",
        "train_row_count": int(len(train)),
        "test_row_count": int(len(test)),
        "positive_rate_train": float(train[label_col].mean()) if len(train) else np.nan,
        "positive_rate_test": float(test[label_col].mean()) if len(test) else np.nan,
        "brier_score": np.nan,
        "log_loss": np.nan,
        "ece": np.nan,
        "auc": np.nan,
        "pr_auc": np.nan,
        "fallback_used": bool(fallback_used),
        "skip_reason": skip_reason,
    }
    if len(test) == 0:
        row["skip_reason"] = "empty_test"
        return row
    y_prob = np.clip(np.asarray(y_prob, dtype=float), 1e-15, 1 - 1e-15)
    row["brier_score"] = float(brier_score_loss(y, y_prob))
    row["log_loss"] = float(log_loss(y, y_prob, labels=[0, 1]))
    row["ece"] = compute_ece(y, y_prob)
    if len(np.unique(y)) > 1:
        row["auc"] = float(roc_auc_score(y, y_prob))
        row["pr_auc"] = float(average_precision_score(y, y_prob))
    else:
        row["skip_reason"] = "single_class_test_metric_partial"
    return row


def normalize_first_purchase_month(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "first_purchase_month" in out.columns:
        out["first_purchase_month"] = pd.to_datetime(out["first_purchase_month"], errors="coerce").dt.to_period("M").astype(str)
    return out


def candidate_feature_frame(candidates: pd.DataFrame, samples: pd.DataFrame) -> pd.DataFrame:
    candidates = normalize_first_purchase_month(candidates)
    samples = normalize_first_purchase_month(samples)
    feature_cols = [
        "manufacturer_code",
        "hospital_code",
        "drug_group",
        "drug_group_source",
        "first_purchase_month",
        "first_purchase_quantity",
        "first_purchase_amount",
        "delivery_rate",
        "arrival_rate",
        "overall_arrival_rate",
        "return_quantity",
        "hospital_level_code",
        "ownership_type_code",
        "province_code",
        "city_code",
        "county_code",
        "drug_category_code",
        "order_phase_code",
        "delivery_state_code",
        "order_terminal_flag",
        "order_failure_flag",
    ]
    existing = [c for c in feature_cols if c in samples.columns]
    merged = candidates.merge(
        samples[existing].drop_duplicates(["manufacturer_code", "hospital_code", "drug_group"]),
        on=["manufacturer_code", "hospital_code", "drug_group"],
        how="left",
        suffixes=("", "_sample"),
    )
    if "drug_group_source_sample" in merged.columns:
        merged["drug_group_source"] = merged["drug_group_source"].fillna(merged["drug_group_source_sample"])
        merged = merged.drop(columns=["drug_group_source_sample"])
    if "one_shot_value_score" not in merged.columns:
        if "first_purchase_amount" in merged.columns:
            merged["one_shot_value_score"] = pd.to_numeric(merged["first_purchase_amount"], errors="coerce")
        elif "first_purchase_quantity" in merged.columns:
            merged["one_shot_value_score"] = pd.to_numeric(merged["first_purchase_quantity"], errors="coerce")
        else:
            merged["one_shot_value_score"] = 1.0
    merged["one_shot_value_score"] = pd.to_numeric(merged["one_shot_value_score"], errors="coerce").fillna(1.0)
    return merged


def enrich_candidates_for_horizon(
    candidates: pd.DataFrame,
    model: Pipeline | None,
    reference: pd.DataFrame,
    *,
    horizon: int,
    numeric_cols: list[str],
    categorical_cols: list[str],
    fallback_used: bool,
) -> pd.DataFrame:
    scored = add_group_prior_features(candidates, reference, horizon=horizon, prior_strength=CONFIG.prior_strength)
    probs = predict_with_fallback(model, scored, horizon=horizon, numeric_cols=numeric_cols, categorical_cols=categorical_cols)
    scored["horizon"] = f"H{horizon}"
    scored[f"repeat_probability_H{horizon}"] = np.clip(probs, 0.0, 1.0)
    scored[f"one_shot_non_repeat_risk_H{horizon}"] = 1.0 - scored[f"repeat_probability_H{horizon}"]
    scored = build_attention_scores(
        scored,
        horizon=horizon,
        value_col="one_shot_value_score",
        selected_attention_policy=CONFIG.selected_attention_policy,
    )
    scored["repeat_probability_interpretation"] = "probability_of_second_purchase_within_H_after_first_purchase"
    scored["probability_available"] = True
    scored["probability_interpretation"] = "first_purchase_repeat_probability_not_recurring_churn_probability"
    scored["model_confidence"] = np.where(fallback_used, "low_fallback_prior", "prototype_logistic")
    scored["manual_review_required"] = True
    scored["similarity_group_id"] = ""
    scored["similarity_group_explanation"] = "similarity_group_explanation_deferred_group_prior_used"
    scored["similar_group_repeat_rate_H"] = np.nan
    scored["similar_group_sample_count"] = 0
    prior_col = f"global_repeat_prior_H{horizon}"
    scored["group_prior_explanation"] = (
        "global/group repeat prior from pre-test training window; global_prior="
        + pd.to_numeric(scored.get(prior_col, pd.Series(np.nan, index=scored.index)), errors="coerce").round(4).astype(str)
    )
    scored["top_explanation_factors"] = "group_prior;first_purchase_strength;fulfillment_status"
    return scored


def training_summary_row(samples_h: pd.DataFrame, train: pd.DataFrame, test: pd.DataFrame, *, horizon: int, skip_reason: str) -> dict[str, Any]:
    return {
        "horizon": f"H{horizon}",
        "closed_sample_count": int(len(samples_h)),
        "train_row_count": int(len(train)),
        "test_row_count": int(len(test)),
        "train_period_start": train["first_purchase_month"].min() if not train.empty else "",
        "train_period_end": train["first_purchase_month"].max() if not train.empty else "",
        "test_period_start": test["first_purchase_month"].min() if not test.empty else "",
        "test_period_end": test["first_purchase_month"].max() if not test.empty else "",
        "positive_rate_train": float(train[f"label_repeat_H{horizon}"].mean()) if not train.empty else np.nan,
        "positive_rate_test": float(test[f"label_repeat_H{horizon}"].mean()) if not test.empty else np.nan,
        "skip_reason": skip_reason,
    }


def leakage_audit_text() -> str:
    return "\n".join(
        [
            "# One-Shot Repeat Leakage Audit",
            "",
            "This report is for the M2 prototype. It is not a recurring churn model.",
            "",
            "## Checks",
            "- First-purchase samples are indexed by manufacturer_code, hospital_code, drug_group, and first_purchase_month.",
            "- Labels use only the second purchase inside the closed H window after first_purchase_time.",
            "- Samples whose first_purchase_time + H exceeds the maximum observable purchase_time are excluded for that H.",
            "- Logistic models are trained with temporal split, not random split.",
            "- Group priors used for model/evaluation/scoring are built from the training reference window only.",
            "- No future value, future recurring status, future order count, or full-history target encoding is used.",
            "- No 2024/test-period calibrator or transformer is fitted.",
            "- value fields are treated as relative purchase amount/value only.",
            "- No value_at_risk or business_priority_score is used as model input.",
            "- Output uses repeat_probability_H and one_shot_non_repeat_risk_H, not churn_probability_H.",
        ]
    )


def data_quality_text(
    *,
    events: pd.DataFrame,
    samples: pd.DataFrame,
    candidates: pd.DataFrame,
    enriched: pd.DataFrame,
    missing_candidate_features: int,
    value_fallback_count: int,
    metrics: pd.DataFrame,
) -> str:
    return "\n".join(
        [
            "# One-Shot Repeat Data Quality Report",
            "",
            "All outputs are prototype/report outputs. No model file or formal prediction artifact is saved.",
            "",
            "## Input Counts",
            f"- purchase event rows: {len(events)}",
            f"- first-purchase samples: {len(samples)}",
            f"- M1 one-shot candidates: {len(candidates)}",
            f"- enriched candidate rows: {len(enriched)}",
            "",
            "## Degradation Notes",
            f"- candidate rows without joined first-purchase features: {missing_candidate_features}",
            f"- one_shot_value_score fallback rows: {value_fallback_count}",
            "- first purchase amount fields are interpreted as relative amount/value if desensitized.",
            "- KMeans similarity explanation is deferred in v1; group prior explanation is used.",
            "",
            "## Metric Availability",
            markdown_table(metrics),
        ]
    )


def synthetic_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    events = pd.DataFrame(
        [
            {
                "manufacturer_code": "m1",
                "hospital_code": "h1",
                "drug_code": "d1",
                "drug_group": "d1",
                "drug_group_source": "drug_code",
                "drug_category_code": "c1",
                "province_code": "p1",
                "city_code": "city1",
                "county_code": "county1",
                "hospital_level_code": "L1",
                "ownership_type_code": "O1",
                "purchase_time": "2020-01-15",
                "purchase_month": "2020-01-31",
                "raw_sensitive_purchase_quantity": 10.0,
                "raw_sensitive_purchase_amount": 100.0,
                "raw_sensitive_delivery_quantity": 10.0,
                "raw_sensitive_arrival_quantity": 10.0,
                "order_phase_code": "ok",
                "delivery_state_code": "arrived",
                "order_failure_flag": 0,
                "order_terminal_flag": 1,
            },
            {
                "manufacturer_code": "m1",
                "hospital_code": "h1",
                "drug_code": "d1",
                "drug_group": "d1",
                "drug_group_source": "drug_code",
                "drug_category_code": "c1",
                "province_code": "p1",
                "city_code": "city1",
                "county_code": "county1",
                "hospital_level_code": "L1",
                "ownership_type_code": "O1",
                "purchase_time": "2020-03-01",
                "purchase_month": "2020-03-31",
                "raw_sensitive_purchase_quantity": 5.0,
                "raw_sensitive_purchase_amount": 50.0,
                "raw_sensitive_delivery_quantity": 5.0,
                "raw_sensitive_arrival_quantity": 5.0,
                "order_phase_code": "ok",
                "delivery_state_code": "arrived",
                "order_failure_flag": 0,
                "order_terminal_flag": 1,
            },
            {
                "manufacturer_code": "m2",
                "hospital_code": "h2",
                "drug_code": "d2",
                "drug_group": "d2",
                "drug_group_source": "drug_code",
                "drug_category_code": "c2",
                "province_code": "p2",
                "city_code": "city2",
                "county_code": "county2",
                "hospital_level_code": "L2",
                "ownership_type_code": "O2",
                "purchase_time": "2023-02-10",
                "purchase_month": "2023-02-28",
                "raw_sensitive_purchase_quantity": 3.0,
                "raw_sensitive_purchase_amount": 300.0,
                "raw_sensitive_delivery_quantity": 3.0,
                "raw_sensitive_arrival_quantity": 2.0,
                "order_phase_code": "ok",
                "delivery_state_code": "partial",
                "order_failure_flag": 0,
                "order_terminal_flag": 1,
            },
            {
                "manufacturer_code": "m3",
                "hospital_code": "h3",
                "drug_code": "d3",
                "drug_group": "d3",
                "drug_group_source": "drug_code",
                "drug_category_code": "c1",
                "province_code": "p1",
                "city_code": "city1",
                "county_code": "county1",
                "hospital_level_code": "L1",
                "ownership_type_code": "O1",
                "purchase_time": "2023-04-01",
                "purchase_month": "2023-04-30",
                "raw_sensitive_purchase_quantity": 4.0,
                "raw_sensitive_purchase_amount": 400.0,
                "raw_sensitive_delivery_quantity": 4.0,
                "raw_sensitive_arrival_quantity": 4.0,
                "order_phase_code": "ok",
                "delivery_state_code": "arrived",
                "order_failure_flag": 0,
                "order_terminal_flag": 1,
            },
            {
                "manufacturer_code": "m3",
                "hospital_code": "h3",
                "drug_code": "d3",
                "drug_group": "d3",
                "drug_group_source": "drug_code",
                "drug_category_code": "c1",
                "province_code": "p1",
                "city_code": "city1",
                "county_code": "county1",
                "hospital_level_code": "L1",
                "ownership_type_code": "O1",
                "purchase_time": "2023-10-01",
                "purchase_month": "2023-10-31",
                "raw_sensitive_purchase_quantity": 4.0,
                "raw_sensitive_purchase_amount": 400.0,
                "raw_sensitive_delivery_quantity": 4.0,
                "raw_sensitive_arrival_quantity": 4.0,
                "order_phase_code": "ok",
                "delivery_state_code": "arrived",
                "order_failure_flag": 0,
                "order_terminal_flag": 1,
            },
            {
                "manufacturer_code": "m4",
                "hospital_code": "h4",
                "drug_code": "d4",
                "drug_group": "d4",
                "drug_group_source": "drug_code",
                "drug_category_code": "c2",
                "province_code": "p2",
                "city_code": "city2",
                "county_code": "county2",
                "hospital_level_code": "L2",
                "ownership_type_code": "O2",
                "purchase_time": "2025-12-01",
                "purchase_month": "2025-12-31",
                "raw_sensitive_purchase_quantity": 1.0,
                "raw_sensitive_purchase_amount": 10.0,
                "raw_sensitive_delivery_quantity": 1.0,
                "raw_sensitive_arrival_quantity": 1.0,
                "order_phase_code": "ok",
                "delivery_state_code": "arrived",
                "order_failure_flag": 0,
                "order_terminal_flag": 1,
            },
        ]
    )
    candidates = pd.DataFrame(
        [
            {
                "manufacturer_code": "m1",
                "hospital_code": "h1",
                "drug_group": "d1",
                "drug_group_source": "drug_code",
                "first_purchase_month": "2020-01",
                "one_shot_value_score": 100.0,
                "attention_reason": "dry_run",
                "probability_available": False,
                "probability_interpretation": "not_recurring_churn_probability",
            },
            {
                "manufacturer_code": "m2",
                "hospital_code": "h2",
                "drug_group": "d2",
                "drug_group_source": "drug_code",
                "first_purchase_month": "2023-02",
                "one_shot_value_score": 300.0,
                "attention_reason": "dry_run",
                "probability_available": False,
                "probability_interpretation": "not_recurring_churn_probability",
            },
        ]
    )
    return events, candidates


def summary_text(
    *,
    samples: pd.DataFrame,
    metrics: pd.DataFrame,
    enriched: pd.DataFrame,
    explanations: pd.DataFrame,
) -> str:
    trained = metrics.assign(status=np.where(metrics["fallback_used"].astype(bool), "fallback", "trained"))
    return "\n".join(
        [
            "# One-Shot Repeat v1 Summary",
            "",
            "This is the M2 one-shot repeat propensity prototype. It does not implement M3/M4/M5/M6/M7, does not generate line cards, and does not call an LLM.",
            "",
            "## Contract",
            "- `repeat_probability_H = P(second_purchase_within_H | first_purchase_context)`.",
            "- `one_shot_non_repeat_risk_H = 1 - repeat_probability_H`.",
            "- `one_shot_non_repeat_risk_H` is not recurring `churn_probability_H`.",
            "- one-shot rows do not enter `recurring_business_priority_candidates`.",
            "- one-shot rows do not enter the recurring survival-lite main flow.",
            "",
            "## Output Status",
            f"1. first-purchase training samples built: {str(not samples.empty).lower()} rows={len(samples)}",
            "2. H3/H6/H12 train/fallback status:",
            markdown_table(trained[["horizon", "train_row_count", "test_row_count", "fallback_used", "skip_reason", "status"]]),
            f"3. repeat_probability_H generated: {str(not enriched.empty).lower()} rows={len(enriched)}",
            f"4. one_shot_non_repeat_risk_H generated: {str(not enriched.empty).lower()}",
            "5. three attention scores generated: retention_risk, conversion_opportunity, balanced_attention",
            f"6. selected_attention_policy: {CONFIG.selected_attention_policy}",
            f"7. explanation output generated: {str(not explanations.empty).lower()} rows={len(explanations)}",
            "8. KMeans similarity explanation: deferred; group prior explanation used in v1.",
            "9. recurring churn interpretation avoided: true.",
            "10. formal model file saved: false.",
            "11. recurring main table modified: false.",
            "",
            "## Next Step",
            "M2 output can feed a later structured evidence bundle or M4 new-terminal detection. The next algorithm prototype may be M3 survival-lite, but this run did not implement it.",
        ]
    )


def run(
    *,
    output_dir: Path = OUTPUT_DIR,
    fact_path: Path = FACT_PATH,
    m1_one_shot_path: Path = M1_ONE_SHOT_PATH,
    dry_run: bool = False,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    if dry_run:
        events, candidates = synthetic_inputs()
    else:
        events = pd.read_parquet(fact_path)
        candidates = pd.read_csv(m1_one_shot_path)
    candidates = normalize_first_purchase_month(candidates)
    samples = build_first_purchase_samples(events, horizons=HORIZONS)
    candidate_features = candidate_feature_frame(candidates, samples)
    missing_candidate_features = int(candidate_features["first_purchase_amount"].isna().sum()) if "first_purchase_amount" in candidate_features.columns else len(candidate_features)
    value_fallback_count = int(candidates.get("one_shot_value_score", pd.Series(index=candidates.index, dtype=float)).isna().sum())

    metric_rows: list[dict[str, Any]] = []
    training_rows: list[dict[str, Any]] = []
    prior_reports: list[pd.DataFrame] = []
    enriched_parts: list[pd.DataFrame] = []

    for horizon in HORIZONS:
        samples_h = closed_horizon_samples(samples, horizon)
        train, test = temporal_train_test_split(samples_h, train_end_month=CONFIG.train_end_month)
        train_for_model = train.copy()
        test = add_group_prior_features(test, train, horizon=horizon, prior_strength=CONFIG.prior_strength)
        prior_reports.append(build_group_prior_report(train, horizon=horizon, prior_strength=CONFIG.prior_strength))

        model, skip_reason, numeric_cols, categorical_cols = fit_logistic_model(train_for_model, horizon=horizon)
        fallback_used = model is None
        y_prob = predict_with_fallback(model, test, horizon=horizon, numeric_cols=numeric_cols, categorical_cols=categorical_cols)
        metric_rows.append(
            metric_row(
                train,
                test,
                y_prob,
                horizon=horizon,
                fallback_used=fallback_used,
                skip_reason=skip_reason,
            )
        )
        training_rows.append(training_summary_row(samples_h, train, test, horizon=horizon, skip_reason=skip_reason))
        enriched_parts.append(
            enrich_candidates_for_horizon(
                candidate_features,
                model,
                train,
                horizon=horizon,
                numeric_cols=numeric_cols,
                categorical_cols=categorical_cols,
                fallback_used=fallback_used,
            )
        )

    metrics = pd.DataFrame(metric_rows)
    training_summary = pd.DataFrame(training_rows)
    group_prior_report = pd.concat(prior_reports, ignore_index=True) if prior_reports else pd.DataFrame()
    enriched = make_long_enriched_output(enriched_parts)
    explanations = build_static_explanations(enriched)
    similarity = empty_similarity_group_report()

    training_summary.to_csv(output_dir / "one_shot_repeat_training_summary.csv", index=False, encoding="utf-8-sig")
    metrics.to_csv(output_dir / "one_shot_repeat_metrics.csv", index=False, encoding="utf-8-sig")
    enriched.to_csv(output_dir / "one_shot_attention_candidates_enriched.csv", index=False, encoding="utf-8-sig")
    explanations.to_csv(output_dir / "one_shot_explanation_factors.csv", index=False, encoding="utf-8-sig")
    group_prior_report.to_csv(output_dir / "one_shot_group_prior_report.csv", index=False, encoding="utf-8-sig")
    similarity.to_csv(output_dir / "one_shot_similarity_group_report.csv", index=False, encoding="utf-8-sig")
    write_text(output_dir / "one_shot_leakage_audit.md", leakage_audit_text())
    write_text(
        output_dir / "one_shot_data_quality_report.md",
        data_quality_text(
            events=events,
            samples=samples,
            candidates=candidates,
            enriched=enriched,
            missing_candidate_features=missing_candidate_features,
            value_fallback_count=value_fallback_count,
            metrics=metrics,
        ),
    )
    write_text(
        output_dir / "one_shot_repeat_v1_summary.md",
        summary_text(samples=samples, metrics=metrics, enriched=enriched, explanations=explanations),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="run on a small synthetic fixture")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    run(output_dir=args.output_dir, dry_run=args.dry_run)
