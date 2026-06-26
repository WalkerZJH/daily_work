
"""Canonical column definitions shared by cleaning, feature engineering, and tasks."""

ORDER_COLUMNS = [
    "order_id",
    "order_detail_id",
    "hospital_code",
    "hospital_name",
    "product_line_code",
    "product_line_name",
    "order_date",
    "purchase_qty",
    "purchase_amount",
    "unit_price",
]

ENTITY_GRAIN = ["hospital_code", "product_line_code"]
