<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import SectionCard from '../../components/SectionCard.vue'
import {
  applyReportContextToQuery,
  buildPersistentParams,
  createEmptyRuleCluesData,
  createEmptyWorkbenchOptions,
  createStaticRuleCluesData,
  createStaticWorkbenchOptions,
  loadReportContext,
  loadRuleCluesData,
  loadWorkbenchOptions,
  normalizeWorkbenchQuery
} from '../monthly-demo/pageDataAdapter'

const params = new URLSearchParams(window.location.search)
const query = reactive(
  normalizeWorkbenchQuery({
    backendBaseUrl: params.get('backendBaseUrl'),
    userId: params.get('user_id') || params.get('userId'),
    demoMode: params.get('demoMode'),
    manufacturerCode: params.get('manufacturer_code'),
    reportMonth: params.get('report_month'),
    runDate: params.get('run_date'),
    horizon: params.get('horizon') || params.get('h'),
    topN: Number(params.get('top_n')),
    sortBy: params.get('sort_by')
  })
)

const options = ref(query.demoMode ? createStaticWorkbenchOptions() : createEmptyWorkbenchOptions(query))
const state = ref(query.demoMode ? createStaticRuleCluesData(query) : createEmptyRuleCluesData(query))
const reportContext = ref(state.value.reportContext)
const activeFilter = ref('all')
const isLoading = ref(false)
let suppressWatcher = false

const filterTabs = [
  { id: 'all', label: '全部规则线索' },
  { id: 'monthly', label: '月报高风险' },
  { id: 'rule_only', label: '仅规则命中' }
]

const selectedHorizonLabel = computed(() => options.value.horizonOptions.find((item) => item.id === query.horizon)?.label || query.horizon)
const filteredClues = computed(() => {
  const items = state.value.dailyDetectorClues || []
  if (activeFilter.value === 'monthly') return items.filter((item) => item.isMonthlyHighRiskEntity)
  if (activeFilter.value === 'rule_only') return items.filter((item) => !item.isMonthlyHighRiskEntity)
  return items
})

function detailHref(clue) {
  const next = buildPersistentParams(query, { clueId: clue.id })
  if (clue.riskEntityId) next.set('id', clue.riskEntityId)
  return `clue-detail.html?${next.toString()}`
}

function updateUrl() {
  window.history.replaceState({}, '', `${window.location.pathname}?${buildPersistentParams(query).toString()}`)
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
  options.value = loadedOptions || createEmptyWorkbenchOptions(fallbackQuery)
  const codes = (options.value.manufacturerOptions || []).map((item) => item.code).filter(Boolean)
  if (codes.length && !codes.includes(query.manufacturerCode)) {
    const nextManufacturer = codes.includes(options.value.defaultManufacturerCode) ? options.value.defaultManufacturerCode : codes[0]
    applyEffectiveQuery({ ...query, manufacturerCode: nextManufacturer })
  }
}

async function refreshClues() {
  isLoading.value = true
  try {
    if (query.demoMode) {
      options.value = createStaticWorkbenchOptions()
      state.value = createStaticRuleCluesData(query)
      reportContext.value = state.value.reportContext
      updateUrl()
      return
    }

    const loadedOptions = await loadWorkbenchOptions(query)
    applyLoadedOptions(loadedOptions, query)

    const context = await loadReportContext(query)
    reportContext.value = context
    if (!context.ready) {
      state.value = createEmptyRuleCluesData(query, context)
      updateUrl()
      return
    }

    const effectiveQuery = applyReportContextToQuery(query, context)
    applyEffectiveQuery(effectiveQuery)
    const [refreshedOptions, loadedData] = await Promise.all([
      loadWorkbenchOptions(effectiveQuery),
      loadRuleCluesData(effectiveQuery)
    ])
    applyLoadedOptions(refreshedOptions, effectiveQuery)
    state.value = loadedData || createEmptyRuleCluesData(effectiveQuery, context)
    reportContext.value = state.value.reportContext || context
  } finally {
    isLoading.value = false
  }
}

onMounted(refreshClues)

watch(
  () => [query.runDate, query.horizon, query.manufacturerCode, query.backendBaseUrl, query.userId, query.demoMode],
  () => {
    if (!suppressWatcher) refreshClues()
  }
)
</script>

<template>
  <div class="page-shell">
    <div class="page-header control-header">
      <div>
        <h1>今日规则线索</h1>
        <div class="subtitle">{{ query.runDate }} · 规则巡检 · {{ selectedHorizonLabel }}</div>
      </div>
      <div class="workbench-controls">
        <label class="control-field">
          <span>生产企业</span>
          <select v-model="query.manufacturerCode">
            <option v-for="item in options.manufacturerOptions" :key="item.code" :value="item.code">{{ item.name }}</option>
          </select>
        </label>
        <label class="control-field">
          <span>观察日期</span>
          <select v-model="query.runDate">
            <option v-for="item in options.dailyDetectorDateOptions" :key="item.runDate" :value="item.runDate">{{ item.label }}</option>
          </select>
        </label>
      </div>
    </div>

    <section v-if="reportContext?.displayTitle" class="notice-strip context-notice">
      <strong>{{ reportContext.displayTitle }}</strong>
      <span v-for="line in reportContext.displayLines" :key="line">{{ line }}</span>
    </section>

    <section class="panel clue-hero">
      <div>
        <span class="eyebrow">今日规则线索</span>
        <h2>全部规则线索</h2>
        <p>
          月报高风险对象上的规则命中会附着到风险卡；未进入月报高风险清单但被规则命中的对象，仅作为今日规则线索展示。
        </p>
      </div>
      <div class="batch-card">
        <div class="batch-row"><span>观察日期</span><strong>{{ query.runDate }}</strong></div>
        <div class="batch-row"><span>今日线索</span><strong>{{ state.dailyDetectorStatus.clueCount }}</strong></div>
        <div class="batch-row"><span>已附着证据</span><strong>{{ state.dailyDetectorStatus.attachedHighRiskCount }}</strong></div>
        <div class="batch-row"><span>数据状态</span><strong>{{ state.dailyDetectorStatus.sourceLabel }}</strong></div>
      </div>
    </section>

    <SectionCard title="线索筛选" subtitle="按线索来源查看今日巡检结果">
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
      </div>
    </SectionCard>

    <SectionCard title="全部规则线索" subtitle="区分月报高风险与仅规则命中对象">
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
                <div class="muted">{{ clue.detectorFamily }} · {{ clue.detectorLevel }}</div>
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
                <span v-else class="muted">今日规则线索，按规则证据单独观察</span>
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
