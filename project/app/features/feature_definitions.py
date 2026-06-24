from __future__ import annotations

BASIC_FEATURES = [
    "org_code",
    "product_line_code",
    "province",
    "city",
    "county",
    "org_level",
    "org_level_detail",
    "manufacturer_code",
    "manufacturer_name",
]

NUMERIC_FEATURES = [
    "days_since_last_purchase",
    "first_purchase_days_ago",
    "purchase_count_30d",
    "purchase_count_90d",
    "purchase_count_180d",
    "purchase_count_365d",
    "active_days_365d",
    "median_interval_days",
    "mean_interval_days",
    "std_interval_days",
    "mad_interval_days",
    "last_interval_days",
    "interval_z_score",
    "overdue_ratio",
    "qty_30d",
    "qty_90d",
    "qty_180d",
    "qty_365d",
    "qty_recent_vs_base_ratio",
    "amount_30d",
    "amount_90d",
    "amount_180d",
    "amount_365d",
    "amount_recent_vs_base_ratio",
    "freq_30d",
    "freq_90d",
    "freq_recent_vs_base_ratio",
    "sku_count_90d",
    "sku_count_365d",
    "sku_shrink_ratio",
    "avg_comparable_unit_price_90d",
    "min_comparable_unit_price_90d",
    "max_comparable_unit_price_90d",
    "price_recent_vs_base_ratio",
    "delivery_rate_90d",
    "receipt_rate_90d",
    "delivery_delay_median",
    "refusal_status_count_90d",
    "adi",
    "cv2",
]

CATEGORICAL_FEATURES = [
    "province",
    "city",
    "county",
    "org_level",
    "org_level_detail",
    "manufacturer_code",
    "manufacturer_name",
    "demand_profile",
]

MODEL_FEATURE_COLUMNS = [*BASIC_FEATURES, *NUMERIC_FEATURES, "demand_profile"]

FEATURE_SCHEMA_VERSION = "palive_features.v1"
