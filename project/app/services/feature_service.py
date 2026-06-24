from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd

from app.adapters.base import DatasetBundle
from app.adapters.canonicalize import prepare_canonical_orders
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

    def run_preprocess(
        self,
        source: DataSourceRequest,
        as_of_date: date,
        enabled_preprocessors: list[str] | None = None,
        optional_tables: dict[str, pd.DataFrame] | None = None,
    ) -> FeatureRunResult:
        bundle = self.load_dataset(source)
        prepared_orders = prepare_canonical_orders(bundle)
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
