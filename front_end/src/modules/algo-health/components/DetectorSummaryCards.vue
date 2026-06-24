<script setup>
import MetricCard from '../../../components/MetricCard.vue'

defineProps({
  summary: { type: Object, default: null }
})
</script>

<template>
  <div class="metric-grid">
    <MetricCard label="读取行数" :value="summary?.loaded_rows ?? '--'" />
    <MetricCard label="有效行数" :value="summary?.valid_rows ?? '--'" />
    <MetricCard label="Detector 数" :value="summary?.detector_count ?? '--'" />
    <MetricCard label="已实现" :value="summary?.implemented_detector_count ?? '--'" />
    <MetricCard label="接口预留" :value="summary?.interface_only_detector_count ?? '--'" />
    <MetricCard label="命中数" :value="summary?.hit_count ?? '--'" />
    <MetricCard label="Warning" :value="summary?.warning_count ?? '--'" />
    <MetricCard label="耗时秒" :value="summary?.elapsed_seconds ?? '--'" />
  </div>
</template>

