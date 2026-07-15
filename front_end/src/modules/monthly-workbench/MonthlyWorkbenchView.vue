<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import SectionCard from '../../components/SectionCard.vue'
import SquareDatePicker from '../../components/ui/SquareDatePicker.vue'
import { useManufacturerScope } from '../../context/manufacturerScope'
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

const params = new URLSearchParams(window.location.search)
const draftQuery = reactive(normalizeWorkbenchQuery({
  backendBaseUrl: params.get('backendBaseUrl'),
  userId: params.get('user_id') || params.get('userId'),
  demoMode: params.get('demoMode'),
  observationDate: params.get('observation_date'),
  manufacturerCode: params.get('manufacturer_code'),
  reportMonth: params.get('report_month'),
  probabilityReportMonth: params.get('probability_report_month'),
  horizon: params.get('horizon'),
  topN: Number(params.get('top_n')),
  sortBy: params.get('sort_by')
}))
const appliedQuery = ref(normalizeWorkbenchQuery(draftQuery))
const options = ref(createEmptyWorkbenchOptions(draftQuery))
const state = ref(createEmptyWorkbenchData(appliedQuery.value))
const reportContext = ref(state.value.reportContext)
const isLoading = ref(false)
const hasSubmittedQuery = ref(false)
const manufacturerScope = useManufacturerScope()
const manufacturerCode = manufacturerScope.manufacturerCode
let requestSequence = 0
let pageReady = false

const rows = computed(() => state.value.workbenchDisplayRows || [])
const emptyTitle = computed(() => hasSubmittedQuery.value ? state.value.emptyTitle : '请设置查询条件并点击查询')
const emptyMessage = computed(() => hasSubmittedQuery.value ? state.value.emptyMessage : '查询完成后将在此展示正式月度候选结果。')
const showContextNotice = computed(() => hasSubmittedQuery.value && Boolean(reportContext.value?.displayTitle))
const selectedHorizonLabel = computed(() => options.value.horizonOptions.find((item) => item.id === appliedQuery.value.horizon)?.label || appliedQuery.value.horizon)
const availableObservationDates = computed(() => (options.value.dailyDetectorDateOptions || []).map((item) => item.runDate).filter(Boolean))

function updateUrl() {
  window.history.replaceState({}, '', `${window.location.pathname}?${buildPersistentParams(appliedQuery.value).toString()}`)
}

function syncDraftContext() {
  window.history.replaceState({}, '', `${window.location.pathname}?${buildPersistentParams(draftQuery).toString()}`)
}

function detailHref(row) {
  return `clue-detail.html?${buildPersistentParams(appliedQuery.value, { id: row.entityId }).toString()}`
}

function cluesHref() {
  return `clues.html?${buildPersistentParams({
    ...appliedQuery.value,
    manufacturerCode: manufacturerCode.value
  }).toString()}`
}

async function loadOptions() {
  const loaded = await loadWorkbenchOptions(draftQuery)
  options.value = loaded || createEmptyWorkbenchOptions(draftQuery)
}

async function submitQuery() {
  const sequence = ++requestSequence
  const manufacturerChanged = appliedQuery.value.manufacturerCode !== draftQuery.manufacturerCode
  hasSubmittedQuery.value = true
  isLoading.value = true
  if (manufacturerChanged) options.value = createEmptyWorkbenchOptions(draftQuery)
  try {
    const [context, refreshedOptions] = await Promise.all([
      loadReportContext(draftQuery),
      manufacturerChanged ? loadWorkbenchOptions(draftQuery) : Promise.resolve(null)
    ])
    if (sequence !== requestSequence) return
    if (refreshedOptions) options.value = refreshedOptions
    const effective = applyReportContextToQuery(draftQuery, context)
    appliedQuery.value = effective
    reportContext.value = context
    const loadedState = await loadWorkbenchData(effective)
    if (sequence !== requestSequence) return
    state.value = loadedState
    reportContext.value = loadedState.reportContext || context
    updateUrl()
  } finally {
    if (sequence === requestSequence) isLoading.value = false
  }
}

onMounted(async () => {
  await manufacturerScope.initialize()
  draftQuery.manufacturerCode = manufacturerCode.value
  await loadOptions()
  pageReady = true
  if (manufacturerCode.value && manufacturerCode.value !== draftQuery.manufacturerCode) {
    draftQuery.manufacturerCode = manufacturerCode.value
    await submitQuery()
  }
})

watch(draftQuery, syncDraftContext, { deep: true })

watch(manufacturerCode, async (nextCode) => {
  if (!pageReady || !nextCode || nextCode === draftQuery.manufacturerCode) return
  draftQuery.manufacturerCode = nextCode
  await submitQuery()
})
</script>

<template>
  <div class="page-shell monthly-workbench">
    <div class="page-header control-header">
      <div>
        <h1>候选对象排序工作台</h1>
        <div class="subtitle">月度排序结果 Top N；规则证据仅在对象详情页展示</div>
      </div>
      <div class="workbench-controls">
        <SquareDatePicker v-model="draftQuery.observationDate" label="观察日期" :available-dates="availableObservationDates" />
      </div>
    </div>

    <section v-if="showContextNotice" class="notice-strip context-notice">
      <strong>{{ reportContext.displayTitle }}</strong>
      <span v-for="line in reportContext.displayLines" :key="line">{{ line }}</span>
    </section>

    <SectionCard title="查询条件">
      <div class="control-grid">
        <div class="control-group">
          <span class="control-label">预测窗口</span>
          <div class="segmented-control">
            <button v-for="item in options.horizonOptions" :key="item.id" type="button" class="segment-btn" :class="{ active: draftQuery.horizon === item.id }" @click="draftQuery.horizon = item.id">{{ item.label }}</button>
          </div>
        </div>
        <label class="control-field">
          <span>展示数量</span>
          <select v-model.number="draftQuery.topN">
            <option v-for="item in options.topNOptions" :key="item" :value="item">Top {{ item }}</option>
          </select>
        </label>
        <label class="control-field">
          <span>排序</span>
          <select v-model="draftQuery.sortBy">
            <option v-for="item in options.sortOptions.filter((item) => item.id !== 'detector_score')" :key="item.id" :value="item.id">{{ item.label }}</option>
          </select>
        </label>
        <button type="button" class="btn btn-primary" :disabled="isLoading" @click="submitQuery">{{ isLoading ? '查询中…' : '查询' }}</button>
      </div>
    </SectionCard>

    <SectionCard title="排序靠前候选对象" :subtitle="`${selectedHorizonLabel} · Top ${appliedQuery.topN}`">
      <div v-if="isLoading" class="empty">正在读取月度排序结果…</div>
      <div v-else-if="!rows.length" class="empty">
        <strong>{{ emptyTitle }}</strong>
        <p>{{ emptyMessage }}</p>
      </div>
      <div v-else class="data-table-wrap">
        <table>
          <thead><tr><th>排名</th><th>生产企业</th><th>医院 × 药品</th><th>月度概率</th><th>涉及金额</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="row in rows" :key="row.id">
              <td><strong>#{{ row.rank || '-' }}</strong></td>
              <td>{{ row.manufacturer }}</td>
              <td><strong>{{ row.hospitalDrugKey }}</strong><div class="muted">{{ row.region }}</div></td>
              <td>{{ row.probabilityDisplay }}</td>
              <td>{{ row.involvedAmountText }}</td>
              <td><a class="btn btn-primary btn-sm" :href="detailHref(row)">查看详情</a></td>
            </tr>
          </tbody>
        </table>
      </div>
      <a class="back-link" :href="cluesHref()">查看规则巡检结果</a>
    </SectionCard>
  </div>
</template>
