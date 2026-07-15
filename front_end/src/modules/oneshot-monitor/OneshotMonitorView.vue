<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import MetricCard from '../../components/MetricCard.vue'
import SectionCard from '../../components/SectionCard.vue'
import { useManufacturerScope } from '../../context/manufacturerScope'
import { createEmptyOneshotData, loadOneshotData, normalizeWorkbenchQuery } from '../monthly-demo/pageDataAdapter'

const params = new URLSearchParams(window.location.search)
const query = reactive(
  normalizeWorkbenchQuery({
    backendBaseUrl: params.get('backendBaseUrl'),
    userId: params.get('user_id') || params.get('userId'),
    demoMode: params.get('demoMode'),
    observationDate: params.get('observation_date'),
    manufacturerCode: params.get('manufacturer_code'),
    reportMonth: params.get('report_month'),
    runDate: params.get('run_date'),
    probabilityReportMonth: params.get('probability_report_month'),
    detectorRunDate: params.get('detector_run_date'),
    horizon: params.get('horizon') || params.get('h'),
    topN: Number(params.get('top_n')),
    sortBy: params.get('sort_by')
  })
)

const state = ref(createEmptyOneshotData())
const isLoading = ref(false)
const manufacturerScope = useManufacturerScope()
const manufacturerCode = manufacturerScope.manufacturerCode
let requestSequence = 0
let pageReady = false

async function loadPage() {
  const sequence = ++requestSequence
  isLoading.value = true
  state.value = createEmptyOneshotData()
  try {
    const loadedState = await loadOneshotData(query, { allowDemo: query.demoMode })
    if (sequence !== requestSequence) return
    state.value = loadedState
  } finally {
    if (sequence === requestSequence) isLoading.value = false
  }
}

onMounted(async () => {
  await manufacturerScope.initialize()
  query.manufacturerCode = manufacturerCode.value
  pageReady = true
  await loadPage()
})

watch(manufacturerCode, async (nextCode) => {
  if (!pageReady || !nextCode || nextCode === query.manufacturerCode) return
  query.manufacturerCode = nextCode
  await loadPage()
})
</script>

<template>
  <div class="page-shell oneshot-monitor">
    <div class="page-header">
      <h1>新进终端监测</h1>
      <div class="subtitle">首采事实 · 新增统计 · 排序依据</div>
    </div>

    <div class="grid-4">
      <MetricCard label="当日新增终端" :value="String(state.oneshotSummary.dailyNewTerminalCount)" tone="success" />
      <MetricCard label="本月新增终端" :value="String(state.oneshotSummary.monthlyNewTerminalCount)" tone="info" />
      <MetricCard label="当前清单" :value="String(state.oneshotSummary.count)" tone="info" />
      <MetricCard v-if="state.oneshotSummary.evidenceReady" label="高复购倾向" :value="String(state.oneshotSummary.highPropensityCount)" tone="success" />
    </div>

    <SectionCard
      title="新进终端清单"
      :subtitle="state.oneshotSummary.evidenceReady ? '围绕首采事实和排序依据展示' : '当前仅展示首采事实'"
    >
      <div v-if="isLoading" class="empty">刷新中</div>
      <div v-else-if="!state.oneshotTerminals.length" class="empty">
        <strong>{{ state.emptyTitle }}</strong>
        <p>{{ state.emptyMessage }}</p>
      </div>
      <div v-else class="data-table-wrap">
        <table>
          <thead>
            <tr>
              <th>新进终端</th>
              <th>产品线</th>
              <th>首次采购</th>
              <th>首采金额</th>
              <th>首采后天数</th>
              <th v-if="state.oneshotSummary.evidenceReady">复购倾向</th>
              <th v-if="state.oneshotSummary.evidenceReady">预计复购金额</th>
              <th v-if="state.oneshotSummary.evidenceReady">复购促进优先级</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in state.oneshotTerminals" :key="row.id">
              <td>
                <strong>{{ row.hospital }}</strong>
                <div class="muted">{{ row.manufacturer }}</div>
                <div class="muted text-mono">{{ row.id }}</div>
              </td>
              <td>{{ row.drug }}<div class="muted">{{ row.region }}</div></td>
              <td>{{ row.firstPurchaseDate }}</td>
              <td>{{ row.firstPurchaseAmountText }}</td>
              <td>{{ row.daysSinceFirstPurchase }} 天</td>
              <td v-if="state.oneshotSummary.evidenceReady"><span class="risk-chip risk-chip-green">{{ row.repurchasePropensityText }}</span></td>
              <td v-if="state.oneshotSummary.evidenceReady">{{ row.expectedRepurchaseAmountText }}</td>
              <td v-if="state.oneshotSummary.evidenceReady">{{ row.priority }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!state.oneshotSummary.evidenceReady && state.oneshotTerminals.length" class="empty">
        暂无独立复购证据，仅展示新进终端首采记录
      </div>
    </SectionCard>

    <SectionCard v-if="state.oneshotSummary.evidenceReady" title="排序依据">
      <div class="observation-list">
        <article v-for="row in state.oneshotTerminals.filter((item) => item.reason)" :key="`${row.id}-reason`" class="observation-card">
          <div>
            <h3>{{ row.hospital }}</h3>
            <p>{{ row.reason }}</p>
          </div>
        </article>
      </div>
    </SectionCard>
  </div>
</template>
