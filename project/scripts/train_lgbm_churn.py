from __future__ import annotations

import argparse
import json
import pickle
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

from app.core.config import PROJECT_ROOT
from app.ml.feature_schema import FEATURE_SCHEMA_VERSION, MODEL_FEATURE_COLUMNS


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/palive_training.yaml")
    parser.add_argument("--input", required=True)
    parser.add_argument("--k", type=int, default=20)
    args = parser.parse_args()

    config_path = _resolve(args.config)
    input_path = _resolve(args.input)
    with config_path.open("r", encoding="utf-8") as file:
        cfg = yaml.safe_load(file) or {}
    data = _read_dataset(input_path)
    if data.empty:
        raise SystemExit("训练数据为空。")
    if "label_churn_H" not in data.columns:
        raise SystemExit("训练数据缺少 label_churn_H。")
    data["origin_date"] = pd.to_datetime(data["origin_date"], errors="coerce")
    data = data[data["origin_date"].notna()].sort_values("origin_date")
    train, valid = _time_split(data)
    if train["label_churn_H"].nunique() < 2:
        raise SystemExit("训练集只有单一类别，无法训练分类模型。")

    feature_columns = [column for column in MODEL_FEATURE_COLUMNS if column in data.columns]
    x_train = pd.get_dummies(train[feature_columns], dummy_na=True)
    x_valid = pd.get_dummies(valid[feature_columns], dummy_na=True)
    x_valid = x_valid.reindex(columns=x_train.columns, fill_value=0)
    y_train = train["label_churn_H"].astype(int)
    y_valid = valid["label_churn_H"].astype(int)

    model, model_type = _fit_model(x_train, y_train)
    p_churn = _predict_churn(model, x_valid)
    metrics = _metrics(y_valid, p_churn, args.k)

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    output_dir = PROJECT_ROOT / "artifacts" / "models" / "palive_lgbm" / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "model.pkl").open("wb") as file:
        pickle.dump(model, file)
    _write_json(
        output_dir / "feature_schema.json",
        {
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "feature_columns": feature_columns,
            "encoded_feature_columns": list(x_train.columns),
        },
    )
    _write_json(output_dir / "metrics.json", metrics)
    model_card = {
        "model_name": "palive_lgbm",
        "model_version": timestamp,
        "analysis_unit": cfg.get("analysis_unit", "org_code_product_line"),
        "label_definition": "label_churn_H=1 表示 origin_date 后 horizon_days 天内没有有效采购",
        "horizon_days": cfg.get("horizon_days", 90),
        "train_start": str(train["origin_date"].min().date()),
        "train_end": str(train["origin_date"].max().date()),
        "validation_start": str(valid["origin_date"].min().date()),
        "validation_end": str(valid["origin_date"].max().date()),
        "model_type": model_type,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "limitations": ["experimental", "not production-calibrated probability"],
    }
    _write_json(output_dir / "model_card.json", model_card)
    with (output_dir / "training_config.yaml").open("w", encoding="utf-8") as file:
        yaml.safe_dump(cfg, file, allow_unicode=True, sort_keys=False)
    print(str(output_dir))


def _fit_model(x_train: pd.DataFrame, y_train: pd.Series):
    try:
        from lightgbm import LGBMClassifier

        model = LGBMClassifier(n_estimators=100, learning_rate=0.05, random_state=42)
        model.fit(x_train, y_train)
        return model, "lightgbm.LGBMClassifier"
    except Exception:
        from sklearn.ensemble import HistGradientBoostingClassifier

        model = HistGradientBoostingClassifier(random_state=42)
        model.fit(x_train, y_train)
        return model, "sklearn.HistGradientBoostingClassifier"


def _predict_churn(model, x_valid: pd.DataFrame):
    if hasattr(model, "predict_proba"):
        return model.predict_proba(x_valid)[:, 1]
    return model.predict(x_valid)


def _metrics(y_true: pd.Series, p_churn, k: int) -> dict:
    from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

    metrics = {
        "brier_score": float(brier_score_loss(y_true, p_churn)),
        "calibration_bins": _calibration_bins(y_true, p_churn),
    }
    metrics["roc_auc"] = float(roc_auc_score(y_true, p_churn)) if y_true.nunique() > 1 else None
    metrics["pr_auc"] = float(average_precision_score(y_true, p_churn)) if y_true.nunique() > 1 else None
    ranked = pd.DataFrame({"y": y_true.to_numpy(), "p": p_churn}).sort_values("p", ascending=False)
    top = ranked.head(max(1, min(k, len(ranked))))
    metrics["precision_at_k"] = float(top["y"].mean())
    positives = ranked["y"].sum()
    metrics["recall_at_k"] = float(top["y"].sum() / positives) if positives else None
    return metrics


def _calibration_bins(y_true: pd.Series, p_churn) -> list[dict]:
    frame = pd.DataFrame({"y": y_true.to_numpy(), "p": p_churn})
    frame["bin"] = pd.cut(frame["p"], bins=[0, 0.2, 0.4, 0.6, 0.8, 1], include_lowest=True)
    out = []
    for key, group in frame.groupby("bin", observed=False):
        out.append(
            {
                "bin": str(key),
                "count": int(len(group)),
                "mean_pred": float(group["p"].mean()) if len(group) else None,
                "event_rate": float(group["y"].mean()) if len(group) else None,
            }
        )
    return out


def _read_dataset(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def _resolve(path: str) -> Path:
    selected = Path(path)
    return selected if selected.is_absolute() else PROJECT_ROOT / selected


def _write_json(path: Path, payload: dict | list) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def _time_split(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = sorted(data["origin_date"].dropna().unique())
    split_idx = max(1, int(len(dates) * 0.8))
    split_date = dates[min(split_idx, len(dates) - 1)]
    train = data[data["origin_date"] < split_date]
    valid = data[data["origin_date"] >= split_date]
    if train.empty or valid.empty:
        midpoint = max(1, int(len(data) * 0.8))
        return data.iloc[:midpoint], data.iloc[midpoint:]
    return train, valid


if __name__ == "__main__":
    main()
