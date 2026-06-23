from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd

from app.adapters.base import DatasetBundle
from app.adapters.csv_adapter import CSVSourceAdapter
from app.features.catalog import FeatureCatalog, build_default_feature_catalog
from app.features.lineage import FeatureLineageRecord
from app.features.snapshot import FeatureSnapshot
from app.features.store import FeatureStore
from app.preprocessors.base import PreprocessContext, unit_id
from app.preprocessors.orchestrator import PreprocessOrchestrator
from app.preprocessors.registry import build_default_preprocessor_registry
from app.schemas.api import DataSourceRequest
from app.schemas.config import AppConfig


@dataclass(frozen=True)
class FeatureRunResult:
    dataset_name: str
    as_of_date: date
    store: FeatureStore
    snapshots: list[FeatureSnapshot]
    lineage: list[FeatureLineageRecord]
    catalog: FeatureCatalog
    prepared_orders: pd.DataFrame
    bundle: DatasetBundle

    @property
    def enabled_preprocessors(self) -> list[str]:
        return [record.preprocessor_name for record in self.lineage]

    @property
    def feature_count(self) -> int:
        return sum(len(snapshot.features) for snapshot in self.snapshots)

    @property
    def warning_summary(self) -> dict[str, int]:
        counter: Counter[str] = Counter()
        for snapshot in self.snapshots:
            counter.update(snapshot.warnings)
        return dict(counter)

    @property
    def feature_count_by_preprocessor(self) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for snapshot in self.snapshots:
            for producer in snapshot.produced_by.values():
                counts[producer] += 1
        return dict(counts)


class FeatureService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def load_dataset(self, source: DataSourceRequest) -> DatasetBundle:
        adapter = CSVSourceAdapter(dataset_name=source.dataset_name, csv_path=source.csv_path)
        return adapter.load_dataset()

    def prepare_orders(self, bundle: DatasetBundle) -> pd.DataFrame:
        orders = bundle.orders.copy()
        if orders.empty:
            return orders

        orders["order_time"] = pd.to_datetime(orders["order_time"], errors="coerce")
        for numeric_field in [
            "purchase_qty",
            "purchase_amount",
            "purchase_price",
            "delivery_qty",
            "receipt_qty",
        ]:
            if numeric_field in orders.columns:
                orders[numeric_field] = pd.to_numeric(orders[numeric_field], errors="coerce")

        mapping = bundle.product_line_mapping.copy()
        if not mapping.empty and "drug_code" in mapping.columns:
            mapping_cols = [
                column
                for column in ["drug_code", "product_line_code", "product_line_name"]
                if column in mapping.columns
            ]
            orders = orders.merge(
                mapping[mapping_cols].drop_duplicates("drug_code"), on="drug_code", how="left"
            )

        drugs = bundle.drugs.copy()
        if not drugs.empty and "drug_code" in drugs.columns:
            metadata_cols = [
                column
                for column in ["drug_code", "drug_name", "spec", "dosage_form", "approval_no"]
                if column in drugs.columns and (column == "drug_code" or column not in orders.columns)
            ]
            if len(metadata_cols) > 1:
                orders = orders.merge(
                    drugs[metadata_cols].drop_duplicates("drug_code"),
                    on="drug_code",
                    how="left",
                )

        if "product_line_code" not in orders.columns:
            orders["product_line_code"] = orders["drug_code"].astype(str)
        orders["product_line_code"] = orders["product_line_code"].fillna("UNKNOWN").astype(str)
        if "product_line_name" not in orders.columns:
            orders["product_line_name"] = orders["product_line_code"]
        orders["product_line_name"] = (
            orders["product_line_name"].fillna(orders["product_line_code"]).astype(str)
        )
        return orders

    def run_preprocess(
        self,
        source: DataSourceRequest,
        as_of_date: date,
        enabled_preprocessors: list[str] | None = None,
        optional_tables: dict[str, pd.DataFrame] | None = None,
    ) -> FeatureRunResult:
        bundle = self.load_dataset(source)
        prepared_orders = self.prepare_orders(bundle)
        store = FeatureStore()
        context = PreprocessContext(
            canonical_orders=prepared_orders,
            dim_drug=bundle.drugs,
            dim_org=bundle.orgs,
            product_line_mapping=bundle.product_line_mapping,
            optional_tables=optional_tables or {},
            as_of_date=as_of_date,
            config=self.config,
            feature_store=store,
        )
        orchestrator = PreprocessOrchestrator(build_default_preprocessor_registry())
        snapshots, lineage = orchestrator.run(context, enabled_preprocessors)
        return FeatureRunResult(
            dataset_name=bundle.dataset_name,
            as_of_date=as_of_date,
            store=store,
            snapshots=snapshots,
            lineage=lineage,
            catalog=build_default_feature_catalog(),
            prepared_orders=prepared_orders,
            bundle=bundle,
        )

    def get_snapshot(
        self,
        source: DataSourceRequest,
        org_code: str,
        analysis_grain: str,
        target_code: str,
        as_of_date: date,
    ) -> tuple[FeatureRunResult, FeatureSnapshot | None]:
        run = self.run_preprocess(source, as_of_date)
        snapshot = run.store.get(unit_id(org_code, analysis_grain, target_code), as_of_date)
        return run, snapshot

    @staticmethod
    def snapshot_to_debug_dict(snapshot: FeatureSnapshot) -> dict[str, Any]:
        return snapshot.model_dump(mode="json")
