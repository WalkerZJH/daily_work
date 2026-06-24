from __future__ import annotations

import pandas as pd

from app.adapters.canonicalize import canonicalize_order_dataframe


def test_raw_chinese_columns_map_to_canonical_schema_and_types() -> None:
    raw = pd.DataFrame(
        [
            {
                "数据唯一标识符": "SRC-1",
                "订单明细ID": "OD-1",
                "采购时间": "2026-01-02",
                "药品编码": "DRUG-1",
                "药品医保编码": "INS-1",
                "通用名": "阿莫西林",
                "商品名": "商品A",
                "规格": "10mg",
                "剂型": "片剂",
                "转换系数": "10",
                "采购价(元)": "20",
                "采购数量": "3",
                "医疗机构编码": "ORG-1",
                "医疗机构": "医院A",
                "省": "江苏省",
            },
            {
                "数据唯一标识符": "SRC-2",
                "订单明细ID": "OD-2",
                "采购时间": "2026-01-03",
                "药品编码": "DRUG-2",
                "通用名": None,
                "商品名": "商品B",
                "转换系数": "0",
                "采购价(元)": "30",
                "采购数量": "5",
                "医疗机构编码": "ORG-1",
            },
        ]
    )

    orders = canonicalize_order_dataframe(raw)

    assert {"source_row_id", "order_detail_id", "order_id", "order_time"}.issubset(
        orders.columns
    )
    assert pd.api.types.is_datetime64_any_dtype(orders["order_time"])
    assert orders.loc[0, "purchase_qty"] == 3
    assert orders.loc[0, "purchase_price"] == 20
    assert orders.loc[0, "comparable_unit_price"] == 2
    assert orders.loc[1, "comparable_unit_price"] == 30
    assert "INVALID_CONVERSION_FACTOR" in orders.loc[1, "canonical_warnings"]
    assert orders.loc[0, "product_line_code"] == "阿莫西林"
