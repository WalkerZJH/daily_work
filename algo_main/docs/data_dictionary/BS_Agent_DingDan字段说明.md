# BS_Agent_DingDan 字段说明

本字典用于第一阶段字段理解、EDA、初步清洗和清洗规则沉淀。当前阶段不做 detector、P_alive、趋势检测、业务预警或工单系统。

## 总体原则

- SQL Server 表 `BS_Agent_DingDan` 是真实数据源。
- CSV 只用于小样本导出、人工 review 映射表和 EDA 汇总结果，不作为百万级主数据处理格式。
- 原始全量缓存优先使用 Parquet：`data/01_raw/BS_Agent_DingDan.parquet`。
- 清洗后算法主链路输入优先使用 Parquet：`data/03_cleaned/bs_agent_dingdan_model_base.parquet`。
- 新脱敏口径下，数量字段统一乘随机数 q，金额字段统一乘随机数 m，采购价格可能单独脱敏。数量字段之间、金额字段之间的比例和趋势可用于探索分析；金额字段与数量字段之间的真实价格关系不可用。
- `医疗机构详细等级` 暂认为错误或不可信，只保留 raw/audit，不进入 clean 主字段和算法字段。
- `hospital_level_code` 是有序类别变量，`semantic_type=ordinal_category`，后续建模时不得默认当作连续变量。

## 字段字典

| 原始中文字段名 | 推荐英文别名 | 字段类型 | 进入 clean 表 | 当前可用于算法 | 清洗规则 | 备注 |
|---|---|---|---|---|---|---|
| 数据唯一标识符 | row_uid | identifier | 是 | 是 | 转字符串，检查唯一性 | clean 主键候选 |
| 订单明细ID | order_detail_id | identifier | 是 | 是 | 转字符串，检查重复和生命周期记录 | 若重复，不武断删除 |
| 数据来源 | data_source | metadata | 否 | 否 | 输出 distinct/top value | 有效但暂不进算法 |
| 订单名称 | order_name | metadata | 否 | 否 | 输出 distinct/top value | 暂时无效 |
| 省 | province_name | geography | 否 | 否 | 进入 region 映射表 | clean 主表保留编码 |
| 省编码 | raw_province_code | geography | 否 | 否 | 用于一致性审计 | 优先从县区编码派生 |
| 市 | city_name | geography | 否 | 否 | 进入 region 映射表 | clean 主表保留编码 |
| 市编码 | raw_city_code | geography | 否 | 否 | 用于一致性审计 | 优先从县区编码派生 |
| 县区 | county_name | geography | 否 | 否 | 进入 region 映射表 | clean 主表保留编码 |
| 县区编码 | county_code | geography | 是 | 是 | 字符串补齐；派生 province_code/city_code | 行政区划编码，不是邮编 |
| 采购时间 | purchase_time | time | 是 | 是 | 解析为 datetime，非法值进报告 | 核心时间字段 |
| 药品编码 | drug_code | drug | 是 | 是 | 转字符串，检查与医保编码一致性 | 药品主编码 |
| 药品医保编码 | insurance_drug_code | drug | 否 | 待确认 | 检查与药品编码一致性 | 完全一致时不进算法 |
| 通用名 | drug_name | drug | 是 | 是 | 去空白，空值报告 | 作为药品具体名称 |
| 商品名 | product_name | drug | 是 | 可选 | 去空白 | 可保留为审计/展示字段 |
| 剂型 | dosage_form | drug | 否 | 否 | raw/audit 保留 | 药品维度审计字段 |
| 规格 | spec | drug | 否 | 否 | raw/audit 保留 | 后续正则拆列依据 |
| 转换系数 | conversion_factor | drug | 否 | 否 | raw/audit 保留 | 暂不用于算法 |
| 采购单位 | purchase_unit | drug | 否 | 否 | raw/audit 保留 | 暂不用于算法 |
| 材质 | material | drug | 否 | 否 | raw/audit 保留 | 暂不用于算法 |
| 采购价(元) | raw_sensitive_purchase_price | numeric_sensitive | 可选 raw_sensitive | 否 | 数值化，仅做脱敏破坏检查 | 不做价格算法 |
| 采购数量 | raw_sensitive_purchase_quantity | numeric_sensitive | 可选 raw_sensitive | 有边界 | 数值化；与配送/到货/退回/作废数量同乘 q | 可用于数量比例和数量趋势探索 |
| 采购金额(元) | raw_sensitive_purchase_amount | numeric_sensitive | 可选 raw_sensitive | 有边界 | 数值化；与配送/到货金额同乘 m | 可用于金额趋势和金额相对关系；不能除以数量推单价 |
| 配送数量 | raw_sensitive_delivery_quantity | numeric_sensitive | 可选 raw_sensitive | 有边界 | 数值化；与采购/到货数量同乘 q | 可计算 delivery_rate = 配送数量 / 采购数量 |
| 配送金额(元) | raw_sensitive_delivery_amount | numeric_sensitive | 可选 raw_sensitive | 否 | 数值化，仅做脱敏破坏检查 | 不做金额算法 |
| 到货数量 | raw_sensitive_arrival_quantity | numeric_sensitive | 可选 raw_sensitive | 有边界 | 数值化；与采购/配送数量同乘 q | 可计算 arrival_rate 和 overall_arrival_rate |
| 到货金额(元) | raw_sensitive_arrival_amount | numeric_sensitive | 可选 raw_sensitive | 否 | 数值化，仅做脱敏破坏检查 | 不做金额算法 |
| 采购地址 | purchase_address | metadata | 否 | 否 | null rate 报告 | 大量 null |
| 订单状态 | order_status_raw | status | 是 | 是 | 用映射表归类为 stage/code | 未匹配值输出 review |
| 企业编码 | enterprise_code | enterprise | 否 | 待确认 | 检查与生产企业字段关系 | 可能为本企业冗余字段 |
| 医疗机构等级 | hospital_level_raw | institution | 是 | 是 | 归一化为 label/code | 主清洗依据 |
| 医疗机构详细等级 | hospital_level_detail_raw | institution | 否 | 否 | 仅 raw/audit | 暂不可信 |
| 医疗机构编码 | hospital_code | institution | 是 | 是 | 转字符串，空值报告 | 机构主编码 |
| 医疗机构 | hospital_name | institution | 是 | 是 | 去空白 | 机构名称 |
| 配送企业编码 | distributor_code | enterprise | 是 | 是 | 转字符串 | 配送维度字段 |
| 配送企业 | distributor_name | enterprise | 是 | 是 | 去空白 | 配送维度字段 |
| 生产企业编码 | manufacturer_code | enterprise | 是 | 是 | 转字符串，检查一对一 | 生产企业主编码 |
| 生产企业 | manufacturer_name | enterprise | 是 | 是 | 去空白，检查一对一 | 生产企业名称 |
| 药品类别 | drug_category_raw | category | 是 | 是 | 编码为 drug_category_code | 输出映射表 |
| 数据更新时间 | updated_at | time | 否 | 否 | 暂时忽略 | 仅重复记录审计时使用 |
| 配送时间 | delivery_time | time | 否 | 否 | null rate 报告 | null 太多，暂不进算法 |
| 到货时间 | arrival_time | time | 否 | 否 | null rate 报告 | null 太多，暂不进算法 |
| 项目名称 | project_name | metadata | 否 | 否 | null rate 报告 | 大量 null |
| 所有制形式 | ownership_type_raw | category | 是 | 是 | 编码为 ownership_type_code | 输出映射表 |
| 退回数量 | return_quantity | numeric_sensitive | 是 | 待确认 | null 填 0，统计非零比例 | 不用于业务算法判断 |
| 作废数量 | void_quantity | numeric_sensitive | 否 | 否 | 统计非零行数和样本 | 非零极少时不进算法 |

## 当前可用于算法的 clean 字段

`row_uid`、`order_detail_id`、`purchase_time`、`province_code`、`city_code`、`county_code`、`drug_code`、`drug_name`、`product_name`、`drug_category_code`、`drug_category_raw`、`hospital_code`、`hospital_name`、`hospital_level_raw`、`hospital_level_label`、`hospital_level_code`、`ownership_type_code`、`ownership_type_raw`、`distributor_code`、`distributor_name`、`manufacturer_code`、`manufacturer_name`、`order_status_raw`、`order_status_stage`、`order_status_code`。

## 当前不可用于业务算法判断的字段

所有 `raw_sensitive_*` 数值字段、`delivery_time`、`arrival_time`、`project_name`、`purchase_address`、`order_name`、`updated_at`、`hospital_level_detail_raw`。

## 待确认问题

1. `订单明细ID` 重复是否代表同一订单明细的状态生命周期记录。
2. 数量字段是否统一乘随机数 q、金额字段是否统一乘随机数 m，以及采购价格是否单独脱敏。
3. `企业编码` 与 `生产企业编码/生产企业` 的业务含义和冗余关系。
4. `医疗机构详细等级` 是否确认为错误字段，是否未来会修复。
