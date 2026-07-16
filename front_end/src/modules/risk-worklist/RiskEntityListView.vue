<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import SectionCard from '../../components/SectionCard.vue'
import SquareDatePicker from '../../components/ui/SquareDatePicker.vue'
import DetectorCardFilterPanel from './DetectorCardFilterPanel.vue'
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
    detectorCategory: params.get('detector_category'),
    detectorId: params.get('detector_id'),
    detectorLevel: params.get('detector_level'),
    horizon: params.get('horizon') || params.get('h'),
    topN: Number(params.get('top_n')),
    sortBy: params.get('sort_by'),
    sortOrder: params.get('sort_order'),
    page: Number(params.get('page')),
    pageSize: Number(params.get('page_size'))
  })
)

const query = draftQuery
const appliedQuery = ref(normalizeWorkbenchQuery(draftQuery))
const options = ref(createEmptyWorkbenchOptions(draftQuery))
const state = ref(createEmptyRuleCluesData(appliedQuery.value))
const reportContext = ref(state.value.reportContext)
const selectedDetectorFamily = ref(query.detectorCategory || 'all')
const selectedDetectorId = ref(query.detectorId || 'all')
const selectedDetectorLevel = ref(query.detectorLevel || 'all')
const selectedSortBy = ref(query.sortBy === 'risk_probability' ? 'detector_score' : query.sortBy)
const selectedSortOrder = ref(query.sortOrder || 'desc')
const selectedRuleCategory = selectedDetectorFamily
const draftFilters = computed(() => ({
  detectorCategory: selectedRuleCategory.value === 'all' ? '' : selectedRuleCategory.value,
  detectorId: selectedDetectorId.value === 'all' ? '' : selectedDetectorId.value,
  detectorLevel: selectedDetectorLevel.value === 'all' ? '' : selectedDetectorLevel.value,
  sortBy: selectedSortBy.value,
  sortOrder: selectedSortOrder.value,
  pageSize: draftQuery.pageSize
}))
const appliedFilters = computed(() => ({
  detectorCategory: appliedQuery.value.detectorCategory,
  detectorId: appliedQuery.value.detectorId,
  detectorLevel: appliedQuery.value.detectorLevel,
  sortBy: appliedQuery.value.sortBy,
  sortOrder: appliedQuery.value.sortOrder,
  pageSize: appliedQuery.value.pageSize
}))
const isLoading = ref(false)
const hasSubmittedQuery = ref(false)
const manufacturerScope = useManufacturerScope()
const manufacturerCode = manufacturerScope.manufacturerCode
let requestSequence = 0
let pageReady = false

const availableObservationDates = computed(() => options.value.dailyDetectorDateOptions?.map((item) => item.id || item.runDate).filter(Boolean) || [])
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
const detectorFamilies = computed(() => {
  const summaries = {
    price: '识别采购价格低位、离散或相对历史水平发生明显变化的规则事实。',
    fulfillment: '识别配送和到货过程中的异常事实；当前受正式数据可用性约束。',
    terminal: '识别采购间隔、首次采购、恢复采购及终端结构变化事实。',
    sales: '识别采购数量与采购频次相对对象自身历史基准的变化。'
  }
  return RULE_CATEGORY_DEFINITIONS.map((definition) => ({
    ...definition,
    summary: summaries[definition.id],
    detectors: (options.value.detectorCatalog || []).filter(
      (item) => ruleCategoryForDetectorFamily(item.detectorFamily) === definition.id
    )
  }))
})
const displayedClues = computed(() => state.value.dailyDetectorClues || [])
const pagination = computed(() => state.value.pagination || { page: 1, pageSize: 20, total: 0, totalPages: 0 })
const appliedFilterSummary = computed(() => {
  if (!hasSubmittedQuery.value) return '尚未应用筛选条件'
  const labels = []
  if (appliedFilters.value.detectorCategory) {
    labels.push(ruleCategoryOptions.value.find((item) => item.id === appliedFilters.value.detectorCategory)?.label || appliedFilters.value.detectorCategory)
    labels.push(appliedFilters.value.detectorId
      ? (options.value.detectorCatalog || []).find((item) => item.detectorId === appliedFilters.value.detectorId)?.detectorName || appliedFilters.value.detectorId
      : '全部 Detector')
  } else {
    labels.push('全部规则')
  }
  if (appliedFilters.value.detectorLevel) labels.push(`命中等级 ${appliedFilters.value.detectorLevel}`)
  labels.push(`${formatCount(pagination.value.total)} 条结果`)
  return labels.join(' · ')
})
const emptyTitle = computed(() => hasSubmittedQuery.value ? state.value.emptyTitle : '请设置查询条件并点击查询')
const emptyMessage = computed(() => hasSubmittedQuery.value ? state.value.emptyMessage : '查询完成后将在此展示规则巡检结果。')
const showContextNotice = computed(() => hasSubmittedQuery.value && Boolean(reportContext.value?.displayTitle))

function detailHref(clue) {
  const next = buildPersistentParams(appliedQuery.value, {
    clueId: clue.id,
    manufacturerCode: clue.manufacturerCode || appliedQuery.value.manufacturerCode,
    hospitalCode: clue.hospitalCode,
    drugCode: clue.drugCode,
    observationDate: clue.detectorRunDate || appliedQuery.value.observationDate
  })
  return `clue-detail.html?${next.toString()}`
}

function formatCount(value) {
  return new Intl.NumberFormat('zh-CN').format(Number(value) || 0)
}

async function queryAllRules() {
  selectedRuleCategory.value = 'all'
  selectedDetectorId.value = 'all'
  await submitQuery(1)
}

async function queryRuleFamily(familyId) {
  selectedRuleCategory.value = familyId
  selectedDetectorId.value = 'all'
  await submitQuery(1)
}

async function queryDetector(familyId, detectorId) {
  selectedRuleCategory.value = familyId
  selectedDetectorId.value = detectorId
  await submitQuery(1)
}

function updateUrl() {
  window.history.replaceState({}, '', `${window.location.pathname}?${buildPersistentParams(appliedQuery.value).toString()}`)
}

function applyLoadedOptions(loadedOptions, fallbackQuery = query) {
  options.value = loadedOptions || createEmptyWorkbenchOptions(fallbackQuery)
}

async function loadOptions() {
  const loadedOptions = await loadWorkbenchOptions(draftQuery)
  applyLoadedOptions(loadedOptions, draftQuery)
}

async function submitQuery(targetPage = 1) {
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
    Object.assign(draftQuery, draftFilters.value)
    draftQuery.page = targetPage
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
    updateUrl()
  } finally {
    if (sequence === requestSequence) {
      isLoading.value = false
    }
  }
}

function resetFilters() {
  selectedRuleCategory.value = 'all'
  selectedDetectorId.value = 'all'
  selectedDetectorLevel.value = 'all'
  selectedSortBy.value = 'detector_score'
  selectedSortOrder.value = 'desc'
}

async function goToPage(page) {
  if (isLoading.value || page < 1 || page > pagination.value.totalPages) return
  await submitQuery(page)
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

watch(manufacturerCode, async (nextCode) => {
  if (!pageReady || !nextCode || nextCode === query.manufacturerCode) return
  query.manufacturerCode = nextCode
  await submitQuery()
})

watch(selectedRuleCategory, () => {
  selectedDetectorId.value = 'all'
  draftQuery.detectorCategory = selectedDetectorFamily.value === 'all' ? '' : selectedDetectorFamily.value
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
        <div class="batch-row"><span>当日规则命中记录</span><strong>{{ formatCount(state.dailyDetectorStatus.clueCount) }}</strong></div>
        <div class="batch-row"><span>数据状态</span><strong>{{ state.dailyDetectorStatus.sourceLabel }}</strong></div>
      </div>
    </section>

    <SectionCard title="线索筛选" subtitle="浏览大类不会请求；点击查询按钮后才会应用到下方结果">
      <DetectorCardFilterPanel
        :families="detectorFamilies"
        :applied-family="appliedFilters.detectorCategory"
        :applied-detector="appliedFilters.detectorId"
        :loading="isLoading"
        @query-all="queryAllRules"
        @query-family="queryRuleFamily"
        @query-detector="queryDetector"
      />
      <div class="control-grid">
        <label class="control-field">
          <span>命中等级</span>
          <select v-model="selectedDetectorLevel">
            <option value="all">全部等级</option>
            <option value="high">高</option>
            <option value="medium">中</option>
            <option value="low">低</option>
          </select>
        </label>
        <label class="control-field">
          <span>排序字段</span>
          <select v-model="selectedSortBy">
            <option value="detector_score">规则巡检分</option>
            <option value="confidence">置信度</option>
            <option value="created_at">生成时间</option>
          </select>
        </label>
        <label class="control-field">
          <span>排序方向</span>
          <select v-model="selectedSortOrder"><option value="desc">降序</option><option value="asc">升序</option></select>
        </label>
        <label class="control-field">
          <span>每页条数</span>
          <select v-model.number="draftQuery.pageSize"><option :value="20">20</option><option :value="50">50</option><option :value="100">100</option></select>
        </label>
        <button type="button" class="btn btn-primary" :disabled="isLoading" @click="submitQuery(1)">{{ isLoading ? '查询中…' : '应用辅助条件' }}</button>
        <button type="button" class="btn" :disabled="isLoading" @click="resetFilters">重置</button>
      </div>
      <div class="detector-filter-summary">
        <strong>当前结果范围</strong>
        <span>生产企业：{{ manufacturerCode || '-' }}</span>
        <span>观察日期：{{ appliedQuery.observationDate || '-' }}</span>
        <span>规则范围：{{ appliedFilterSummary }}</span>
      </div>
    </SectionCard>

    <SectionCard title="当前筛选结果" subtitle="同一医院—药品可能命中多条规则，因此规则命中记录数不等于实体数。">
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
              <th>命中规则</th>
              <th>命中等级</th>
              <th>关键证据</th>
              <th>观察日期</th>
              <th>动作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="clue in displayedClues" :key="clue.id">
              <td>
                <strong>{{ clue.hospital }} × {{ clue.drug }}</strong>
                <div class="muted">{{ clue.hospitalCode }} · {{ clue.drugCode }}</div>
                <div v-if="clue.manufacturerNameAvailable" class="muted">{{ clue.region }} · {{ clue.manufacturer }} · {{ clue.manufacturerCode }}</div>
                <div v-else class="muted">生产企业编码：{{ clue.manufacturerCode }} · 名称：--</div>
              </td>
              <td>
                <strong>{{ clue.detectorName }}</strong>
                <div class="muted">{{ clue.detectorFamilyLabel }} · {{ clue.detectorId }}</div>
                <div class="muted">规则巡检分 {{ clue.detectorScoreText }}（非概率）</div>
              </td>
              <td>
                <strong>{{ clue.detectorLevel }}</strong>
              </td>
              <td class="narrative-cell">
                <strong>{{ clue.rootCauseLabel }}</strong>
                <div class="muted">{{ clue.evidenceText }}</div>
              </td>
              <td>{{ clue.detectorRunDate || appliedQuery.observationDate }}</td>
              <td><a class="btn btn-sm" :href="detailHref(clue)">查看实体证据</a></td>
            </tr>
          </tbody>
        </table>
        <div class="pagination-row">
          <button type="button" class="btn btn-sm" :disabled="pagination.page <= 1 || isLoading" @click="goToPage(pagination.page - 1)">上一页</button>
          <span>第 {{ pagination.page }} / {{ pagination.totalPages || 1 }} 页，共 {{ formatCount(pagination.total) }} 条</span>
          <button type="button" class="btn btn-sm" :disabled="pagination.page >= pagination.totalPages || isLoading" @click="goToPage(pagination.page + 1)">下一页</button>
        </div>
      </div>
    </SectionCard>
  </div>
</template>

<style scoped>
.detector-filter-summary { display: flex; flex-wrap: wrap; gap: 8px 18px; margin-top: 18px; padding: 14px 16px; border-left: 3px solid #3b82f6; background: #f6f8fb; }
.detector-filter-summary strong { flex-basis: 100%; }
.clue-hero { align-items: center; padding-block: 20px; }
.narrative-cell { min-width: 260px; }
</style>
