<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import SectionCard from '../../components/SectionCard.vue'
import { useManufacturerScope } from '../../context/manufacturerScope'
import {
  applyReportContextToQuery,
  buildPersistentParams,
  createEmptyClueDetailData,
  createEmptyRuleOnlyClueDetailData,
  horizonOptions,
  loadReportContext,
  loadRiskEntityDetailData,
  loadRuleOnlyClueDetailData,
  normalizeWorkbenchQuery
} from '../monthly-demo/pageDataAdapter'

const params = new URLSearchParams(window.location.search)
const riskEntityId = params.get('id') || params.get('riskEntityId')
const clueId = params.get('clueId')
// Candidate links may retain clueId for source traceability; candidate mode wins for compatibility.
const detailMode = riskEntityId ? 'candidate' : clueId ? 'rule-only' : 'invalid'
const draftQuery = reactive(normalizeWorkbenchQuery({
  backendBaseUrl: params.get('backendBaseUrl'),
  userId: params.get('user_id') || params.get('userId'),
  demoMode: params.get('demoMode'),
  observationDate: params.get('observation_date'),
  manufacturerCode: params.get('manufacturer_code'),
  reportMonth: params.get('report_month'),
  probabilityReportMonth: params.get('probability_report_month'),
  horizon: params.get('horizon'),
  sortBy: params.get('sort_by'),
  detectorRunDate: params.get('detector_run_date') || params.get('run_date')
}))
const appliedQuery = ref(normalizeWorkbenchQuery(draftQuery))
const candidateState = ref(createEmptyClueDetailData({ riskEntityId, query: appliedQuery.value }))
const ruleOnlyState = ref(createEmptyRuleOnlyClueDetailData({ clueId, query: appliedQuery.value }))
const reportContext = ref(candidateState.value.reportContext)
const isLoading = ref(false)
const manufacturerScope = useManufacturerScope()
const manufacturerCode = manufacturerScope.manufacturerCode
let requestSequence = 0
let pageReady = false

const entity = computed(() => candidateState.value.entity)
const profiles = computed(() => Object.values(candidateState.value.horizonProfiles || {}))
const evidence = computed(() => candidateState.value.detectorEvidence || [])
const probabilityTrend = computed(() => candidateState.value.probabilityTrend || [])
const probabilityTrendWarnings = computed(() => candidateState.value.probabilityTrendWarnings || [])
const selectedHorizonProfile = computed(() => candidateState.value.horizonProfiles?.[appliedQuery.value.horizon] || null)
const selectedHorizonLabel = computed(() => horizonOptions.find((item) => item.id === appliedQuery.value.horizon)?.label || appliedQuery.value.horizon)
const ruleClue = computed(() => ruleOnlyState.value.clue)
const evidenceFields = computed(() => flattenEvidence(ruleClue.value?.evidencePayload))

const TREND_PLOT = Object.freeze({ left: 72, right: 648, top: 28, bottom: 218 })

const trendYAxis = computed(() => {
  const values = probabilityTrend.value
    .map((point) => Number(point.riskProbability))
    .filter(Number.isFinite)
    .map((value) => Math.max(0, Math.min(1, value)))

  if (!values.length) return { min: 0, max: 1, ticks: [] }

  const observedMin = Math.min(...values)
  const observedMax = Math.max(...values)
  const observedSpan = observedMax - observedMin
  const domainSpan = Math.max(observedSpan * 1.5, 0.02)
  const center = (observedMin + observedMax) / 2
  let min = center - domainSpan / 2
  let max = center + domainSpan / 2

  if (min < 0) {
    max -= min
    min = 0
  }
  if (max > 1) {
    min -= max - 1
    max = 1
  }
  min = Math.max(0, min)
  max = Math.min(1, max)

  const ticks = Array.from({ length: 5 }, (_, index) => {
    const value = max - ((max - min) * index) / 4
    return {
      value,
      y: scaleTrendY(value, min, max),
      label: `${(value * 100).toFixed(1)}%`
    }
  })
  return { min, max, ticks }
})

const trendXTicks = computed(() => probabilityTrend.value.map((point, index, points) => ({
  ...point,
  x: trendPointX(index, points.length)
})))

const trendDirection = computed(() => {
  const points = probabilityTrend.value
  if (points.length < 2) return { kind: 'single', delta: 0 }
  const delta = Number(points.at(-1).riskProbability) - Number(points[0].riskProbability)
  if (delta > 0.0005) return { kind: 'up', delta }
  if (delta < -0.0005) return { kind: 'down', delta }
  return { kind: 'flat', delta }
})

const trendDirectionText = computed(() => {
  if (trendDirection.value.kind === 'single') return '当前仅有 1 个有效月份'
  const change = Math.abs(trendDirection.value.delta * 100).toFixed(1)
  if (trendDirection.value.kind === 'up') return `▲ 上升 ${change} 个百分点`
  if (trendDirection.value.kind === 'down') return `▼ 下降 ${change} 个百分点`
  return `— 持平（变化 ${change} 个百分点）`
})

const trendRangeText = computed(() => {
  const points = probabilityTrend.value
  if (!points.length) return ''
  const first = points[0]
  const last = points.at(-1)
  return `${first.reportMonth} ${first.riskProbabilityText} → ${last.reportMonth} ${last.riskProbabilityText}`
})

const trendAriaLabel = computed(() => `月度滚动丢失概率趋势。${trendRangeText.value}。${trendDirectionText.value}`)

const trendPolyline = computed(() => {
  const points = trendXTicks.value
  if (points.length < 2) return ''
  return points.map((point) => `${point.x.toFixed(1)},${trendPointY(point.riskProbability).toFixed(1)}`).join(' ')
})

function trendPointY(probability) {
  return scaleTrendY(Number(probability), trendYAxis.value.min, trendYAxis.value.max)
}

function scaleTrendY(probability, min, max) {
  const safeProbability = Math.max(min, Math.min(max, probability))
  const ratio = max === min ? 0.5 : (safeProbability - min) / (max - min)
  return TREND_PLOT.bottom - ratio * (TREND_PLOT.bottom - TREND_PLOT.top)
}

function trendPointX(index, count) {
  if (count <= 1) return (TREND_PLOT.left + TREND_PLOT.right) / 2
  return TREND_PLOT.left + (index / (count - 1)) * (TREND_PLOT.right - TREND_PLOT.left)
}

function trendWarningText(warning) {
  if (warning === 'TREND_MODEL_ARTIFACT_CHANGED') return '趋势区间内模型版本发生变化，概率变化可能同时受到模型版本和实体特征变化影响。'
  if (warning === 'HISTORICAL_RISK_PROBABILITY_UNAVAILABLE') return '部分月份存在结果记录但月度概率不可用，未作为趋势采样点展示。'
  if (warning === 'HISTORICAL_RISK_ENTITY_SCOPE_MISMATCH') return '部分历史记录未通过同一生产企业、医院和药品关系校验，未纳入趋势。'
  return warning
}

function backHref() {
  const query = buildPersistentParams({
    ...appliedQuery.value,
    manufacturerCode: manufacturerCode.value
  })
  return `${detailMode === 'rule-only' ? 'clues.html' : 'index.html'}?${query.toString()}`
}

function updateUrl() {
  if (detailMode !== 'candidate') return
  window.history.replaceState({}, '', `${window.location.pathname}?${buildPersistentParams(appliedQuery.value, { id: riskEntityId, clueId }).toString()}`)
}

async function refreshCandidateDetail() {
  const sequence = ++requestSequence
  isLoading.value = true
  try {
    const context = await loadReportContext(draftQuery)
    if (sequence !== requestSequence) return
    const effective = applyReportContextToQuery(draftQuery, context)
    appliedQuery.value = effective
    reportContext.value = context
    const loadedState = await loadRiskEntityDetailData(riskEntityId, effective)
    if (sequence !== requestSequence) return
    candidateState.value = loadedState
    reportContext.value = loadedState.reportContext || context
    updateUrl()
  } finally {
    if (sequence === requestSequence) isLoading.value = false
  }
}

async function selectHorizon(horizon) {
  if (horizon === appliedQuery.value.horizon || isLoading.value) return
  draftQuery.horizon = horizon
  await refreshCandidateDetail()
}

async function loadRuleOnlyDetail() {
  const sequence = ++requestSequence
  isLoading.value = true
  try {
    const loadedState = await loadRuleOnlyClueDetailData(clueId, appliedQuery.value)
    if (sequence !== requestSequence) return
    ruleOnlyState.value = loadedState
  } finally {
    if (sequence === requestSequence) isLoading.value = false
  }
}

function formatEvidenceValue(value) {
  if (value === null || value === undefined || value === '') return '暂无数据'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function flattenEvidence(value, prefix = '') {
  if (value === null || value === undefined || value === '') return []
  if (Array.isArray(value)) return [{ key: prefix || 'evidence_payload', value }]
  if (typeof value !== 'object') return [{ key: prefix || 'evidence_payload', value }]
  return Object.entries(value).flatMap(([key, item]) => {
    const path = prefix ? `${prefix}.${key}` : key
    return item && typeof item === 'object' && !Array.isArray(item)
      ? flattenEvidence(item, path)
      : [{ key: path, value: item }]
  })
}

onMounted(async () => {
  await manufacturerScope.initialize()
  draftQuery.manufacturerCode = manufacturerCode.value
  appliedQuery.value = normalizeWorkbenchQuery(draftQuery)
  pageReady = true
  if (detailMode === 'candidate') {
    await refreshCandidateDetail()
  } else if (detailMode === 'rule-only') {
    await loadRuleOnlyDetail()
  }
})

watch(manufacturerCode, async (nextCode) => {
  if (!pageReady || !nextCode || nextCode === draftQuery.manufacturerCode) return
  draftQuery.manufacturerCode = nextCode
  appliedQuery.value = normalizeWorkbenchQuery(draftQuery)
  if (detailMode === 'candidate') await refreshCandidateDetail()
  if (detailMode === 'rule-only') await loadRuleOnlyDetail()
})
</script>

<template>
  <div class="page-shell">
    <a class="back-link" :href="backHref()">{{ detailMode === 'rule-only' ? '返回规则巡检结果' : '返回月度候选工作台' }}</a>

    <div v-if="detailMode === 'candidate'" class="page-header control-header">
      <div>
        <h1>候选对象详情</h1>
        <div class="subtitle">固定候选对象的月度模型结果与 detector 命中证据</div>
      </div>
      <div class="workbench-controls">
        <div class="segmented-control horizon-switcher" aria-label="风险窗口切换">
          <button
            v-for="item in horizonOptions"
            :key="item.id"
            type="button"
            class="segment-btn"
            :class="{ active: appliedQuery.horizon === item.id }"
            :disabled="isLoading"
            @click="selectHorizon(item.id)"
          >{{ item.label }}</button>
        </div>
        <button type="button" class="btn btn-primary" :disabled="isLoading" @click="refreshCandidateDetail">{{ isLoading ? '查询中…' : '刷新详情' }}</button>
      </div>
    </div>

    <div v-else-if="detailMode === 'rule-only'" class="page-header">
      <div><h1>规则线索详情</h1><div class="subtitle">Daily Detector 的事实型规则巡检记录</div></div>
    </div>

    <div v-if="detailMode === 'invalid'" class="empty"><strong>缺少详情标识</strong><p>请从月度候选工作台或规则巡检结果打开详情。</p></div>
    <div v-else-if="isLoading" class="empty">正在读取详情…</div>

    <template v-else-if="detailMode === 'rule-only'">
      <div v-if="!ruleClue" class="empty"><strong>{{ ruleOnlyState.emptyTitle }}</strong><p>{{ ruleOnlyState.emptyMessage }}</p></div>
      <template v-else>
        <SectionCard title="对象与观测上下文">
          <dl class="definition-grid">
            <dt>医院</dt><dd>{{ ruleClue.hospital || '暂无数据' }}</dd>
            <dt>药品</dt><dd>{{ ruleClue.drug || '暂无数据' }}</dd>
            <dt>生产企业</dt><dd>{{ ruleClue.manufacturer || '暂无数据' }}</dd>
            <dt>观测日期</dt><dd>{{ ruleClue.observationDate || '暂无数据' }}</dd>
            <dt>关联状态</dt><dd>{{ ruleClue.relationshipLabel }}</dd>
          </dl>
        </SectionCard>
        <SectionCard title="规则信息">
          <dl class="definition-grid">
            <dt>规则名称</dt><dd>{{ ruleClue.detectorName || '暂无数据' }}</dd>
            <dt>Detector ID</dt><dd>{{ ruleClue.detectorId || '暂无数据' }}</dd>
            <dt>Detector family</dt><dd>{{ ruleClue.detectorFamilyLabel || ruleClue.detectorFamily || '暂无数据' }}</dd>
            <dt>规则巡检分数</dt><dd>{{ ruleClue.detectorScoreText || '暂无数据' }}</dd>
            <dt v-if="ruleClue.detectorLevel">命中等级</dt><dd v-if="ruleClue.detectorLevel">{{ ruleClue.detectorLevel }}</dd>
            <dt v-if="ruleClue.confidence !== null && ruleClue.confidence !== undefined">置信信息</dt><dd v-if="ruleClue.confidence !== null && ruleClue.confidence !== undefined">{{ ruleClue.confidence }}</dd>
          </dl>
        </SectionCard>
        <SectionCard title="命中说明">
          <dl class="definition-grid"><dt>证据说明</dt><dd>{{ ruleClue.evidenceText || '当前规则未提供该字段' }}</dd><dt>规则原因</dt><dd>{{ ruleClue.rootCause || '当前规则未提供该字段' }}</dd></dl>
        </SectionCard>
        <SectionCard title="证据详情">
          <div v-if="!evidenceFields.length" class="empty">当前规则未提供证据 payload。</div>
          <dl v-else class="definition-grid"><template v-for="field in evidenceFields" :key="field.key"><dt>{{ field.key }}</dt><dd>{{ formatEvidenceValue(field.value) }}</dd></template></dl>
        </SectionCard>
        <section class="notice-strip context-notice"><strong>口径说明</strong><span>规则巡检分数不是月度风险概率。</span><span>仅规则命中不会创建 Recurring 风险候选对象。</span></section>
      </template>
    </template>

    <template v-else>
      <section v-if="reportContext?.displayTitle" class="notice-strip context-notice"><strong>{{ reportContext.displayTitle }}</strong><span v-for="line in reportContext.displayLines" :key="line">{{ line }}</span></section>
      <div v-if="!entity" class="empty"><strong>{{ candidateState.emptyTitle }}</strong><p>{{ candidateState.emptyMessage }}</p></div>
      <template v-else>
        <SectionCard title="对象与当前月度结果" subtitle="该结果来自月度候选排序，不由 detector 生成"><dl class="definition-grid"><dt>医院 × 药品</dt><dd>{{ entity.hospital }} × {{ entity.drug }}</dd><dt>生产企业</dt><dd>{{ entity.manufacturer }}</dd><dt>观察日期</dt><dd>{{ appliedQuery.observationDate }}</dd><dt>预测窗口</dt><dd>{{ selectedHorizonLabel }}</dd><dt>月度概率</dt><dd>{{ selectedHorizonProfile?.probabilityDisplay || entity.probabilityDisplay }}</dd><dt>涉及金额</dt><dd>{{ selectedHorizonProfile?.involvedAmountText || entity.involvedAmountText }}</dd><dt>风险展示等级</dt><dd>{{ selectedHorizonProfile?.riskLevel || entity.riskLevel }}</dd></dl></SectionCard>
        <SectionCard title="H3 / H6 / H12 月度结果" subtitle="不同预测窗口相互独立"><div class="data-table-wrap"><table><thead><tr><th>窗口</th><th>月度概率</th><th>涉及金额</th><th>展示等级</th></tr></thead><tbody><tr v-for="profile in profiles" :key="profile.horizon"><td>{{ profile.horizon }}</td><td>{{ profile.probabilityDisplay }}</td><td>{{ profile.involvedAmountText }}</td><td>{{ profile.riskLevel }}</td></tr></tbody></table></div></SectionCard>
        <SectionCard title="当前日期命中的规则证据" subtitle="规则仅提供事实证据，不改变候选池、排序、概率或金额"><div v-if="!evidence.length" class="empty">当前 observation_date 没有该候选对象的 detector 命中。</div><article v-else v-for="item in evidence" :key="`${item.detectorId}-${item.detectorRunDate}`" class="detector-result-card"><h3>{{ item.detectorName || item.detectorId }}</h3><dl class="definition-grid compact"><dt>Detector ID</dt><dd>{{ item.detectorId || '-' }}</dd><dt>规则巡检分数</dt><dd>{{ item.detectorScoreText || '-' }}</dd><dt>命中说明</dt><dd>{{ item.evidenceText || '-' }}</dd><dt>当前值</dt><dd>{{ item.currentValueText || '-' }}</dd><dt>历史基准</dt><dd>{{ item.baselineValueText || '-' }}</dd><dt>比较值 / 阈值</dt><dd>{{ item.comparisonText || '-' }}</dd><dt>备注</dt><dd>{{ item.caveat || '-' }}</dd></dl></article></SectionCard>
        <SectionCard title="月度滚动丢失概率趋势" :subtitle="`当前预测窗口：${selectedHorizonLabel}；纵轴根据当前样本动态缩放，坐标值仍为真实概率`">
          <div v-if="probabilityTrend.length" class="probability-trend">
            <div class="trend-summary" :class="`trend-summary-${trendDirection.kind}`">
              <span>区间变化</span>
              <strong>{{ trendDirectionText }}</strong>
              <small>{{ trendRangeText }}</small>
            </div>
            <svg viewBox="0 0 680 280" role="img" aria-label="月度滚动丢失概率趋势">
              <desc>{{ trendAriaLabel }}</desc>
              <g v-for="tick in trendYAxis.ticks" :key="tick.label">
                <line class="trend-grid-line" :x1="TREND_PLOT.left" :x2="TREND_PLOT.right" :y1="tick.y" :y2="tick.y" />
                <text class="trend-axis-label trend-axis-label-y" :x="TREND_PLOT.left - 12" :y="tick.y + 4" text-anchor="end">{{ tick.label }}</text>
              </g>
              <line class="trend-axis-line" :x1="TREND_PLOT.left" :x2="TREND_PLOT.left" :y1="TREND_PLOT.top" :y2="TREND_PLOT.bottom" />
              <line class="trend-axis-line" :x1="TREND_PLOT.left" :x2="TREND_PLOT.right" :y1="TREND_PLOT.bottom" :y2="TREND_PLOT.bottom" />
              <text class="trend-axis-title" x="18" y="123" text-anchor="middle" transform="rotate(-90 18 123)">丢失概率</text>
              <text class="trend-axis-title" x="360" y="270" text-anchor="middle">报告月份</text>
              <polyline v-if="trendPolyline" :class="['trend-line', `trend-line-${trendDirection.kind}`]" :points="trendPolyline" />
              <g v-for="point in trendXTicks" :key="point.reportMonth">
                <line class="trend-axis-tick" :x1="point.x" :x2="point.x" :y1="TREND_PLOT.bottom" :y2="TREND_PLOT.bottom + 6" />
                <circle :class="['trend-dot', `trend-dot-${trendDirection.kind}`]" :cx="point.x" :cy="trendPointY(point.riskProbability)" r="5">
                  <title>{{ point.reportMonth }}：{{ point.riskProbabilityText }}</title>
                </circle>
                <text class="trend-axis-label trend-axis-label-x" :x="point.x" :y="TREND_PLOT.bottom + 22" text-anchor="middle">{{ point.reportMonth }}</text>
              </g>
            </svg>
            <div class="trend-legend">
              <span v-for="point in probabilityTrend" :key="point.reportMonth">{{ point.reportMonth }} · {{ point.riskProbabilityText }} · 涉及金额 {{ point.involvedAmountText }}</span>
            </div>
          </div>
          <div v-else class="empty">当前候选对象暂无可用的历史月度概率趋势。</div>
          <div v-if="probabilityTrendWarnings.length" class="notice-strip context-notice"><span v-for="warning in probabilityTrendWarnings" :key="warning">{{ trendWarningText(warning) }}</span></div>
        </SectionCard>
      </template>
    </template>
  </div>
</template>
