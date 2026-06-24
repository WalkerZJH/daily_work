# 数据库字段映射

`SQLTableSourceAdapter` 从环境变量 `DATABASE_URL` 读取数据库连接，默认读取表 `BS_Agent_DingDan`。如需覆盖表名，可设置环境变量 `ORDER_TABLE_NAME`。

适配器只做只读查询，并根据 `RAW_ORDER_COLUMN_MAP` 构造列投影查询，不使用 `SELECT *`。

## 关键字段映射

| 原始列名 | canonical 字段 |
| --- | --- |
| 数据唯一标识符 | source_row_id |
| 订单明细ID | order_detail_id / order_id |
| 数据来源 | data_source |
| 订单名称 | order_name |
| 省 | province |
| 省编码 | province_code |
| 市 | city |
| 市编码 | city_code |
| 县区 | county |
| 县区编码 | county_code |
| 采购时间 | order_time |
| 药品编码 | drug_code |
| 药品医保编码 | insurance_drug_code |
| 通用名 | generic_name |
| 商品名 | trade_name |
| 剂型 | dosage_form |
| 规格 | spec |
| 转换系数 | conversion_factor |
| 采购单位 | purchase_unit |
| 采购价(元) | purchase_price |
| 采购数量 | purchase_qty |
| 采购金额(元) | purchase_amount |
| 配送数量 | delivery_qty |
| 配送金额(元) | delivery_amount |
| 到货数量 | receipt_qty |
| 到货金额(元) | receipt_amount |
| 订单状态 | order_status |
| 企业编码 | enterprise_code |
| 医疗机构等级 | org_level |
| 医疗机构详细等级 | org_level_detail |
| 医疗机构编码 | org_code |
| 医疗机构 | org_name |
| 配送企业编码 | distributor_code |
| 配送企业 | distributor_name |
| 生产企业编码 | manufacturer_code |
| 生产企业 | manufacturer_name |
| 药品类别 | drug_category |
| 数据更新时间 | updated_at |
| 配送时间 | delivery_time |
| 到货时间 | receipt_time |
| 退回数量 | return_qty |
| 作废数量 | void_qty |

## 宽表拆分

订单宽表会拆分为：

- `orders`：canonical 订单明细。
- `drugs`：按 `drug_code` 去重派生的药品维表。
- `orgs`：按 `org_code` 去重派生的机构维表。
- `product_line_mapping`：产品线映射。

如果没有外部产品线表，产品线 fallback 集中在 adapter/canonicalizer 内处理：

- `product_line_code`：优先 `generic_name`，其次 `insurance_drug_code`，最后 `drug_code`。
- `product_line_name`：优先 `generic_name`，其次 `trade_name`，最后 `drug_code`。

该 fallback 只是 v1 临时口径，不得写死到 detector 内部。

## comparable_unit_price

`comparable_unit_price` 的 v1 fallback 公式为：

```text
purchase_price / conversion_factor
```

当 `conversion_factor` 缺失、为 0 或为负数时，回退为 `purchase_price`，并记录 `INVALID_CONVERSION_FACTOR` 警告。

该公式尚未确认一定符合业务单位折算口径，后续需要结合真实数据和业务口径继续校验。

## 查询过滤

数据库 source 支持以下过滤参数：

- `as_of_date`
- `enterprise_code`
- `province`
- `province_code`
- `row_limit`
