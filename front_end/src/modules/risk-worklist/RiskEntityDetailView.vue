<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import SectionCard from '../../components/SectionCard.vue'
import SquareDatePicker from '../../components/ui/SquareDatePicker.vue'
import {
  applyReportContextToQuery,
  buildPersistentParams,
  createEmptyClueDetailData,
  createEmptyWorkbenchOptions,
  loadClueDetailData,
  loadReportContext,
  loadWorkbenchOptions,
  normalizeWorkbenchQuery
} from '../monthly-demo/pageDataAdapter'

const params = new URLSearchParams(window.location.search)
const clueId = params.get('clueId')
const riskEntityId = params.get('id') || params.get('riskEntityId')
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

const state = ref(createEmptyClueDetailData({ clueId, riskEntityId, query }))
const options = ref(createEmptyWorkbenchOptions(query))
const reportContext = ref(state.value.reportContext)
const selectedRuleFamily = ref('all')
const selectedRuleId = ref('all')
const isLoading = ref(false)
let suppressWatcher = false
let requestSequence = 0

const entity = computed(() => state.value.entity)
const clue = computed(() => state.value.clue || {})
const isMonthlyHighRiskEntity = computed(() => Boolean(state.value.isMonthlyHighRiskEntity && entity.value))
const ruleEvidence = computed(() => state.value.detectorEvidence || [])
const probabilityTrend = computed(() => state.value.probabilityTrend || [])
const selectedHorizonLabel = computed(() => options.value.horizonOptions.find((item) => item.id === query.horizon)?.label || query.horizon)
const availableObservationDates = computed(() => options.value.dailyDetectorDateOptions?.map((item) => item.id).filter(Boolean) || [])

const ruleFamilyOptions = computed(() => {
  const families = [...new Map(ruleEvidence.value.map((item) => [
    item.detectorFamily,
    { id: item.detectorFamily, label: item.detectorFamilyLabel || item.detectorFamily }
  ])).values()].filter((item) => item.id)
  return [{ id: 'all', label: '全部大类' }, ...families]
})

const ruleIdOptions = computed(() => {
  const filtered = selectedRuleFamily.value === 'all'
    ? ruleEvidence.value
    : ruleEvidence.value.filter((item) => item.detectorFamily === selectedRuleFamily.value)
  const ids = filtered.map((item) => ({ id: item.detectorId || item.id, label: item.detectorName })).filter((item) => item.id)
  return [{ id: 'all', label: '全部小类' }, ...ids]
})

const filteredRuleEvidence = computed(() => {
  return ruleEvidence.value.filter((item) => {
    const familyMatched = selectedRuleFamily.value === 'all' || item.detectorFamily === selectedRuleFamily.value
    const idMatched = selectedRuleId.value === 'all' || item.detectorId === selectedRuleId.value || item.id === selectedRuleId.value
    return familyMatched && idMatched
  })
})

const trendPolyline = computed(() => {
  const points = probabilityTrend.value
  if (points.length < 2) return ''
  return points
    .map((point, index) => {
      const x = 24 + (index / (points.length - 1)) * 252
      const y = 118 - Math.max(0.05, Math.min(0.95, Number(point.riskProbability || 0))) * 92
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
})

function backHref() {
  return `clues.html?${buildPersistentParams(query).toString()}`
}

function updateUrl() {
  const next = buildPersistentParams(query, {})
  if (clueId) next.set('clueId', clueId)
  if (riskEntityId) next.set('id', riskEntityId)
  window.history.replaceState({}, '', `${window.location.pathname}?${next.toString()}`)
}

function applyEffectiveQuery(nextQuery) {
  suppressWatcher = true
  Object.assign(query, nextQuery)
  updateUrl()
  window.setTimeout(() => {
    suppressWatcher = false
  }, 0)
}

async function refreshDetail() {
  const sequence = ++requestSequence
  isLoading.value = true
  try {
    selectedRuleId.value = 'all'
    if (query.demoMode) {
      options.value = await loadWorkbenchOptions(query, { allowDemo: true })
      state.value = await loadClueDetailData({ clueId, riskEntityId, query }, { allowDemo: true })
      reportContext.value = state.value.reportContext
      updateUrl()
      return
    }

    const context = await loadReportContext(query)
    if (sequence !== requestSequence) return
    reportContext.value = context
    if (!context.ready) {
      options.value = createEmptyWorkbenchOptions(query)
      state.value = createEmptyClueDetailData({ clueId, riskEntityId, query, reportContext: context })
      updateUrl()
      return
    }

    const effectiveQuery = applyReportContextToQuery(query, context)
    applyEffectiveQuery(effectiveQuery)
    const [loadedOptions, loadedData] = await Promise.all([
      loadWorkbenchOptions(effectiveQuery),
      loadClueDetailData({ clueId, riskEntityId, query: effectiveQuery })
    ])
    if (sequence !== requestSequence) return
    options.value = loadedOptions || createEmptyWorkbenchOptions(effectiveQuery)
    state.value = loadedData || createEmptyClueDetailData({ clueId, riskEntityId, query: effectiveQuery, reportContext: context })
    reportContext.value = state.value.reportContext || context
  } finally {
    if (sequence === requestSequence) {
      isLoading.value = false
    }
  }
}

onMounted(refreshDetail)

watch(
  () => [query.horizon, query.observationDate, query.manufacturerCode, query.backendBaseUrl, query.userId, query.demoMode],
  () => {
    if (!suppressWatcher) refreshDetail()
  }
)

watch(selectedRuleFamily, () => {
  selectedRuleId.value = 'all'
})
</script>

<template>
  <div class="page-shell">
    <a class="back-link" :href="backHref()">返回今日规则线索</a>
    <div class="page-header control-header">
      <div>
        <h1>{{ isMonthlyHighRiskEntity ? '风险对象详情' : '规则线索详情' }} · {{ clue.hospital || '-' }}</h1>
        <div class="subtitle">
          {{ query.observationDate }} · {{ entity?.manufacturer || clue.manufacturer || query.manufacturerCode }} · {{ selectedHorizonLabel }}
        </div>
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
          <SquareDatePicker v-model="query.observationDate" label="观察日期" :available-dates="availableObservationDates" />
        </label>
      </div>
    </div>

    <section v-if="reportContext?.displayTitle" class="notice-strip context-notice">
      <strong>{{ reportContext.displayTitle }}</strong>
      <span v-for="line in reportContext.displayLines" :key="line">{{ line }}</span>
    </section>

    <div v-if="isLoading" class="empty">刷新中</div>
    <div v-else-if="state.emptyTitle && !clue.id && !entity" class="empty">
      <strong>{{ state.emptyTitle }}</strong>
      <p>{{ state.emptyMessage }}</p>
    </div>

    <section v-else class="panel clue-detail-hero">
      <div>
        <span class="eyebrow">{{ isMonthlyHighRiskEntity ? '月报风险证据' : '今日规则线索' }}</span>
        <h2>{{ clue.hospital || entity?.hospital || '-' }} × {{ clue.drug || entity?.drug || '-' }}</h2>
        <p>{{ clue.evidenceText || entity?.reason || '-' }}</p>
      </div>
      <div class="batch-card">
        <div class="batch-row"><span>线索类型</span><strong>{{ clue.sourceTypeLabel || (isMonthlyHighRiskEntity ? '月报高风险' : '仅规则命中') }}</strong></div>
        <div class="batch-row"><span>规则巡检分</span><strong>{{ clue.detectorScoreText || '-' }}</strong></div>
        <div class="batch-row"><span>规则等级</span><strong>{{ clue.detectorLevel || '-' }}</strong></div>
      </div>
    </section>

    <SectionCard
      v-if="isMonthlyHighRiskEntity"
      title="风险摘要"
      subtitle="窗口切换后，丢失概率、涉及金额、趋势和证据一起刷新"
    >
      <div class="riskcard-header compact">
        <div>
          <span class="eyebrow">预测窗口</span>
          <h3>{{ selectedHorizonLabel }}</h3>
        </div>
        <div class="segmented-control horizon-switcher" aria-label="风险窗口切换">
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
      <dl class="definition-grid compact riskcard-score-grid">
        <dt>对象编号</dt><dd class="text-mono">{{ entity.id }}</dd>
        <dt>丢失概率</dt><dd>{{ entity.probabilityDisplay }}</dd>
        <dt>涉及金额</dt><dd>{{ entity.involvedAmountText }}</dd>
        <dt>风险等级</dt><dd><span class="risk-chip" :class="`risk-chip-${entity.riskColor}`">{{ entity.riskLevel }}</span></dd>
        <dt>跟进状态</dt><dd>{{ entity.status || '-' }}</dd>
      </dl>
      <p class="body-copy">{{ entity.reason }}</p>
    </SectionCard>

    <SectionCard
      v-else-if="clue.id"
      title="仅规则命中对象"
      subtitle="该线索未进入本期月报高风险对象，只展示规则巡检信息"
    >
      <dl class="definition-grid">
        <dt>生产企业</dt><dd>{{ clue.manufacturer }}</dd>
        <dt>区域</dt><dd>{{ clue.region }}</dd>
        <dt>规则类型</dt><dd>{{ clue.detectorFamilyLabel }}</dd>
        <dt>规则根因</dt><dd>{{ clue.rootCauseLabel }}</dd>
      </dl>
    </SectionCard>

    <SectionCard title="巡检证据" subtitle="先选规则大类，再选规则小类">
      <div class="control-grid">
        <label class="control-field">
          <span>规则大类</span>
          <select v-model="selectedRuleFamily">
            <option v-for="item in ruleFamilyOptions" :key="item.id" :value="item.id">{{ item.label }}</option>
          </select>
        </label>
        <label class="control-field">
          <span>规则小类</span>
          <select v-model="selectedRuleId">
            <option v-for="item in ruleIdOptions" :key="item.id" :value="item.id">{{ item.label }}</option>
          </select>
        </label>
      </div>
      <div v-if="!filteredRuleEvidence.length" class="empty">当前筛选下暂无巡检证据</div>
      <div v-else class="detector-result-grid">
        <article v-for="rule in filteredRuleEvidence" :key="rule.id" class="detector-result-card">
          <div class="detector-result-head">
            <h3>{{ rule.detectorName }}</h3>
            <span class="status-badge status-badge-info">{{ rule.detectorLevel }}</span>
          </div>
          <dl class="definition-grid compact">
            <dt>规则巡检分</dt><dd>{{ rule.detectorScoreText }}</dd>
            <dt>规则类型</dt><dd>{{ rule.detectorFamilyLabel }}</dd>
            <dt>根因标签</dt><dd>{{ rule.rootCauseLabel }}</dd>
            <dt>证据说明</dt><dd>{{ rule.evidenceText }}</dd>
          </dl>
        </article>
      </div>
    </SectionCard>

    <SectionCard
      v-if="isMonthlyHighRiskEntity"
      title="丢失概率趋势"
      subtitle="横轴为月报月份，纵轴为丢失概率，金额为同窗口涉及金额"
    >
      <div v-if="probabilityTrend.length" class="probability-trend">
        <svg viewBox="0 0 300 136" role="img" aria-label="丢失概率趋势">
          <polyline class="trend-grid-line" points="24,26 276,26" />
          <polyline class="trend-grid-line" points="24,72 276,72" />
          <polyline class="trend-grid-line" points="24,118 276,118" />
          <polyline class="trend-line" :points="trendPolyline" />
          <circle
            v-for="(point, index) in probabilityTrend"
            :key="point.reportMonth"
            class="trend-dot"
            :cx="24 + (index / Math.max(1, probabilityTrend.length - 1)) * 252"
            :cy="118 - Math.max(0.05, Math.min(0.95, Number(point.riskProbability || 0))) * 92"
            r="4"
          />
        </svg>
        <div class="trend-legend">
          <span v-for="point in probabilityTrend" :key="point.reportMonth">
            {{ point.reportMonth }} · {{ point.riskProbabilityText }} · 涉及金额 {{ point.involvedAmountText }}
          </span>
        </div>
      </div>
      <div v-else class="empty">暂无趋势数据</div>
    </SectionCard>
  </div>
</template>
