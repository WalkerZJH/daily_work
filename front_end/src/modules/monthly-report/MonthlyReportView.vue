<script setup>
import { computed, onMounted, ref } from 'vue'
import MetricCard from '../../components/MetricCard.vue'
import SectionCard from '../../components/SectionCard.vue'
import {
  createEmptyMonthlyReportsData,
  loadMonthlyReportsData,
  normalizeWorkbenchQuery
} from '../monthly-demo/pageDataAdapter'

const query = normalizeWorkbenchQuery(Object.fromEntries(new URLSearchParams(window.location.search).entries()))
const state = ref(createEmptyMonthlyReportsData(query))
const selectedReportId = ref(state.value.dailyReportOptions[0]?.id || '')
const activeDailyReport = computed(
  () => state.value.dailyReportOptions.find((item) => item.id === selectedReportId.value) || state.value.dailyReportOptions[0] || {}
)

onMounted(async () => {
  const data = await loadMonthlyReportsData(query, { allowDemo: query.demoMode })
  if (!data) return
  state.value = data
  if (!state.value.dailyReportOptions.some((item) => item.id === selectedReportId.value)) {
    selectedReportId.value = state.value.dailyReportOptions[0]?.id || ''
  }
})
</script>

<template>
  <div class="page-shell">
    <div class="page-header">
      <h1>月报切换</h1>
      <div class="subtitle">
        查看不同月报日的风险对象、巡检线索与新进终端概览
      </div>
    </div>

    <div v-if="!state.ready" class="empty-state panel">
      <h2>{{ state.emptyTitle }}</h2>
      <p>{{ state.emptyMessage }}</p>
    </div>

    <section v-else class="report-switch-panel panel">
      <div class="report-switch-copy">
        <span class="eyebrow">往期日报切换</span>
        <h2>{{ activeDailyReport.title }}</h2>
        <p>{{ activeDailyReport.summary }}</p>
      </div>
      <div class="segmented-control report-switcher" aria-label="往期日报切换">
        <button
          v-for="report in state.dailyReportOptions"
          :key="report.id"
          type="button"
          class="segment-btn"
          :class="{ active: selectedReportId === report.id }"
          @click="selectedReportId = report.id"
        >
          <strong>{{ report.date }}</strong>
          <span>{{ report.label }}</span>
        </button>
      </div>
      <dl class="definition-grid compact report-switch-meta">
        <dt>月报批次</dt><dd class="text-mono">{{ activeDailyReport.scoreBatchId }}</dd>
        <dt>月报日期</dt><dd>{{ activeDailyReport.date }}</dd>
        <dt>重点风险对象</dt><dd>{{ activeDailyReport.highRiskEntities }}</dd>
        <dt>新进终端</dt><dd>{{ activeDailyReport.oneshotCount }}</dd>
        <dt>巡检线索</dt><dd>{{ activeDailyReport.detectorAlerts }}</dd>
      </dl>
    </section>

    <div v-if="state.ready" class="grid-4">
      <MetricCard
        v-for="item in state.overviewMetrics"
        :key="item.label"
        :label="item.label"
        :value="item.value"
        :tone="item.tone"
      />
    </div>

    <SectionCard v-if="state.ready" title="日报规则巡检状态" subtitle="日报变化来自规则巡检">
      <dl class="definition-grid compact">
        <dt>巡检日期</dt><dd>{{ state.dailyDetectorStatus.runDate }}</dd>
        <dt>今日规则线索</dt><dd>{{ state.dailyDetectorStatus.clueCount }}</dd>
        <dt>已附着规则证据</dt><dd>{{ state.dailyDetectorStatus.attachedHighRiskCount }}</dd>
        <dt>数据状态</dt><dd>{{ state.dailyDetectorStatus.sourceLabel }}</dd>
      </dl>
    </SectionCard>

    <SectionCard v-if="state.ready" title="月报列表" subtitle="生产商主视角下的风险对象与巡检概览">
      <div class="report-list">
        <article v-for="report in state.monthlyReports" :key="report.id" class="report-card">
          <h3>{{ report.title }}</h3>
          <p>{{ report.summary }}</p>
          <dl class="definition-grid compact">
            <dt>月报月份</dt><dd>{{ report.reportMonth }}</dd>
            <dt>月报批次</dt><dd class="text-mono">{{ report.scoreBatchId }}</dd>
            <dt>月报日期</dt><dd>{{ report.dataWatermarkAt }}</dd>
          </dl>
        </article>
      </div>
    </SectionCard>
  </div>
</template>
