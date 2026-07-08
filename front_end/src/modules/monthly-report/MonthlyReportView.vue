<script setup>
import { computed, onMounted, ref } from 'vue'
import MetricCard from '../../components/MetricCard.vue'
import SectionCard from '../../components/SectionCard.vue'
import { createStaticMonthlyReportsData, loadMonthlyReportsData } from '../monthly-demo/pageDataAdapter'

const state = ref(createStaticMonthlyReportsData())
const selectedReportId = ref(state.value.dailyReportOptions[0].id)
const activeDailyReport = computed(
  () => state.value.dailyReportOptions.find((item) => item.id === selectedReportId.value) || state.value.dailyReportOptions[0]
)

onMounted(async () => {
  const data = await loadMonthlyReportsData()
  if (!data) return
  state.value = data
  if (!state.value.dailyReportOptions.some((item) => item.id === selectedReportId.value)) {
    selectedReportId.value = state.value.dailyReportOptions[0].id
  }
})
</script>

<template>
  <div class="page-shell">
    <div class="page-header">
      <h1>月报与批次</h1>
      <div class="subtitle">
        MonthlyReport · RiskResultBatch · score_batch_id={{ state.batchContext.scoreBatchId }} · data_watermark_at={{ state.batchContext.dataWatermarkAt }}
      </div>
    </div>

    <section class="report-switch-panel panel">
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
        <dt>score_batch_id</dt><dd class="text-mono">{{ activeDailyReport.scoreBatchId }}</dd>
        <dt>data_watermark_at</dt><dd>{{ activeDailyReport.dataWatermarkAt }}</dd>
        <dt>高风险 entity</dt><dd>{{ activeDailyReport.highRiskEntities }}</dd>
        <dt>oneshot</dt><dd>{{ activeDailyReport.oneshotCount }}</dd>
        <dt>detector 告警</dt><dd>{{ activeDailyReport.detectorAlerts }}</dd>
      </dl>
    </section>

    <div class="grid-4">
      <MetricCard
        v-for="item in state.overviewMetrics"
        :key="item.label"
        :label="item.label"
        :value="item.value"
        :tone="item.tone"
      />
    </div>

    <SectionCard title="批次模型指标" subtitle="主干模型、oneshot 复购模型与 detector 排序模型">
      <div class="data-table-wrap">
        <table>
          <thead>
            <tr>
              <th>模型</th>
              <th>评估窗口</th>
              <th>AUC</th>
              <th>PRAUC</th>
              <th>ECE</th>
              <th>Brier</th>
              <th>TopK recall</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="metric in state.modelMetrics" :key="metric.id">
              <td>
                <strong>{{ metric.name }}</strong>
                <div class="muted">{{ metric.role }} · {{ metric.horizon }}</div>
              </td>
              <td>{{ metric.window }}</td>
              <td>{{ metric.auc }}</td>
              <td>{{ metric.prauc }}</td>
              <td>{{ metric.ece }}</td>
              <td>{{ metric.brier }}</td>
              <td>
                <strong>{{ metric.topK }}</strong>
                <div class="muted">{{ metric.topKPolicy }}</div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </SectionCard>

    <SectionCard title="MonthlyReport 列表" subtitle="生产商主视角 / 高风险实体 / 医院 × 药品补齐结果按月对齐">
      <div class="report-list">
        <article v-for="report in state.monthlyReports" :key="report.id" class="report-card">
          <h3>{{ report.title }}</h3>
          <p>{{ report.summary }}</p>
          <dl class="definition-grid compact">
            <dt>report_month</dt><dd>{{ report.reportMonth }}</dd>
            <dt>score_batch_id</dt><dd class="text-mono">{{ report.scoreBatchId }}</dd>
            <dt>data_watermark_at</dt><dd>{{ report.dataWatermarkAt }}</dd>
          </dl>
        </article>
      </div>
    </SectionCard>
  </div>
</template>
