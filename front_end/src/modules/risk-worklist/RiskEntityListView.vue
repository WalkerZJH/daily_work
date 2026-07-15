<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import SectionCard from '../../components/SectionCard.vue'
import SquareDatePicker from '../../components/ui/SquareDatePicker.vue'
import { useManufacturerScope } from '../../context/manufacturerScope'
import {
  applyReportContextToQuery,
  buildPersistentParams,
  createEmptyRuleCluesData,
  createEmptyWorkbenchOptions,
  loadReportContext,
  loadRuleCluesData,
  loadWorkbenchOptions,
  normalizeWorkbenchQuery,
  RULE_CATEGORY_DEFINITIONS,
  ruleCategoryForDetectorFamily
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
const state = ref(createEmptyRuleCluesData(appliedQuery.value))
const reportContext = ref(state.value.reportContext)
const selectedDetectorFamily = ref(query.detectorFamily || 'all')
const selectedDetectorId = ref(query.detectorId || 'all')
const isLoading = ref(false)
const hasSubmittedQuery = ref(false)
const manufacturerScope = useManufacturerScope()
const manufacturerCode = manufacturerScope.manufacturerCode
let requestSequence = 0
let pageReady = false

const availableObservationDates = computed(() => options.value.dailyDetectorDateOptions?.map((item) => item.id).filter(Boolean) || [])
const selectedRuleCategory = selectedDetectorFamily
if (selectedRuleCategory.value === 'all') selectedDetectorId.value = 'all'
const ruleCategoryOptions = computed(() => [{ id: 'all', label: '全部大类' }, ...RULE_CATEGORY_DEFINITIONS.map((item) => ({
  id: item.id,
  label: item.unavailable ? `${item.label}（暂未实现）` : item.label,
  disabled: Boolean(item.unavailable)
}))])
const ruleSubtypeOptions = computed(() => {
  if (selectedRuleCategory.value === 'all') return [{ id: 'all', label: '全部小类' }]
  const catalog = selectedRuleCategory.value === 'all'
    ? options.value.detectorCatalog || []
    : (options.value.detectorCatalog || []).filter((item) => ruleCategoryForDetectorFamily(item.detectorFamily) === selectedRuleCategory.value)
  return [{ id: 'all', label: '全部小类' }, ...catalog.map((item) => ({ id: item.detectorId, label: item.detectorName || item.detectorId }))]
})
const displayedClues = computed(() => (state.value.dailyDetectorClues || []).filter((item) => selectedRuleCategory.value === 'all' || ruleCategoryForDetectorFamily(item.detectorFamily) === selectedRuleCategory.value))
const emptyTitle = computed(() => hasSubmittedQuery.value ? state.value.emptyTitle : '请设置查询条件并点击查询')
const emptyMessage = computed(() => hasSubmittedQuery.value ? state.value.emptyMessage : '查询完成后将在此展示规则巡检结果。')
const showContextNotice = computed(() => hasSubmittedQuery.value && Boolean(reportContext.value?.displayTitle))

function detailHref(clue) {
  const next = buildPersistentParams(appliedQuery.value, { clueId: clue.id })
  return `clue-detail.html?${next.toString()}`
}

function updateUrl() {
  window.history.replaceState({}, '', `${window.location.pathname}?${buildPersistentParams(appliedQuery.value).toString()}`)
}

function syncDraftContext() {
  window.history.replaceState({}, '', `${window.location.pathname}?${buildPersistentParams(draftQuery).toString()}`)
}

function applyLoadedOptions(loadedOptions, fallbackQuery = query) {
  options.value = loadedOptions || createEmptyWorkbenchOptions(fallbackQuery)
}

async function loadOptions() {
  const loadedOptions = await loadWorkbenchOptions(draftQuery)
  applyLoadedOptions(loadedOptions, draftQuery)
}

async function submitQuery() {
  const sequence = ++requestSequence
  const manufacturerChanged = appliedQuery.value.manufacturerCode !== draftQuery.manufacturerCode
  hasSubmittedQuery.value = true
  isLoading.value = true
  if (manufacturerChanged) {
    options.value = createEmptyWorkbenchOptions(draftQuery)
    state.value = createEmptyRuleCluesData(draftQuery)
  }
  try {
    draftQuery.detectorFamily = ''
    draftQuery.detectorId = selectedDetectorId.value === 'all' ? '' : selectedDetectorId.value
    if (draftQuery.demoMode) {
      const [loadedOptions, loadedState] = await Promise.all([
        loadWorkbenchOptions(draftQuery, { allowDemo: true }),
        loadRuleCluesData(draftQuery, { allowDemo: true })
      ])
      if (sequence !== requestSequence) return
      options.value = loadedOptions
      state.value = loadedState
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

onMounted(async () => {
  await manufacturerScope.initialize()
  query.manufacturerCode = manufacturerCode.value
  await loadOptions()
  pageReady = true
  if (manufacturerCode.value && manufacturerCode.value !== query.manufacturerCode) {
    query.manufacturerCode = manufacturerCode.value
    await submitQuery()
  }
})

watch(draftQuery, syncDraftContext, { deep: true })

watch(manufacturerCode, async (nextCode) => {
  if (!pageReady || !nextCode || nextCode === query.manufacturerCode) return
  query.manufacturerCode = nextCode
  await submitQuery()
})

watch(selectedRuleCategory, () => {
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
        <div class="subtitle">{{ query.observationDate }} · 规则巡检</div>
      </div>
      <div class="workbench-controls">
        <SquareDatePicker v-model="query.observationDate" label="观察日期" :available-dates="availableObservationDates" />
      </div>
    </div>

    <section v-if="showContextNotice" class="notice-strip context-notice">
      <strong>{{ reportContext.displayTitle }}</strong>
      <span v-for="line in reportContext.displayLines" :key="line">{{ line }}</span>
    </section>

    <section class="panel clue-hero">
      <div>
        <span class="eyebrow">规则巡检结果</span>
        <h2>全部规则线索</h2>
        <p>展示不同 detector 在指定观察上下文中命中的实体及其规则证据。</p>
      </div>
      <div class="batch-card">
        <div class="batch-row"><span>观察日期</span><strong>{{ query.observationDate }}</strong></div>
        <div class="batch-row"><span>规则命中数</span><strong>{{ state.dailyDetectorStatus.clueCount }}</strong></div>
        <div class="batch-row"><span>数据状态</span><strong>{{ state.dailyDetectorStatus.sourceLabel }}</strong></div>
      </div>
    </section>

    <SectionCard title="线索筛选" subtitle="按规则大类、小类与命中来源查看巡检结果">
      <div class="control-grid">
        <label class="control-field">
          <span>规则大类</span>
          <select v-model="selectedRuleCategory">
            <option v-for="item in ruleCategoryOptions" :key="item.id" :value="item.id" :disabled="item.disabled">{{ item.label }}</option>
          </select>
        </label>
        <label class="control-field">
          <span>规则小类</span>
          <select v-model="selectedDetectorId">
            <option v-for="item in ruleSubtypeOptions" :key="item.id" :value="item.id">{{ item.label }}</option>
          </select>
        </label>
        <button type="button" class="btn btn-primary" :disabled="isLoading" @click="submitQuery">{{ isLoading ? '查询中…' : '查询' }}</button>
      </div>
    </SectionCard>

    <SectionCard title="规则巡检结果" subtitle="展示 detector 命中的 entity 与规则证据">
      <div v-if="isLoading" class="empty">刷新中</div>
      <div v-else-if="!displayedClues.length" class="empty">
        <strong>{{ emptyTitle }}</strong>
        <p>{{ emptyMessage }}</p>
      </div>
      <div v-else class="data-table-wrap">
        <table>
          <thead>
            <tr>
              <th>医院 × 药品</th>
              <th>规则</th>
              <th>规则巡检分</th>
              <th>证据摘要</th>
              <th>动作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="clue in displayedClues" :key="clue.id">
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
