<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import SectionCard from '../../components/SectionCard.vue'
import SquareDatePicker from '../../components/ui/SquareDatePicker.vue'
import {
  applyReportContextToQuery,
  buildPersistentParams,
  createEmptyRuleCluesData,
  createEmptyWorkbenchOptions,
  loadReportContext,
  loadRuleCluesData,
  loadWorkbenchOptions,
  normalizeWorkbenchQuery
} from '../monthly-demo/pageDataAdapter'

const params = new URLSearchParams(window.location.search)
const draftQuery = reactive(
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

const query = draftQuery
const appliedQuery = ref(normalizeWorkbenchQuery(draftQuery))
const options = ref(createEmptyWorkbenchOptions(draftQuery))
const manufacturerCatalog = ref([])
const state = ref(createEmptyRuleCluesData(appliedQuery.value))
const reportContext = ref(state.value.reportContext)
const activeFilter = ref('all')
const selectedDetectorFamily = ref(query.detectorFamily || 'all')
const selectedDetectorId = ref(query.detectorId || 'all')
const isLoading = ref(false)
let requestSequence = 0
let initializedManufacturer = Boolean(query.manufacturerCode)

const filterTabs = [
  { id: 'all', label: '全部规则线索' },
  { id: 'monthly', label: '月报高风险' },
  { id: 'rule_only', label: '仅规则命中' }
]

const selectedHorizonLabel = computed(() => options.value.horizonOptions.find((item) => item.id === query.horizon)?.label || query.horizon)
const availableObservationDates = computed(() => options.value.dailyDetectorDateOptions?.map((item) => item.id).filter(Boolean) || [])
const detectorFamilyOptions = computed(() => {
  const families = [...new Map((options.value.detectorCatalog || []).map((item) => [
    item.detectorFamily,
    { id: item.detectorFamily, label: item.detectorFamilyLabel || item.detectorFamily }
  ])).values()].filter((item) => item.id)
  return [{ id: 'all', label: '全部大类' }, ...families]
})
const detectorIdOptions = computed(() => {
  const catalog = selectedDetectorFamily.value === 'all'
    ? options.value.detectorCatalog || []
    : (options.value.detectorCatalog || []).filter((item) => item.detectorFamily === selectedDetectorFamily.value)
  return [{ id: 'all', label: '全部小类' }, ...catalog.map((item) => ({ id: item.detectorId, label: item.detectorName || item.detectorId }))]
})
const filteredClues = computed(() => {
  const items = state.value.dailyDetectorClues || []
  if (activeFilter.value === 'monthly') return items.filter((item) => item.isMonthlyHighRiskEntity)
  if (activeFilter.value === 'rule_only') return items.filter((item) => !item.isMonthlyHighRiskEntity)
  return items
})

function detailHref(clue) {
  const next = buildPersistentParams(appliedQuery.value, { clueId: clue.id })
  if (clue.riskEntityId) next.set('id', clue.riskEntityId)
  return `clue-detail.html?${next.toString()}`
}

function updateUrl() {
  window.history.replaceState({}, '', `${window.location.pathname}?${buildPersistentParams(appliedQuery.value).toString()}`)
}

function syncDraftContext() {
  window.history.replaceState({}, '', `${window.location.pathname}?${buildPersistentParams(draftQuery).toString()}`)
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
    query.manufacturerCode = nextManufacturer
  }
}

async function loadOptions() {
  const loadedOptions = await loadWorkbenchOptions(draftQuery)
  applyLoadedOptions(loadedOptions, draftQuery)
}

async function submitQuery() {
  const sequence = ++requestSequence
  isLoading.value = true
  try {
    draftQuery.detectorFamily = selectedDetectorFamily.value === 'all' ? '' : selectedDetectorFamily.value
    draftQuery.detectorId = selectedDetectorId.value === 'all' ? '' : selectedDetectorId.value
    if (draftQuery.demoMode) {
      options.value = await loadWorkbenchOptions(draftQuery, { allowDemo: true })
      state.value = await loadRuleCluesData(draftQuery, { allowDemo: true })
      appliedQuery.value = normalizeWorkbenchQuery(draftQuery)
      reportContext.value = state.value.reportContext
      updateUrl()
      return
    }

    const context = await loadReportContext(draftQuery)
    if (sequence !== requestSequence) return
    reportContext.value = context
    if (!context.ready) {
      state.value = createEmptyRuleCluesData(draftQuery, context)
      appliedQuery.value = normalizeWorkbenchQuery(draftQuery)
      updateUrl()
      return
    }

    const effectiveQuery = applyReportContextToQuery(draftQuery, context)
    Object.assign(draftQuery, effectiveQuery)
    appliedQuery.value = normalizeWorkbenchQuery(effectiveQuery)
    const [refreshedOptions, loadedData] = await Promise.all([
      loadWorkbenchOptions(effectiveQuery),
      loadRuleCluesData(effectiveQuery)
    ])
    if (sequence !== requestSequence) return
    applyLoadedOptions(refreshedOptions, effectiveQuery)
    state.value = loadedData || createEmptyRuleCluesData(effectiveQuery, context)
    reportContext.value = state.value.reportContext || context
  } finally {
    if (sequence === requestSequence) {
      isLoading.value = false
    }
  }
}

onMounted(loadOptions)

watch(draftQuery, syncDraftContext, { deep: true })

watch(selectedDetectorFamily, () => {
  selectedDetectorId.value = 'all'
  draftQuery.detectorFamily = selectedDetectorFamily.value === 'all' ? '' : selectedDetectorFamily.value
  draftQuery.detectorId = ''
})

watch(selectedDetectorId, () => {
  draftQuery.detectorId = selectedDetectorId.value === 'all' ? '' : selectedDetectorId.value
})
</script>

<template>
  <div class="page-shell">
    <div class="page-header control-header">
      <div>
        <h1>规则巡检结果</h1>
        <div class="subtitle">{{ query.observationDate }} · 规则巡检 · {{ selectedHorizonLabel }}</div>
      </div>
      <div class="workbench-controls">
        <label class="control-field">
          <span>生产企业</span>
          <select v-model="query.manufacturerCode">
            <option v-for="item in options.manufacturerOptions" :key="item.code" :value="item.code">{{ item.name }}</option>
          </select>
        </label>
        <SquareDatePicker v-model="query.observationDate" label="观察日期" :available-dates="availableObservationDates" />
      </div>
    </div>

    <section v-if="reportContext?.displayTitle" class="notice-strip context-notice">
      <strong>{{ reportContext.displayTitle }}</strong>
      <span v-for="line in reportContext.displayLines" :key="line">{{ line }}</span>
    </section>

    <section class="panel clue-hero">
      <div>
        <span class="eyebrow">规则巡检结果</span>
        <h2>全部规则线索</h2>
        <p>
          月报高风险对象上的规则命中会附着到风险卡；未进入月报高风险清单但被规则命中的对象，仅作为规则巡检结果展示。
        </p>
      </div>
      <div class="batch-card">
        <div class="batch-row"><span>观察日期</span><strong>{{ query.observationDate }}</strong></div>
        <div class="batch-row"><span>规则命中数</span><strong>{{ state.dailyDetectorStatus.clueCount }}</strong></div>
        <div class="batch-row"><span>已附着证据</span><strong>{{ state.dailyDetectorStatus.attachedHighRiskCount }}</strong></div>
        <div class="batch-row"><span>数据状态</span><strong>{{ state.dailyDetectorStatus.sourceLabel }}</strong></div>
      </div>
    </section>

    <SectionCard title="线索筛选" subtitle="按规则大类、小类与命中来源查看巡检结果">
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
          <span>规则大类</span>
          <select v-model="selectedDetectorFamily">
            <option v-for="item in detectorFamilyOptions" :key="item.id" :value="item.id">{{ item.label }}</option>
          </select>
        </label>
        <label class="control-field">
          <span>规则小类</span>
          <select v-model="selectedDetectorId">
            <option v-for="item in detectorIdOptions" :key="item.id" :value="item.id">{{ item.label }}</option>
          </select>
        </label>
        <div class="segmented-control">
          <button
            v-for="tab in filterTabs"
            :key="tab.id"
            type="button"
            class="segment-btn"
            :class="{ active: activeFilter === tab.id }"
            @click="activeFilter = tab.id"
          >
            <strong>{{ tab.label }}</strong>
          </button>
        </div>
        <button type="button" class="btn btn-primary" :disabled="isLoading" @click="submitQuery">{{ isLoading ? '查询中…' : '查询' }}</button>
      </div>
    </SectionCard>

    <SectionCard title="规则巡检结果" subtitle="展示 detector 命中的 entity；区分月报高风险与仅规则命中对象">
      <div v-if="isLoading" class="empty">刷新中</div>
      <div v-else-if="!filteredClues.length" class="empty">
        <strong>{{ state.emptyTitle }}</strong>
        <p>{{ state.emptyMessage }}</p>
      </div>
      <div v-else class="data-table-wrap">
        <table>
          <thead>
            <tr>
              <th>线索类型</th>
              <th>医院 × 药品</th>
              <th>规则</th>
              <th>规则巡检分</th>
              <th>月报信息</th>
              <th>证据摘要</th>
              <th>动作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="clue in filteredClues" :key="clue.id">
              <td>
                <span class="status-badge" :class="clue.isMonthlyHighRiskEntity ? 'status-badge-error' : 'status-badge-neutral'">
                  {{ clue.sourceTypeLabel }}
                </span>
              </td>
              <td>
                <strong>{{ clue.hospital }} × {{ clue.drug }}</strong>
                <div class="muted">{{ clue.region }} · {{ clue.manufacturer }}</div>
              </td>
              <td>
                <strong>{{ clue.detectorName }}</strong>
                <div class="muted">{{ clue.detectorFamilyLabel }} · {{ clue.detectorLevel }}</div>
              </td>
              <td>
                <strong>{{ clue.detectorScoreText }}</strong>
                <div class="muted">{{ clue.detectorScoreLabel }}</div>
              </td>
              <td>
                <template v-if="clue.isMonthlyHighRiskEntity">
                  <span>丢失概率 {{ clue.monthlyRiskProbabilityText }}</span>
                  <div class="muted">涉及金额 {{ clue.involvedAmountText }}</div>
                </template>
                <span v-else class="muted">仅规则命中，按 detector 证据单独观察</span>
              </td>
              <td class="narrative-cell">
                <strong>{{ clue.rootCauseLabel }}</strong>
                <div class="muted">{{ clue.evidenceText }}</div>
              </td>
              <td><a class="btn btn-primary btn-sm" :href="detailHref(clue)">{{ clue.actionText }}</a></td>
            </tr>
          </tbody>
        </table>
      </div>
    </SectionCard>
  </div>
</template>
