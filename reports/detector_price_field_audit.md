# Detector 价格字段审计

- 单价字段：`purchase_unit_price`，来源为清洗表中的直接采购单价字段。
- 禁止使用 `order_amount / order_quantity` 推导或替代单价。
- 采购单位字段：`purchase_unit`，已在清洗链路标准化，不在 Detector 阶段回查 raw。
- 全量单价空值：0；非正数：12。
- 正常完成订单：514,583；其中正单价覆盖：514,583。
- 正常完成订单单位空值：0。
- 药品数：61；存在多个采购单位的药品数：0。
- 价格比较键固定为 `drug_code × purchase_unit`；实体侧规则再叠加 `manufacturer_code × hospital_code`。
- 低价参考集只使用观察日前正常完成订单，当前观察日订单不进入自身参考集。

价格规则当前工程门已通过，但企业阈值与价格业务语义仍待业务验收，不能解释为价格竞争。
