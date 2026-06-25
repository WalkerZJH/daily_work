from __future__ import annotations

import os
from collections import Counter

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_app_config
from app.detectors.registry import DETECTOR_META
from app.adapters.canonicalize import prepare_canonical_orders
from app.schemas.api import DetectorCategoryOption, DetectorOption, OptionItem
from app.schemas.config import AppConfig
from app.schemas.api import DataSourceRequest
from app.services.detector_config_service import DetectorRuntimeConfigService
from app.services.feature_service import FeatureService

router = APIRouter(prefix="/api/v0/options", tags=["options"])

CATEGORY_NAMES = {
    "price_warning": "价格预警",
    "delivery_response": "配送响应",
    "terminal_change": "终端丢失/新进",
    "sales_fluctuation": "销量波动",
}


@router.get("/enterprises", response_model=list[OptionItem])
def enterprise_options(config: AppConfig = Depends(get_app_config)) -> list[OptionItem]:
    orders = _orders(config)
    if "enterprise_code" not in orders.columns:
        return []
    return _code_name_options(orders, "enterprise_code", "enterprise_code")


@router.get("/provinces", response_model=list[OptionItem])
def province_options(config: AppConfig = Depends(get_app_config)) -> list[OptionItem]:
    orders = _orders(config)
    code_col = "province_code" if "province_code" in orders.columns else "province"
    name_col = "province" if "province" in orders.columns else code_col
    return _code_name_options(orders, code_col, name_col)


@router.get("/product-lines", response_model=list[OptionItem])
def product_line_options(
    enterprise_code: str | None = Query(default=None),
    province_code: str | None = Query(default=None),
    config: AppConfig = Depends(get_app_config),
) -> list[OptionItem]:
    orders = _orders(config)
    if enterprise_code and "enterprise_code" in orders.columns:
        orders = orders[orders["enterprise_code"].astype(str) == str(enterprise_code)]
    if province_code and "province_code" in orders.columns:
        orders = orders[orders["province_code"].astype(str) == str(province_code)]
    if "product_line_code" not in orders.columns:
        return []
    name_col = "product_line_name" if "product_line_name" in orders.columns else "product_line_code"
    return _code_name_options(orders, "product_line_code", name_col)


@router.get("/detector-categories", response_model=list[DetectorCategoryOption])
def detector_category_options() -> list[DetectorCategoryOption]:
    counter = Counter(meta.category for meta in DETECTOR_META.values() if meta.detector_id.endswith("_warning"))
    return [
        DetectorCategoryOption(category_id=category, category_name=CATEGORY_NAMES.get(category, category), detector_count=count)
        for category, count in sorted(counter.items())
    ]


@router.get("/detectors", response_model=list[DetectorOption])
def detector_options(category: str | None = Query(default=None)) -> list[DetectorOption]:
    config_service = DetectorRuntimeConfigService()
    output = []
    for detector_id, meta in DETECTOR_META.items():
        if not detector_id.endswith("_warning"):
            continue
        if category and meta.category != category:
            continue
        runtime, _ = config_service.get_config(detector_id)
        output.append(
            DetectorOption(
                detector_id=detector_id,
                name_zh=meta.name_zh or meta.name,
                enabled=runtime.enabled,
                mode=runtime.mode,
                implemented=meta.implemented,
            )
        )
    return output


def _orders(config: AppConfig):
    source_type = "database" if os.getenv("DATABASE_URL") else "csv"
    source = DataSourceRequest(
        source_type=source_type,
        dataset_name="database:BS_Agent_DingDan" if source_type == "database" else "sample",
        row_limit=1000 if source_type == "database" else None,
    )
    bundle = FeatureService(config).load_dataset(source)
    return prepare_canonical_orders(bundle)


def _code_name_options(frame, code_col: str, name_col: str) -> list[OptionItem]:
    if code_col not in frame.columns:
        return []
    pairs = frame[[code_col, name_col]].dropna(subset=[code_col]).drop_duplicates().head(200)
    return [
        OptionItem(code=str(row[code_col]), name=str(row[name_col]) if name_col in pairs.columns else str(row[code_col]))
        for _, row in pairs.iterrows()
    ]
