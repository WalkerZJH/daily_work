# Database Mapping

`SQLTableSourceAdapter` reads `DATABASE_URL` from environment and defaults to table `BS_Agent_DingDan`. Override table name with `ORDER_TABLE_NAME`.

The adapter is read-only and builds a projected query from `RAW_ORDER_COLUMN_MAP`; it does not use `SELECT *`.

Key mappings:

| Raw column | Canonical field |
| --- | --- |
| 数据唯一标识符 | source_row_id |
| 订单明细ID | order_detail_id / order_id |
| 采购时间 | order_time |
| 药品编码 | drug_code |
| 药品医保编码 | insurance_drug_code |
| 通用名 | generic_name |
| 商品名 | trade_name |
| 采购价(元) | purchase_price |
| 采购数量 | purchase_qty |
| 配送数量 | delivery_qty |
| 到货数量 | receipt_qty |
| 医疗机构编码 | org_code |
| 医疗机构 | org_name |
| 配送企业编码 | distributor_code |
| 生产企业编码 | manufacturer_code |
| 数据更新时间 | updated_at |

The wide table is split into `orders`, `drugs`, `orgs`, and `product_line_mapping`. Product-line fallback is centralized in the adapter/canonicalizer:

- `product_line_code`: `generic_name`, then `insurance_drug_code`, then `drug_code`.
- `product_line_name`: `generic_name`, then `trade_name`, then `drug_code`.

`comparable_unit_price` v1 fallback is `purchase_price / conversion_factor`. If conversion factor is missing, zero, or negative, the fallback is `purchase_price` and `INVALID_CONVERSION_FACTOR` is recorded. This is not asserted as business-correct; unit conversion needs later confirmation.

Supported filters: `as_of_date`, `enterprise_code`, `province`, `province_code`, `row_limit`.
