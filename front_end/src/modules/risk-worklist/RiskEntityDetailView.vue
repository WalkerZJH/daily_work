<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import SectionCard from '../../components/SectionCard.vue'
import {
  createStaticClueDetailData,
  createStaticWorkbenchOptions,
  loadClueDetailData,
  loadWorkbenchOptions,
  normalizeWorkbenchQuery
} from '../monthly-demo/pageDataAdapter'

const params = new URLSearchParams(window.location.search)
const clueId = params.get('clueId')
const riskEntityId = params.get('id') || params.get('riskEntityId')
const query = reactive(
  normalizeWorkbenchQuery({
    manufacturerCode: params.get('manufacturer_code'),
    reportMonth: params.get('report_month'),
    runDate: params.get('run_date'),
    horizon: params.get('horizon') || params.get('h')
  })
)

const state = ref(createStaticClueDetailData({ clueId, riskEntityId, query }))
const options = ref(createStaticWorkbenchOptions())
const selectedDetectorFamily = ref('all')
const selectedDetectorId = ref('all')

const entity = computed(() => state.value.entity)
const clue = computed(() => state.value.clue || {})
const isMonthlyHighRiskEntity = computed(() => Boolean(state.value.isMonthlyHighRiskEntity && entity.value))
const detectorEvidence = computed(() => state.value.detectorEvidence || [])
const probabilityTrend = computed(() => state.value.probabilityTrend || [])

const detectorFamilyOptions = computed(() => {
  const families = [...new Set(detectorEvidence.value.map((item) => item.detectorFamily).filter(Boolean))]
  return [{ id: 'all', label: '全部大类' }, ...families.map((family) => ({ id: family, label: family }))]
})

const detectorIdOptions = computed(() => {
  const filtered = selectedDetectorFamily.value === 'all'
    ? detectorEvidence.value
    : detectorEvidence.value.filter((item) => item.detectorFamily === selectedDetectorFamily.value)
  const ids = filtered.map((item) => ({ id: item.detectorId || item.id, label: item.detectorName })).filter((item) => item.id)
  return [{ id: 'all', label: '全部小类' }, ...ids]
})

const filteredDetectorEvidence = computed(() => {
  return detectorEvidence.value.filter((item) => {
    const familyMatched = selectedDetectorFamily.value === 'all' || item.detectorFamily === selectedDetectorFamily.value
    const idMatched = selectedDetectorId.value === 'all' || item.detectorId === selectedDetectorId.value || item.id === selectedDetectorId.value
    return familyMatched && idMatched
  })
})

const trendPolyline = computed(() => {
  const points = probabilityTrend.value
  if (points.length < 2) return ''
  return points
    .map((item, index) => {
      const x = 24 + (index / (points.length - 1)) * 252
      const y = 118 - Math.max(0.05, Math.min(0.95, Number(item.riskProbability || 0))) * 92
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
})

function backHref() {
  const next = new URLSearchParams({
    manufacturer_code: query.manufacturerCode,
    report_month: query.reportMonth,
    run_date: query.runDate,
    horizon: query.horizon
  })
  return `clues.html?${next.toString()}`
}

function updateUrl() {
  const next = new URLSearchParams({
    manufacturer_code: query.manufacturerCode,
    report_month: query.reportMonth,
    run_date: query.runDate,
    horizon: query.horizon
  })
  if (clueId) next.set('clueId', clueId)
  if (riskEntityId) next.set('id', riskEntityId)
  window.history.replaceState({}, '', `${window.location.pathname}?${next.toString()}`)
}

async function refreshDetail() {
  updateUrl()
  selectedDetectorId.value = 'all'
  const fallback = createStaticClueDetailData({ clueId, riskEntityId, query })
  const data = await loadClueDetailData({
    clueId,
    riskEntityId,
    query: {
      ...query,
      detectorFamily: selectedDetectorFamily.value === 'all' ? undefined : selectedDetectorFamily.value,
      detectorId: selectedDetectorId.value === 'all' ? undefined : selectedDetectorId.value
    }
  })
  state.value = data || fallback
}

onMounted(async () => {
  const loadedOptions = await loadWorkbenchOptions(query)
  if (loadedOptions) options.value = loadedOptions
  await refreshDetail()
})

watch(() => [query.horizon, query.runDate, query.manufacturerCode], refreshDetail)
watch(selectedDetectorFamily, () => {
  selectedDetectorId.value = 'all'
})
</script>

<template>
  <div class="page-shell">
    <a class="back-link" :href="backHref()">返回今日巡检线索</a>
    <div class="page-header control-header">
      <div>
        <h1>{{ isMonthlyHighRiskEntity ? '风险对象详情' : '规则线索详情' }} · {{ clue.hospital }}</h1>
        <div class="subtitle">
          {{ query.runDate }} · {{ entity?.manufacturer || clue.manufacturer || query.manufacturerCode }} ·
          {{ options.horizonOptions.find((item) => item.id === query.horizon)?.label }}
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
          <span>日报日期</span>
          <select v-model="query.runDate">
            <option v-for="item in options.dailyDetectorDateOptions" :key="item.runDate" :value="item.runDate">{{ item.label }}</option>
          </select>
        </label>
      </div>
    </div>

    <section class="panel clue-detail-hero">
      <div>
        <span class="eyebrow">{{ isMonthlyHighRiskEntity ? '月报风险证据' : '今日巡检线索' }}</span>
        <h2>{{ clue.hospital }} × {{ clue.drug }}</h2>
        <p>{{ clue.evidenceText }}</p>
      </div>
      <div class="batch-card">
        <div class="batch-row"><span>线索类型</span><strong>{{ clue.sourceTypeLabel }}</strong></div>
        <div class="batch-row"><span>规则巡检分</span><strong>{{ clue.detectorScoreText }}</strong></div>
        <div class="batch-row"><span>规则等级</span><strong>{{ clue.detectorLevel }}</strong></div>
      </div>
    </section>

    <SectionCard
      v-if="isMonthlyHighRiskEntity"
      title="风险摘要"
      subtitle="窗口切换后，丢失概率、涉及金额、趋势和证据一起刷新"
    >
      <div class="riskcard-toolbar">
        <div>
          <span class="eyebrow">预测窗口</span>
          <h3>{{ options.horizonOptions.find((item) => item.id === query.horizon)?.label }}</h3>
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
      v-else
      title="仅规则命中对象"
      subtitle="该线索未进入本期月报高风险对象，只展示规则巡检信息"
    >
      <dl class="definition-grid">
        <dt>生产企业</dt><dd>{{ clue.manufacturer }}</dd>
        <dt>区域</dt><dd>{{ clue.region }}</dd>
        <dt>规则类型</dt><dd>{{ clue.detectorFamily }}</dd>
        <dt>规则根因</dt><dd>{{ clue.rootCauseLabel }}</dd>
      </dl>
    </SectionCard>

    <SectionCard title="巡检证据" subtitle="先选规则大类，再选规则小类">
      <div class="control-grid">
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
      </div>
      <div class="detector-result-grid">
        <article v-for="detector in filteredDetectorEvidence" :key="detector.id" class="detector-result-card">
          <div class="detector-result-head">
            <h3>{{ detector.detectorName }}</h3>
            <span class="status-badge status-badge-info">{{ detector.detectorLevel }}</span>
          </div>
          <dl class="definition-grid compact">
            <dt>规则巡检分</dt><dd>{{ detector.detectorScoreText }}</dd>
            <dt>规则类型</dt><dd>{{ detector.detectorFamily }}</dd>
            <dt>根因标签</dt><dd>{{ detector.rootCauseLabel }}</dd>
            <dt>证据说明</dt><dd>{{ detector.evidenceText }}</dd>
          </dl>
        </article>
      </div>
      <div v-if="!filteredDetectorEvidence.length" class="empty">当前筛选下暂无巡检证据</div>
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
