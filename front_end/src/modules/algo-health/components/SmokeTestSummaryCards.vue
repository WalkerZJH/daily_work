<script setup>
import MetricCard from '../../../components/MetricCard.vue'

defineProps({
  summary: { type: Object, default: null }
})
</script>

<template>
  <div class="metric-grid">
    <MetricCard label="读取行数" :value="summary?.loaded_rows ?? '--'" />
    <MetricCard label="有效订单" :value="summary?.valid_order_rows ?? '--'" />
    <MetricCard label="分析单元" :value="summary?.unit_count ?? '--'" />
    <MetricCard label="特征数量" :value="summary?.feature_count ?? '--'" />
    <MetricCard label="预测数量" :value="summary?.prediction_count ?? '--'" />
    <MetricCard label="风险卡草稿" :value="summary?.risk_card_count ?? '--'" />
    <MetricCard label="耗时秒" :value="summary?.elapsed_seconds ?? '--'" />
  </div>
</template>
