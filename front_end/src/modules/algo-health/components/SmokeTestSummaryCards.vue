<script setup>
import MetricCard from '../../../components/MetricCard.vue'

defineProps({
  summary: { type: Object, default: null }
})
</script>

<template>
  <div class="metric-grid">
    <MetricCard label="读取订单行数" :value="summary?.raw_order_rows ?? summary?.loaded_rows ?? '--'" />
    <MetricCard label="有效订单行数" :value="summary?.effective_order_rows ?? summary?.valid_order_rows ?? '--'" />
    <MetricCard label="分析单元数" :value="summary?.analysis_unit_count ?? summary?.unit_count ?? '--'" />
    <MetricCard label="P_alive 预测结果数" :value="summary?.prediction_count ?? '--'" />
    <MetricCard label="特征列数" :value="summary?.feature_column_count ?? summary?.feature_count ?? '--'" />
    <MetricCard label="Fallback" :value="summary?.fallback_used === undefined ? '--' : (summary.fallback_used ? '是' : '否')" />
    <MetricCard label="耗时秒" :value="summary?.elapsed_seconds ?? '--'" />
  </div>
  <div v-if="summary" class="summary-note">
    有效订单行数 {{ summary.effective_order_rows ?? summary.valid_order_rows ?? '--' }}；
    分析单元数 {{ summary.analysis_unit_count ?? summary.unit_count ?? '--' }}；
    P_alive 预测结果数 {{ summary.prediction_count ?? '--' }}。
    <span v-if="summary.prediction_count === (summary.analysis_unit_count ?? summary.unit_count)">每个分析单元在检测日期只输出 1 条 P_alive。</span>
  </div>
</template>

<style scoped>
.summary-note {
  margin-top: 10px;
  color: var(--text-muted);
  font-size: 13px;
}
</style>
