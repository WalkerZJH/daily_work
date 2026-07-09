<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import MetricCard from '../../components/MetricCard.vue'
import SectionCard from '../../components/SectionCard.vue'
import {
  applyReportContextToQuery,
  buildPersistentParams,
  createEmptyWorkbenchData,
  createEmptyWorkbenchOptions,
  createStaticWorkbenchData,
  createStaticWorkbenchOptions,
  loadReportContext,
  loadWorkbenchData,
  loadWorkbenchOptions,
  normalizeWorkbenchQuery
} from '../monthly-demo/pageDataAdapter'

const urlParams = new URLSearchParams(window.location.search)
const query = reactive(
  normalizeWorkbenchQuery({
    backendBaseUrl: urlParams.get('backendBaseUrl'),
    userId: urlParams.get('user_id') || urlParams.get('userId'),
    demoMode: urlParams.get('demoMode'),
    manufacturerCode: urlParams.get('manufacturer_code'),
    reportMonth: urlParams.get('report_month'),
    runDate: urlParams.get('run_date'),
    horizon: urlParams.get('horizon') || urlParams.get('h'),
    topN: Number(urlParams.get('top_n')),
    sortBy: urlParams.get('sort_by')
  })
)

const options = ref(query.demoMode ? createStaticWorkbenchOptions() : createEmptyWorkbenchOptions(query))
const state = ref(query.demoMode ? createStaticWorkbenchData(query) : createEmptyWorkbenchData(query))
const reportContext = ref(state.value.reportContext)
const isLoading = ref(false)
let suppressWatcher = false

const todayMetrics = computed(() => state.value.overviewMetrics || [])
const selectedHorizonLabel = computed(() => options.value.horizonOptions.find((item) => item.id === query.horizon)?.label || query.horizon)
const selectedSortLabel = computed(() => options.value.sortOptions.find((item) => item.id === query.sortBy)?.label || '当前条件')
const hasRows = computed(() => (state.value.workbenchDisplayRows || []).length > 0)

function detailHref(row) {
  const params = buildPersistentParams(query, { id: row.entityId })
  return `clue-detail.html?${params.toString()}`
}

function updateUrl() {
  const nextUrl = `${window.location.pathname}?${buildPersistentParams(query).toString()}`
  window.history.replaceState({}, '', nextUrl)
}

function applyEffectiveQuery(nextQuery) {
  suppressWatcher = true
  Object.assign(query, nextQuery)
  updateUrl()
  window.setTimeout(() => {
    suppressWatcher = false
  }, 0)
}

async function refreshWorkbench() {
  isLoading.value = true
  try {
    if (query.demoMode) {
      options.value = createStaticWorkbenchOptions()
      state.value = createStaticWorkbenchData(query)
      reportContext.value = state.value.reportContext
      updateUrl()
      return
    }

    const context = await loadReportContext(query)
    reportContext.value = context
    if (!context.ready) {
      options.value = createEmptyWorkbenchOptions(query)
      state.value = createEmptyWorkbenchData(query, context)
      updateUrl()
      return
    }

    const effectiveQuery = applyReportContextToQuery(query, context)
    applyEffectiveQuery(effectiveQuery)
    const [loadedOptions, loadedData] = await Promise.all([
      loadWorkbenchOptions(effectiveQuery),
      loadWorkbenchData(effectiveQuery)
    ])
    options.value = loadedOptions || createEmptyWorkbenchOptions(effectiveQuery)
    state.value = loadedData || createEmptyWorkbenchData(effectiveQuery, context)
    reportContext.value = state.value.reportContext || context
  } finally {
    isLoading.value = false
  }
}

onMounted(refreshWorkbench)

watch(
  () => [query.manufacturerCode, query.runDate, query.horizon, query.topN, query.sortBy, query.backendBaseUrl, query.userId, query.demoMode],
  () => {
    if (!suppressWatcher) refreshWorkbench()
  }
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
          <span>观察日期</span>
          <select v-model="query.runDate">
            <option v-for="item in options.dailyDetectorDateOptions" :key="item.runDate" :value="item.runDate">
              {{ item.label }}
            </option>
          </select>
        </label>
      </div>
    </div>

    <section v-if="reportContext?.displayTitle" class="notice-strip context-notice">
      <strong>{{ reportContext.displayTitle }}</strong>
      <span v-for="line in reportContext.displayLines" :key="line">{{ line }}</span>
    </section>

    <section class="workbench-hero panel">
      <div>
        <span class="eyebrow">月报主风险 + 日报巡检</span>
        <h2>今日重点</h2>
        <p>
          按当前生产企业、观察日期和预测窗口展示医院 × 药品对象。丢失概率来自月报结果；今日变化来自规则巡检线索。
        </p>
      </div>
      <div class="batch-card">
        <div class="batch-row"><span>生产企业</span><strong>{{ state.scope.manufacturerName || state.scope.manufacturerCode }}</strong></div>
        <div class="batch-row"><span>观察日期</span><strong>{{ query.runDate }}</strong></div>
        <div class="batch-row"><span>月报月份</span><strong>{{ query.reportMonth }}</strong></div>
        <div class="batch-row"><span>预测窗口</span><strong>{{ selectedHorizonLabel }}</strong></div>
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
        v-for="item in todayMetrics"
        :key="item.label"
        :label="item.label"
        :value="item.value"
        :tone="item.tone"
      />
    </div>

    <SectionCard title="今日重点风险对象" :subtitle="`按${selectedSortLabel}排序`">
      <div class="table-toolbar">
        <span class="status-badge status-badge-neutral" v-if="isLoading">刷新中</span>
        <span class="muted">按当前条件展示 Top {{ query.topN }} 对象</span>
      </div>
      <div v-if="!hasRows && !isLoading" class="empty">
        <strong>{{ state.emptyTitle }}</strong>
        <p>{{ state.emptyMessage }}</p>
      </div>
      <div v-else class="data-table-wrap">
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
