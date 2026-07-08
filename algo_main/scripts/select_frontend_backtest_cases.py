"""Select temporary static frontend backtest proof cases from current v2 artifacts.

The display-name join in this script is only for early frontend validation.
Formal monthly display lookup tables should be produced by the model layer.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


HORIZON_MONTHS = {"H3": 3, "H6": 6, "H12": 12}
DEFAULT_REPORT_DATES = {"H3": "2024-10-31", "H6": "2024-10-31", "H12": "2025-01-31"}
HORIZON_LABELS = {"H3": "3月风险", "H6": "6月风险", "H12": "12月风险"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path("algo_main/data/entity_complete_v2_coverage_expansion"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("algo_main/reports/entity_complete_v2_coverage_expansion/24_frontend_static_backtest_cases"),
    )
    parser.add_argument("--report-date", default=None)
    parser.add_argument("--horizon", default=None, choices=sorted(HORIZON_MONTHS))
    parser.add_argument("--horizons", default="H3,H6,H12")
    parser.add_argument(
        "--horizon-report-date",
        action="append",
        default=[],
        help="Override one horizon report date, for example H12=2025-01-31.",
    )
    parser.add_argument("--min-probability", type=float, default=0.55)
    parser.add_argument("--top-n", type=int, default=8)
    return parser.parse_args()


def money(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"¥{float(value):,.0f}"


def percent(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value) * 100:.1f}%"


def iso(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def normalize_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def first_non_empty(values: pd.Series) -> str:
    for value in values:
        text = normalize_text(value)
        if text:
            return text
    return ""


def parse_horizons(args: argparse.Namespace) -> list[str]:
    if args.horizon:
        return [args.horizon]
    horizons = [item.strip().upper() for item in args.horizons.split(",") if item.strip()]
    unknown = sorted(set(horizons) - set(HORIZON_MONTHS))
    if unknown:
        raise ValueError(f"Unknown horizons: {', '.join(unknown)}")
    return horizons or ["H6"]


def parse_report_dates(args: argparse.Namespace, horizons: list[str]) -> dict[str, str]:
    report_dates = {horizon: DEFAULT_REPORT_DATES[horizon] for horizon in horizons}
    if args.report_date:
        report_dates = {horizon: args.report_date for horizon in horizons}
    for override in args.horizon_report_date:
        if "=" not in override:
            raise ValueError("--horizon-report-date must use H6=YYYY-MM-DD format")
        horizon, report_date = override.split("=", 1)
        horizon = horizon.strip().upper()
        if horizon not in HORIZON_MONTHS:
            raise ValueError(f"Unknown horizon override: {horizon}")
        report_dates[horizon] = report_date.strip()
    return report_dates


def build_drug_display_name(row: pd.Series) -> str:
    drug_name = normalize_text(row.get("drug_name"))
    product_name = normalize_text(row.get("product_name"))
    if drug_name and product_name and product_name != drug_name:
        return f"{drug_name}（{product_name}）"
    return drug_name or product_name


def load_entity_names(data_root: Path) -> pd.DataFrame:
    columns = [
        "manufacturer_code",
        "manufacturer_name",
        "hospital_code",
        "hospital_name",
        "drug_code",
        "drug_name",
        "product_name",
    ]
    names = pd.read_parquet(data_root / "03_cleaned/bs_agent_dingdan_clean.parquet", columns=columns)
    names = names.rename(columns={"drug_code": "drug_group"})
    keys = ["manufacturer_code", "hospital_code", "drug_group"]
    for column in keys + ["manufacturer_name", "hospital_name", "drug_name", "product_name"]:
        names[column] = names[column].map(normalize_text)
    names = (
        names.groupby(keys, as_index=False)
        .agg(
            manufacturer_name=("manufacturer_name", first_non_empty),
            hospital_name=("hospital_name", first_non_empty),
            drug_name=("drug_name", first_non_empty),
            product_name=("product_name", first_non_empty),
        )
        .copy()
    )
    names["drug_display_name"] = names.apply(build_drug_display_name, axis=1)
    return names


def load_predictions(data_root: Path, horizons: list[str]) -> pd.DataFrame:
    value_cols = [f"value_at_risk_amount_nonnegative_{horizon}_asof_cutoff" for horizon in horizons]
    prediction_cols = [
        "manufacturer_code",
        "hospital_code",
        "drug_group",
        "cutoff_month",
        "horizon",
        "label_die_H",
        "label_alive_H",
        "label_window_closed",
        "split",
        "one_shot_flag",
        "history_sufficiency_flag",
        "demand_shape_label",
        "probability_score",
        "manufacturer_share_within_hospital_drug_asof_cutoff",
        *value_cols,
    ]
    predictions = pd.read_parquet(data_root / "06_predictions/selected_model_predictions.parquet", columns=prediction_cols)
    predictions["cutoff_month"] = pd.to_datetime(predictions["cutoff_month"])
    return predictions


def load_purchases(data_root: Path) -> pd.DataFrame:
    purchases = pd.read_parquet(
        data_root / "04_facts/fact_purchase_event.parquet",
        columns=[
            "manufacturer_code",
            "hospital_code",
            "drug_group",
            "purchase_time",
            "raw_sensitive_purchase_amount",
            "raw_sensitive_purchase_quantity",
        ],
    )
    purchases["purchase_time"] = pd.to_datetime(purchases["purchase_time"])
    return purchases


def select_cases(
    args: argparse.Namespace,
    predictions: pd.DataFrame,
    purchases: pd.DataFrame,
    entity_names: pd.DataFrame,
    horizon: str,
    report_date_value: str,
) -> pd.DataFrame:
    report_date = pd.Timestamp(report_date_value)
    horizon_end = report_date + pd.DateOffset(months=HORIZON_MONTHS[horizon])
    value_col = f"value_at_risk_amount_nonnegative_{horizon}_asof_cutoff"

    candidates = predictions[
        predictions["cutoff_month"].eq(report_date)
        & predictions["horizon"].eq(horizon)
        & predictions["label_window_closed"].astype(bool)
        & predictions["label_die_H"].eq(1)
        & ~predictions["one_shot_flag"].fillna(False).astype(bool)
        & predictions["probability_score"].ge(args.min_probability)
    ].copy()
    candidates["window_consumption_amount"] = candidates[value_col].fillna(0)
    candidates["business_score"] = candidates["probability_score"] * candidates["window_consumption_amount"]
    candidates = candidates.sort_values(["business_score", "probability_score"], ascending=False).head(args.top_n)
    candidates = candidates.merge(
        entity_names,
        on=["manufacturer_code", "hospital_code", "drug_group"],
        how="left",
    )

    rows: list[dict[str, Any]] = []
    for row in candidates.itertuples(index=False):
        entity_mask = (
            purchases["manufacturer_code"].eq(row.manufacturer_code)
            & purchases["hospital_code"].eq(row.hospital_code)
            & purchases["drug_group"].eq(row.drug_group)
        )
        entity_purchases = purchases[entity_mask].sort_values("purchase_time")
        before = entity_purchases[entity_purchases["purchase_time"].le(report_date)]
        after = entity_purchases[entity_purchases["purchase_time"].gt(report_date)]
        validation_window = after[after["purchase_time"].le(horizon_end)]
        last_purchase = before["purchase_time"].max() if not before.empty else pd.NaT
        next_purchase = after["purchase_time"].min() if not after.empty else pd.NaT
        amount_12m = before[before["purchase_time"].gt(report_date - pd.DateOffset(months=12))][
            "raw_sensitive_purchase_amount"
        ].sum()

        hospital_name = normalize_text(getattr(row, "hospital_name", "")) or row.hospital_code
        drug_display_name = normalize_text(getattr(row, "drug_display_name", "")) or row.drug_group

        rows.append(
            {
                "case_id": f"{row.manufacturer_code}|{row.hospital_code}|{row.drug_group}|{horizon}",
                "manufacturer_code": row.manufacturer_code,
                "manufacturer_name": normalize_text(getattr(row, "manufacturer_name", "")),
                "hospital_code": row.hospital_code,
                "hospital_name": hospital_name,
                "drug_group": row.drug_group,
                "drug_name": normalize_text(getattr(row, "drug_name", "")),
                "product_name": normalize_text(getattr(row, "product_name", "")),
                "drug_display_name": drug_display_name,
                "display_title": f"{hospital_name} × {drug_display_name}",
                "report_date": iso(report_date),
                "report_month": report_date.strftime("%Y-%m"),
                "horizon": horizon,
                "horizon_label": HORIZON_LABELS[horizon],
                "validation_end_date": iso(horizon_end),
                "risk_probability": round(float(row.probability_score), 6),
                "risk_probability_display": percent(row.probability_score),
                "window_consumption_amount": round(float(row.window_consumption_amount), 2),
                "window_consumption_display": money(row.window_consumption_amount),
                "business_score": round(float(row.business_score), 2),
                "business_score_display": money(row.business_score),
                "last_purchase_date_before_report": iso(last_purchase),
                "days_since_last_purchase_at_report": int((report_date - last_purchase).days) if not pd.isna(last_purchase) else None,
                "next_purchase_after_report": iso(next_purchase),
                "validation_window_purchase_count": int(len(validation_window)),
                "days_without_purchase_from_report_to_validation": int((horizon_end - report_date).days),
                "days_without_purchase_from_last_to_validation": int((horizon_end - last_purchase).days)
                if not pd.isna(last_purchase)
                else None,
                "observed_amount_last_12m_asof_report": round(float(amount_12m), 2),
                "observed_amount_last_12m_display": money(amount_12m),
                "history_sufficiency": row.history_sufficiency_flag,
                "demand_shape": row.demand_shape_label,
                "manufacturer_share": round(float(row.manufacturer_share_within_hospital_drug_asof_cutoff), 4)
                if not pd.isna(row.manufacturer_share_within_hospital_drug_asof_cutoff)
                else None,
                "outcome": "hit" if len(validation_window) == 0 else "miss",
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    args = parse_args()
    horizons = parse_horizons(args)
    report_dates = parse_report_dates(args, horizons)
    predictions = load_predictions(args.data_root, horizons)
    purchases = load_purchases(args.data_root)
    entity_names = load_entity_names(args.data_root)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    horizon_outputs: dict[str, pd.DataFrame] = {}
    payload: dict[str, Any] = {"horizons": {}}
    for horizon in horizons:
        output = select_cases(args, predictions, purchases, entity_names, horizon, report_dates[horizon])
        horizon_outputs[horizon] = output
        csv_path = args.output_dir / f"frontend_static_backtest_cases_{horizon.lower()}.csv"
        output.to_csv(csv_path, index=False, encoding="utf-8-sig")
        payload["horizons"][horizon] = {
            "report_date": report_dates[horizon],
            "horizon": horizon,
            "horizon_label": HORIZON_LABELS[horizon],
            "case_count": int(len(output)),
            "cases": output.to_dict(orient="records"),
        }
        print(f"wrote {csv_path}")

    default_horizon = "H6" if "H6" in horizon_outputs else horizons[0]
    output = horizon_outputs[default_horizon]
    csv_path = args.output_dir / "frontend_static_backtest_cases.csv"
    json_path = args.output_dir / "frontend_static_backtest_cases.json"
    grouped_json_path = args.output_dir / "frontend_static_backtest_cases_by_horizon.json"
    output.to_csv(csv_path, index=False, encoding="utf-8-sig")
    json_path.write_text(
        json.dumps(
            {
                "report_date": report_dates[default_horizon],
                "horizon": default_horizon,
                "case_count": int(len(output)),
                "cases": output.to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    grouped_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {csv_path}")
    print(f"wrote {json_path}")
    print(f"wrote {grouped_json_path}")


if __name__ == "__main__":
    main()
