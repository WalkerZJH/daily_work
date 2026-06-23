from __future__ import annotations

from datetime import date

import pytest

from app.core.config import load_config
from app.features.catalog import FeatureCatalog, FeatureSpec, build_default_feature_catalog
from app.features.store import FeatureStore
from app.preprocessors.registry import build_default_preprocessor_registry
from app.schemas.api import DataSourceRequest
from app.services.feature_service import FeatureService


def test_feature_catalog_rejects_duplicate_feature_names() -> None:
    catalog = FeatureCatalog()
    spec = FeatureSpec(
        name="x",
        dtype="float",
        grain="unit",
        description="test",
        produced_by="test",
        version="v0",
    )
    catalog.register(spec)
    with pytest.raises(ValueError, match="Duplicate feature name"):
        catalog.register(spec)


def test_feature_store_get_and_query() -> None:
    config = load_config()
    run = FeatureService(config).run_preprocess(
        DataSourceRequest(dataset_name="sample"),
        date(2025, 12, 31),
    )
    store: FeatureStore = run.store

    snapshot = store.get("ORG_A|product_line|PL_A", date(2025, 12, 31))
    assert snapshot is not None
    assert snapshot.features["unit_id"] == "ORG_A|product_line|PL_A"
    assert store.query(as_of_date=date(2025, 12, 31), grain="product_line")


def test_preprocessor_registry_and_run() -> None:
    registry = build_default_preprocessor_registry()
    assert "unit_builder" in registry.names()
    assert "temporal_window" in registry.names()

    run = FeatureService(load_config()).run_preprocess(
        DataSourceRequest(dataset_name="sample"),
        date(2025, 12, 31),
    )

    assert run.enabled_preprocessors[:3] == ["unit_builder", "temporal_window", "demand_shape"]
    assert run.feature_count > 0
    assert len(build_default_feature_catalog().list()) >= 40


def test_as_of_date_excludes_future_orders_from_feature_snapshot() -> None:
    run = FeatureService(load_config()).run_preprocess(
        DataSourceRequest(dataset_name="sample"),
        date(2025, 12, 31),
    )
    snapshot = run.store.get("ORG_A|product_line|PL_A", date(2025, 12, 31))

    assert snapshot is not None
    assert snapshot.features["last_order_date"] == "2025-06-20"
    assert snapshot.features["first_order_date"] == "2025-01-05"
