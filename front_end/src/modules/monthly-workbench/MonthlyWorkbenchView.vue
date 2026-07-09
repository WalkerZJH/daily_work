<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import MetricCard from '../../components/MetricCard.vue'
import SectionCard from '../../components/SectionCard.vue'
import {
  createStaticWorkbenchData,
  createStaticWorkbenchOptions,
  loadWorkbenchData,
  loadWorkbenchOptions,
  normalizeWorkbenchQuery
} from '../monthly-demo/pageDataAdapter'

const urlParams = new URLSearchParams(window.location.search)
const query = reactive(
  normalizeWorkbenchQuery({
    manufacturerCode: urlParams.get('manufacturer_code'),
    reportMonth: urlParams.get('report_month'),
    runDate: urlParams.get('run_date'),
    horizon: urlParams.get('horizon') || urlParams.get('h'),
    topN: Number(urlParams.get('top_n')),
    sortBy: urlParams.get('sort_by')
  })
)

const options = ref(createStaticWorkbenchOptions())
const state = ref(createStaticWorkbenchData(query))
const isLoading = ref(false)

const dailyDetectorMetrics = computed(() => [
  { label: '日报日期', value: state.value.dailyDetectorStatus.runDate || '-', tone: 'info' },
  { label: '今日巡检线索', value: String(state.value.dailyDetectorStatus.clueCount ?? '-'), tone: 'warning' },
  { label: '已附着证据', value: String(state.value.dailyDetectorStatus.attachedHighRiskCount ?? '-'), tone: 'success' },
  { label: '巡检对象', value: String(state.value.dailyDetectorStatus.scannedEntityCount ?? '-'), tone: 'neutral' }
])

const queryParams = computed(() => {
  const params = new URLSearchParams({
    manufacturer_code: query.manufacturerCode,
    report_month: query.reportMonth,
    run_date: query.runDate,
    horizon: query.horizon,
    top_n: String(query.topN),
    sort_by: query.sortBy
  })
  return params
})

function detailHref(row) {
  const params = new URLSearchParams(queryParams.value)
  params.set('id', row.entityId)
  return `clue-detail.html?${params.toString()}`
}

function updateUrl() {
  const nextUrl = `${window.location.pathname}?${queryParams.value.toString()}`
  window.history.replaceState({}, '', nextUrl)
}

async function refreshWorkbench() {
  isLoading.value = true
  updateUrl()
  const staticState = createStaticWorkbenchData(query)
  const data = await loadWorkbenchData(query)
  state.value = data || staticState
  isLoading.value = false
}

onMounted(async () => {
  const loadedOptions = await loadWorkbenchOptions(query)
  if (loadedOptions) options.value = loadedOptions
  await refreshWorkbench()
})

watch(
  () => [query.manufacturerCode, query.runDate, query.horizon, query.topN, query.sortBy],
  () => refreshWorkbench()
)
</script>

<template>
  <div class="page-shell monthly-workbench">
    <div class="page-header control-header">
      <div>
        <h1>VP 工作台</h1>
        <div class="subtitle">今日重点风险对象 · 今日巡检线索 · 涉及金额与丢失概率按当前条件刷新</div>
      </div>

      <div class="workbench-controls" aria-label="工作台筛选">
        <label class="control-field">
          <span>生产企业</span>
          <select v-model="query.manufacturerCode">
            <option v-for="item in options.manufacturerOptions" :key="item.code" :value="item.code">
              {{ item.name }}
            </option>
          </select>
        </label>
        <label class="control-field">
          <span>日报日期</span>
          <select v-model="query.runDate">
            <option v-for="item in options.dailyDetectorDateOptions" :key="item.runDate" :value="item.runDate">
              {{ item.label }}
            </option>
          </select>
        </label>
      </div>
    </div>

    <section class="workbench-hero panel">
      <div>
        <span class="eyebrow">月报主风险 + 日报巡检</span>
        <h2>今日重点风险对象</h2>
        <p>
          按当前生产企业、日报日期和预测窗口展示医院 × 药品对象。丢失概率来自月报结果；今日变化来自规则巡检线索。
        </p>
      </div>
      <div class="batch-card">
        <div class="batch-row"><span>生产企业</span><strong>{{ state.scope.manufacturerName || state.scope.manufacturerCode }}</strong></div>
        <div class="batch-row"><span>月报月份</span><strong>{{ query.reportMonth }}</strong></div>
        <div class="batch-row"><span>日报日期</span><strong>{{ query.runDate }}</strong></div>
        <div class="batch-row"><span>当前窗口</span><strong>{{ options.horizonOptions.find((item) => item.id === query.horizon)?.label }}</strong></div>
        <div class="batch-row"><span>数据来源</span><strong>{{ state.displayLookupStatus.label }}</strong></div>
      </div>
    </section>

    <SectionCard title="工作台设置" subtitle="切换后同步刷新当前列表与详情">
      <div class="control-grid">
        <div class="control-group">
          <span class="control-label">预测窗口</span>
          <div class="segmented-control">
            <button
              v-for="item in options.horizonOptions"
              :key="item.id"
              type="button"
              class="segment-btn"
              :class="{ active: query.horizon === item.id }"
              @click="query.horizon = item.id"
            >
              {{ item.label }}
            </button>
          </div>
        </div>
        <label class="control-field">
          <span>显示数量</span>
          <select v-model.number="query.topN">
            <option v-for="item in options.topNOptions" :key="item" :value="item">Top {{ item }}</option>
          </select>
        </label>
        <label class="control-field">
          <span>排序</span>
          <select v-model="query.sortBy">
            <option v-for="item in options.sortOptions" :key="item.id" :value="item.id">
              {{ item.label }}
            </option>
          </select>
        </label>
      </div>
    </SectionCard>

    <div class="grid-4">
      <MetricCard
        v-for="item in state.overviewMetrics"
        :key="item.label"
        :label="item.label"
        :value="item.value"
        :tone="item.tone"
      />
    </div>

    <SectionCard title="今日巡检线索" subtitle="日报日期对应当天巡检批次">
      <div class="grid-4">
        <MetricCard
          v-for="item in dailyDetectorMetrics"
          :key="item.label"
          :label="item.label"
          :value="item.value"
          :tone="item.tone"
        />
      </div>
      <div class="detector-status-row">
        <span class="status-badge status-badge-neutral">{{ state.dailyDetectorStatus.sourceLabel }}</span>
        <strong>{{ state.dailyDetectorStatus.statusText }}</strong>
        <span>{{ state.dailyDetectorStatus.caveat }}</span>
      </div>
    </SectionCard>

    <SectionCard title="今日重点风险对象" :subtitle="`按${options.sortOptions.find((item) => item.id === query.sortBy)?.label || '当前条件'}排序`">
      <div class="table-toolbar">
        <span class="status-badge status-badge-neutral" v-if="isLoading">刷新中</span>
        <span class="muted">按当前条件展示 Top {{ query.topN }} 对象</span>
      </div>
      <div class="data-table-wrap">
        <table>
          <thead>
            <tr>
              <th>排序</th>
              <th>生产企业</th>
              <th>医院 × 药品</th>
              <th>来源</th>
              <th>丢失概率</th>
              <th>涉及金额</th>
              <th>动作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in state.workbenchDisplayRows" :key="row.id">
              <td><strong>#{{ index + 1 }}</strong></td>
              <td>{{ row.manufacturer }}</td>
              <td>
                <strong>{{ row.hospitalDrugKey }}</strong>
                <div class="muted">{{ row.region }}</div>
              </td>
              <td>
                <span class="status-badge status-badge-info">{{ row.sourceType }}</span>
                <div class="muted">{{ row.fillSource }}</div>
              </td>
              <td>{{ row.probabilityDisplay }}</td>
              <td><strong>{{ row.involvedAmountText }}</strong></td>
              <td>
                <a v-if="row.entityId" class="btn btn-primary btn-sm" :href="detailHref(row)">查看详情</a>
                <span v-else class="status-badge status-badge-neutral">{{ row.action }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </SectionCard>
  </div>
</template>
