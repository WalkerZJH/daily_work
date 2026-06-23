<template>
  <section class="warning-stack">
    <div class="warning-item">
      当前页面接入的是 v0 fake 链路：sample CSV + CSVAdapter + 规则 detector + 规则融合。真实 MySQL 数据、DBAdapter、物化视图和模型训练产物尚未接入。
    </div>
    <div class="warning-item">
      当前只覆盖终端动态识别。价格异常、配送异常、销量波动、完整工单处置、自动派单、同伴对照、BG/NBD、FDR、概率校准和 Agent 解释层均为预留能力。
    </div>
  </section>
</template>

<style scoped>
.warning-stack {
  display: grid;
  gap: 8px;
  margin-bottom: 16px;
}

.warning-item {
  border: 1px solid #fde68a;
  border-radius: var(--radius-sm);
  background: #fffbeb;
  color: #92400e;
  padding: 10px 12px;
  font-size: 12px;
  line-height: 1.5;
}
</style>
