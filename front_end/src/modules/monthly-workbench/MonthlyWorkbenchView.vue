<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import MetricCard from '../../components/MetricCard.vue'
import SectionCard from '../../components/SectionCard.vue'
import SquareDatePicker from '../../components/ui/SquareDatePicker.vue'
import {
  applyReportContextToQuery,
  buildPersistentParams,
  createEmptyWorkbenchData,
  createEmptyWorkbenchOptions,
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
    observationDate: urlParams.get('observation_date'),
    manufacturerCode: urlParams.get('manufacturer_code'),
    reportMonth: urlParams.get('report_month'),
    runDate: urlParams.get('run_date'),
    probabilityReportMonth: urlParams.get('probability_report_month'),
    detectorRunDate: urlParams.get('detector_run_date'),
    horizon: urlParams.get('horizon') || urlParams.get('h'),
    topN: Number(urlParams.get('top_n')),
    sortBy: urlParams.get('sort_by')
  })
)

const options = ref(createEmptyWorkbenchOptions(query))
const manufacturerCatalog = ref([])
const state = ref(createEmptyWorkbenchData(query))
const reportContext = ref(state.value.reportContext)
const isLoading = ref(false)
let suppressWatcher = false
let requestSequence = 0
let initializedManufacturer = Boolean(query.manufacturerCode)

const todayMetrics = computed(() => state.value.overviewMetrics || [])
const selectedHorizonLabel = computed(() => options.value.horizonOptions.find((item) => item.id === query.horizon)?.label || query.horizon)
const selectedSortLabel = computed(() => options.value.sortOptions.find((item) => item.id === query.sortBy)?.label || '当前条件')
const hasRows = computed(() => (state.value.workbenchDisplayRows || []).length > 0)
const availableObservationDates = computed(() => (options.value.dailyDetectorDateOptions || []).map((item) => item.runDate).filter(Boolean))

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

function applyLoadedOptions(loadedOptions, fallbackQuery = query) {
  const nextOptions = loadedOptions || createEmptyWorkbenchOptions(fallbackQuery)
  if (nextOptions.manufacturerOptions?.length) {
    manufacturerCatalog.value = nextOptions.manufacturerOptions
  }
  options.value = {
    ...nextOptions,
    manufacturerOptions: manufacturerCatalog.value.length ? manufacturerCatalog.value : nextOptions.manufacturerOptions
  }
  const codes = (options.value.manufacturerOptions || []).map((item) => item.code).filter(Boolean)
  if (!initializedManufacturer && !query.manufacturerCode && codes.length) {
    const nextManufacturer = codes.includes(options.value.defaultManufacturerCode) ? options.value.defaultManufacturerCode : codes[0]
    initializedManufacturer = true
    applyEffectiveQuery({ ...query, manufacturerCode: nextManufacturer })
  }
}

async function refreshWorkbench() {
  const sequence = ++requestSequence
  isLoading.value = true
  try {
    if (query.demoMode) {
      const demoOptions = await loadWorkbenchOptions(query, { allowDemo: true })
      const demoData = await loadWorkbenchData(query, { allowDemo: true })
      if (sequence !== requestSequence) return
      options.value = demoOptions
      state.value = demoData
      reportContext.value = state.value.reportContext
      updateUrl()
      return
    }

    const loadedOptions = await loadWorkbenchOptions(query)
    if (sequence !== requestSequence) return
    applyLoadedOptions(loadedOptions, query)

    const context = await loadReportContext(query)
    if (sequence !== requestSequence) return
    reportContext.value = context
    if (!context.ready) {
      state.value = createEmptyWorkbenchData(query, context)
      updateUrl()
      return
    }

    const effectiveQuery = applyReportContextToQuery(query, context)
    applyEffectiveQuery(effectiveQuery)
    const [refreshedOptions, loadedData] = await Promise.all([
      loadWorkbenchOptions(effectiveQuery),
      loadWorkbenchData(effectiveQuery)
    ])
    if (sequence !== requestSequence) return
    applyLoadedOptions(refreshedOptions, effectiveQuery)
    if (!responseMatchesQuery(loadedData, effectiveQuery)) return
    state.value = loadedData || createEmptyWorkbenchData(effectiveQuery, context)
    reportContext.value = state.value.reportContext || context
  } finally {
    isLoading.value = false
  }
}

function responseMatchesQuery(loadedData, expectedQuery) {
  if (!loadedData?.query) return true
  return loadedData.query.manufacturerCode === expectedQuery.manufacturerCode &&
    loadedData.query.horizon === expectedQuery.horizon &&
    loadedData.query.sortBy === expectedQuery.sortBy
}

onMounted(refreshWorkbench)

watch(
  () => [query.manufacturerCode, query.observationDate, query.horizon, query.topN, query.sortBy, query.backendBaseUrl, query.userId, query.demoMode],
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
        <SquareDatePicker
          v-model="query.observationDate"
          label="观察日期"
          :available-dates="availableObservationDates"
        />
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
        <div class="batch-row"><span>观察日期</span><strong>{{ query.observationDate }}</strong></div>
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

    <SectionCard title="今日重点风险对象" :subtitle="`按 ${selectedSortLabel} 排序`">
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
