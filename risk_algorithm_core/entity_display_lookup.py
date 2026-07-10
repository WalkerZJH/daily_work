"""Build result-batch display-name lookup tables."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pandas as pd


ENTITY_DISPLAY_LOOKUP_SCHEMA_VERSION = "entity_display_lookup_v1"

ENTITY_DISPLAY_LOOKUP_COLUMNS = [
    "tenant_id",
    "report_month",
    "manufacturer_code",
    "manufacturer_display_name",
    "hospital_code",
    "hospital_display_name",
    "drug_code",
    "drug_group",
    "drug_display_name",
    "product_line_code",
    "product_line_name",
    "region_code",
    "region_display_name",
    "display_key",
    "display_name_source",
    "display_name_quality",
    "source_raw_batch_id",
    "updated_at",
]

ENTITY_DISPLAY_LOOKUP_UNIQUE_KEY = [
    "tenant_id",
    "report_month",
    "manufacturer_code",
    "hospital_code",
    "drug_group",
]


def build_entity_display_lookup(
    risk_entities: pd.DataFrame,
    normalized_tables: dict[str, pd.DataFrame] | None,
    report_month: str,
    source_raw_batch_id: str | None = None,
    updated_at: str | None = None,
    raw_batch_id: str | None = None,
    additional_entities: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build display names for monthly entities plus related detector entities."""
    normalized_tables = normalized_tables or {}
    source_raw_batch_id = source_raw_batch_id or raw_batch_id or ""
    updated_at = updated_at or dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()
    entity_source = _combine_entity_sources(risk_entities, additional_entities)
    if entity_source.empty:
        return pd.DataFrame(columns=ENTITY_DISPLAY_LOOKUP_COLUMNS)

    base = _base_entity_keys(entity_source, report_month)
    manufacturer_map = _lookup_map(normalized_tables.get("manufacturer_master"), "manufacturer_code", ["manufacturer_display_name", "manufacturer_name"])
    hospital_map = _lookup_map(normalized_tables.get("hospital_master"), "hospital_code", ["hospital_display_name", "hospital_name"])
    hospital_region_code = _lookup_map(normalized_tables.get("hospital_master"), "hospital_code", ["region_code"])
    hospital_region_name = _lookup_map(normalized_tables.get("hospital_master"), "hospital_code", ["region_display_name", "region_name"])
    drug_map = _lookup_map(normalized_tables.get("drug_master"), "drug_code", ["drug_display_name", "drug_name"])
    drug_line_code = _lookup_map(normalized_tables.get("drug_master"), "drug_code", ["product_line_code"])
    drug_line_name = _lookup_map(normalized_tables.get("drug_master"), "drug_code", ["product_line_name"])
    mapping_line_code = _lookup_map(normalized_tables.get("product_line_mapping"), "drug_code", ["product_line_code"])
    mapping_line_name = _lookup_map(normalized_tables.get("product_line_mapping"), "drug_code", ["product_line_name"])
    order_names = _order_name_maps(normalized_tables.get("orders"))

    rows: list[dict[str, Any]] = []
    for _, entity in base.iterrows():
        manufacturer_code = _str_value(entity.get("manufacturer_code"))
        hospital_code = _str_value(entity.get("hospital_code"))
        drug_code = _str_value(entity.get("drug_code")) or _str_value(entity.get("drug_group"))
        drug_group = _str_value(entity.get("drug_group")) or drug_code

        manufacturer_name, manufacturer_source = _resolve_name(
            manufacturer_code,
            [
                (manufacturer_map.get(manufacturer_code), "master"),
                (_str_value(entity.get("manufacturer_display_name")), "result_batch"),
            ],
            fallback=manufacturer_code,
        )
        hospital_name, hospital_source = _resolve_name(
            hospital_code,
            [
                (hospital_map.get(hospital_code), "master"),
                (_str_value(entity.get("hospital_display_name")), "result_batch"),
                (order_names["hospital"].get(hospital_code), "order"),
            ],
            fallback=hospital_code,
        )
        drug_name, drug_source = _resolve_name(
            drug_group,
            [
                (drug_map.get(drug_code), "master"),
                (_str_value(entity.get("drug_display_name")), "result_batch"),
                (order_names["drug"].get(drug_code), "order"),
            ],
            fallback=drug_group or drug_code,
        )
        region_code, region_code_source = _resolve_name(
            _str_value(entity.get("region_code")),
            [
                (hospital_region_code.get(hospital_code), "master"),
                (_str_value(entity.get("region_code")), "result_batch"),
                (order_names["region_code"].get(hospital_code), "order"),
            ],
            fallback=_str_value(entity.get("region_code")),
        )
        region_name, region_source = _resolve_name(
            region_code or "unknown_region",
            [
                (hospital_region_name.get(hospital_code), "master"),
                (_str_value(entity.get("region_display_name")), "result_batch"),
                (order_names["region"].get(hospital_code), "order"),
            ],
            fallback=_str_value(entity.get("region_display_name")) or "unknown_region",
        )
        product_line_code = mapping_line_code.get(drug_code) or drug_line_code.get(drug_code) or _str_value(entity.get("product_line_code"))
        product_line_name = mapping_line_name.get(drug_code) or drug_line_name.get(drug_code) or _str_value(entity.get("product_line_name"))

        _ = manufacturer_source, region_code_source
        sources = {hospital_source, drug_source, region_source}
        quality = _quality_from_sources(sources)
        display_key = "|".join([_str_value(entity.get("tenant_id")) or "default_tenant", report_month, manufacturer_code, hospital_code, drug_group])
        rows.append(
            {
                "tenant_id": _str_value(entity.get("tenant_id")) or "default_tenant",
                "report_month": report_month,
                "manufacturer_code": manufacturer_code,
                "manufacturer_display_name": manufacturer_name,
                "hospital_code": hospital_code,
                "hospital_display_name": hospital_name,
                "drug_code": drug_code,
                "drug_group": drug_group,
                "drug_display_name": drug_name,
                "product_line_code": product_line_code,
                "product_line_name": product_line_name,
                "region_code": region_code,
                "region_display_name": region_name,
                "display_key": display_key,
                "display_name_source": quality,
                "display_name_quality": quality,
                "source_raw_batch_id": source_raw_batch_id,
                "updated_at": updated_at,
            }
        )

    out = pd.DataFrame(rows, columns=ENTITY_DISPLAY_LOOKUP_COLUMNS)
    out = out.drop_duplicates(ENTITY_DISPLAY_LOOKUP_UNIQUE_KEY, keep="first").reset_index(drop=True)
    return out[ENTITY_DISPLAY_LOOKUP_COLUMNS]


def _combine_entity_sources(
    risk_entities: pd.DataFrame,
    additional_entities: pd.DataFrame | None,
) -> pd.DataFrame:
    frames = [frame.copy() for frame in [risk_entities, additional_entities] if frame is not None and not frame.empty]
    if not frames:
        return pd.DataFrame()
    columns = sorted({column for frame in frames for column in frame.columns})
    aligned = [frame.reindex(columns=columns) for frame in frames]
    return pd.concat(aligned, ignore_index=True)


def _base_entity_keys(risk_entities: pd.DataFrame, report_month: str) -> pd.DataFrame:
    base = risk_entities.copy()
    if "tenant_id" not in base:
        base["tenant_id"] = "default_tenant"
    if "report_month" not in base:
        base["report_month"] = report_month
    if "drug_code" not in base:
        base["drug_code"] = base.get("drug_group", "")
    if "drug_group" not in base:
        base["drug_group"] = base.get("drug_code", "")
    key_cols = [col for col in ENTITY_DISPLAY_LOOKUP_UNIQUE_KEY if col in base]
    return base.drop_duplicates(key_cols, keep="first").reset_index(drop=True)


def _lookup_map(df: pd.DataFrame | None, key_col: str, value_cols: list[str]) -> dict[str, str]:
    if df is None or df.empty or key_col not in df:
        return {}
    value_col = next((col for col in value_cols if col in df), None)
    if value_col is None:
        return {}
    work = df[[key_col, value_col]].dropna(subset=[key_col])
    out: dict[str, str] = {}
    for _, row in work.iterrows():
        key = _str_value(row[key_col])
        value = _str_value(row[value_col])
        if key and value and key not in out:
            out[key] = value
    return out


def _order_name_maps(orders: pd.DataFrame | None) -> dict[str, dict[str, str]]:
    maps = {"hospital": {}, "drug": {}, "region": {}, "region_code": {}}
    if orders is None or orders.empty:
        return maps
    work = orders.copy()
    if "order_date" in work:
        work = work.sort_values("order_date")
    if "hospital_code" in work:
        maps["hospital"] = _latest_map(work, "hospital_code", ["hospital_display_name", "hospital_name"])
        maps["region"] = _latest_map(work, "hospital_code", ["region_display_name", "region_name"])
        maps["region_code"] = _latest_map(work, "hospital_code", ["region_code"])
    if "drug_code" in work:
        maps["drug"] = _latest_map(work, "drug_code", ["drug_display_name", "drug_name"])
    return maps


def _latest_map(df: pd.DataFrame, key_col: str, value_cols: list[str]) -> dict[str, str]:
    value_col = next((col for col in value_cols if col in df), None)
    if value_col is None:
        return {}
    out: dict[str, str] = {}
    for _, row in df[[key_col, value_col]].dropna(subset=[key_col]).iterrows():
        key = _str_value(row[key_col])
        value = _str_value(row[value_col])
        if key and value:
            out[key] = value
    return out


def _resolve_name(identity: str, candidates: list[tuple[str | None, str]], fallback: str) -> tuple[str, str]:
    for value, source in candidates:
        clean = _str_value(value)
        if clean and clean.lower() not in {"nan", "none", "nat"}:
            return clean, source
    clean_fallback = _str_value(fallback) or _str_value(identity)
    return clean_fallback, "code_fallback"


def _quality_from_sources(sources: set[str]) -> str:
    clean = {source for source in sources if source}
    if clean == {"master"}:
        return "master"
    if clean == {"code_fallback"}:
        return "code_fallback"
    if len(clean) == 1:
        return next(iter(clean))
    if "code_fallback" in clean:
        return "code_fallback"
    return "mixed"


def _str_value(value: Any) -> str:
    if value is None or value is pd.NA:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()
