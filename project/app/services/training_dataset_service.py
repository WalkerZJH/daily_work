from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from app.adapters.canonicalize import prepare_canonical_orders
from app.core.config import PROJECT_ROOT
from app.features.data_quality import training_quality_summary
from app.features.label_builder import build_churn_label, filter_effective_purchases
from app.features.unit_snapshot_builder import UnitSnapshotBuilder, UnitSnapshotBuilderConfig
from app.schemas.config import AppConfig
from app.schemas.training import TrainingDatasetBuildRequest, TrainingDatasetBuildResponse
from app.services.feature_service import FeatureService


class TrainingDatasetService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def build_dataset(self, request: TrainingDatasetBuildRequest) -> TrainingDatasetBuildResponse:
        bundle = FeatureService(self.config).load_dataset(request, request.train_end)
        orders = prepare_canonical_orders(bundle)
        dataset = self.build_from_orders(
            orders,
            train_start=request.train_start,
            train_end=request.train_end,
            horizon_days=request.horizon_days,
            freq=request.freq,
        )
        output_path = self._write_dataset(dataset, request.output_path)
        return self._response(dataset, request, output_path)

    def build_from_orders(
        self,
        orders: pd.DataFrame,
        *,
        train_start,
        train_end,
        horizon_days: int,
        freq: str = "M",
    ) -> pd.DataFrame:
        prepared = orders.copy()
        prepared["order_time"] = pd.to_datetime(prepared["order_time"], errors="coerce")
        prepared = prepared[prepared["order_time"].notna()]
        effective = filter_effective_purchases(prepared)
        if effective.empty:
            return pd.DataFrame()
        max_data_date = pd.Timestamp(effective["order_time"].max()).date()
        origins = _origin_dates(train_start, train_end, freq)
        builder = UnitSnapshotBuilder(UnitSnapshotBuilderConfig())
        rows: list[dict[str, Any]] = []
        for origin in origins:
            units = effective[effective["order_time"].dt.date <= origin][
                ["org_code", "product_line_code"]
            ].dropna().drop_duplicates()
            snapshots = builder.build_for_units(effective, units, origin)
            for _, snapshot in snapshots.iterrows():
                label, label_debug = build_churn_label(
                    effective,
                    org_code=str(snapshot["org_code"]),
                    product_line_code=str(snapshot["product_line_code"]),
                    origin_date=origin,
                    horizon_days=horizon_days,
                    max_data_date=max_data_date,
                )
                if label is None:
                    continue
                row = snapshot.to_dict()
                row["origin_date"] = origin
                row["label_churn_H"] = label
                row["label_debug"] = label_debug
                rows.append(row)
        return pd.DataFrame(rows)

    def _write_dataset(self, dataset: pd.DataFrame, output_path: str | None) -> str | None:
        if not output_path:
            return None
        path = Path(output_path)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() == ".parquet":
            dataset.to_parquet(path, index=False)
        else:
            dataset.to_csv(path, index=False)
        return str(path)

    @staticmethod
    def _response(
        dataset: pd.DataFrame,
        request: TrainingDatasetBuildRequest,
        output_path: str | None,
    ) -> TrainingDatasetBuildResponse:
        labels = dataset.get("label_churn_H", pd.Series(dtype=float)).dropna()
        positive = int((labels == 1).sum())
        negative = int((labels == 0).sum())
        warning_counter = Counter(training_quality_summary(dataset)["warnings"])
        return TrainingDatasetBuildResponse(
            sample_count=int(len(dataset)),
            positive_count=positive,
            negative_count=negative,
            positive_rate=float(positive / len(labels)) if len(labels) else None,
            train_start=request.train_start,
            train_end=request.train_end,
            horizon_days=request.horizon_days,
            freq=request.freq,
            output_path=output_path,
            warning_summary=dict(warning_counter),
            data_quality=training_quality_summary(dataset),
        )


def _origin_dates(train_start, train_end, freq: str) -> list:
    frequency = "MS" if freq == "M" else "W-MON"
    dates = pd.date_range(start=pd.Timestamp(train_start), end=pd.Timestamp(train_end), freq=frequency)
    return [ts.date() for ts in dates]
