<script setup>
import { computed, onMounted, ref } from 'vue'
import SectionCard from '../../components/SectionCard.vue'
import { createStaticClueDetailData, loadClueDetailData } from '../monthly-demo/pageDataAdapter'

const params = new URLSearchParams(window.location.search)
const initialData = createStaticClueDetailData({
  clueId: params.get('clueId'),
  riskEntityId: params.get('id') || params.get('riskEntityId')
})

const state = ref(initialData)
const riskCardHorizonTabs = ['H3', 'H6', 'H12']
const requestedHorizon = params.get('horizon') || params.get('h')
const selectedHorizon = ref(riskCardHorizonTabs.includes(requestedHorizon) ? requestedHorizon : state.value.entity?.horizon || 'H6')

const entity = computed(() => state.value.entity)
const clue = computed(() => state.value.clue || {})
const isMonthlyHighRiskEntity = computed(() => Boolean(state.value.isMonthlyHighRiskEntity && entity.value))
const horizonProfiles = computed(() => state.value.horizonProfiles || {})
const activeRiskCard = computed(() => horizonProfiles.value[selectedHorizon.value] || horizonProfiles.value.H6 || {})
const detectorEvidence = computed(() => state.value.detectorEvidence || [])
const probabilityTrend = computed(() => state.value.probabilityTrend || [])

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

function horizonLabel(horizon) {
  const labels = { H3: '3月', H6: '6月', H12: '12月' }
  return labels[horizon] || horizon
}

onMounted(async () => {
  const data = await loadClueDetailData({
    clueId: params.get('clueId'),
    riskEntityId: params.get('id') || params.get('riskEntityId')
  })
  if (!data) return
  state.value = data
  if (!horizonProfiles.value[selectedHorizon.value]) selectedHorizon.value = entity.value?.horizon || 'H6'
})
</script>

<template>
  <div class="page-shell">
    <a class="back-link" href="clues.html">返回今日规则线索</a>
    <div class="page-header">
      <h1>{{ isMonthlyHighRiskEntity ? '月报风险与规则证据' : '规则线索详情' }} · {{ clue.hospital }}</h1>
      <div class="subtitle">
        {{ clue.detectorRunDate }} · {{ clue.detectorName }} · {{ clue.detectorScoreLabel }}
      </div>
    </div>

    <section class="panel clue-detail-hero">
      <div>
        <span class="eyebrow">{{ isMonthlyHighRiskEntity ? 'Monthly Risk Evidence' : 'Daily Rule Clue' }}</span>
        <h2>{{ clue.hospital }} × {{ clue.drug }}</h2>
        <p>{{ clue.evidenceText }}</p>
      </div>
      <div class="batch-card">
        <div class="batch-row"><span>线索类型</span><strong>{{ clue.sourceTypeLabel }}</strong></div>
        <div class="batch-row"><span>规则巡检分</span><strong>{{ clue.detectorScoreText }}</strong></div>
        <div class="batch-row"><span>规则等级</span><strong>{{ clue.detectorLevel }}</strong></div>
        <div class="batch-row"><span>巡检日期</span><strong>{{ clue.detectorRunDate }}</strong></div>
      </div>
    </section>

    <div v-if="isMonthlyHighRiskEntity" class="grid-2">
      <SectionCard title="月报风险摘要" subtitle="月报丢失概率来自稳定批次，不承诺每日变化">
        <dl class="definition-grid">
          <dt>实体 ID</dt><dd class="text-mono">{{ entity.id }}</dd>
          <dt>药品</dt><dd>{{ entity.drug }}</dd>
          <dt>风险等级</dt><dd><span class="risk-chip" :class="`risk-chip-${entity.riskColor}`">{{ entity.riskLevel }}</span></dd>
          <dt>月报丢失概率</dt><dd>{{ entity.probabilityDisplay }}</dd>
          <dt>预测窗口消费</dt><dd>{{ entity.averageConsumptionText }}</dd>
          <dt>损失价值</dt><dd>{{ entity.lossValueText || entity.businessScoreText }}</dd>
          <dt>跟进状态</dt><dd>{{ entity.status }}</dd>
        </dl>
      </SectionCard>

      <SectionCard title="风险窗口" subtitle="窗口切换只影响月报风险卡视角">
        <div class="riskcard-toolbar">
          <div>
            <span class="eyebrow">窗口切换</span>
            <h3>{{ activeRiskCard.horizonLabel || horizonLabel(activeRiskCard.horizon) }} · {{ activeRiskCard.label }}</h3>
          </div>
          <div class="segmented-control horizon-switcher" aria-label="风险窗口切换">
            <button
              v-for="horizon in riskCardHorizonTabs"
              :key="horizon"
              type="button"
              class="segment-btn"
              :class="{ active: selectedHorizon === horizon }"
              @click="selectedHorizon = horizon"
            >
              {{ horizonLabel(horizon) }}
            </button>
          </div>
        </div>
        <dl class="definition-grid compact riskcard-score-grid">
          <dt>月报丢失概率</dt><dd>{{ activeRiskCard.probabilityDisplay }}</dd>
          <dt>预测窗口消费</dt><dd>{{ activeRiskCard.averageConsumptionText }}</dd>
          <dt>损失价值</dt><dd>{{ activeRiskCard.lossValueText || activeRiskCard.businessScoreText }}</dd>
        </dl>
        <p class="body-copy">{{ activeRiskCard.reason }}</p>
      </SectionCard>
    </div>

    <SectionCard
      v-else
      title="仅规则命中对象"
      subtitle="该线索未进入本期月报高风险对象，只展示规则巡检信息"
    >
      <dl class="definition-grid">
        <dt>生产商</dt><dd>{{ clue.manufacturer }}</dd>
        <dt>区域</dt><dd>{{ clue.region }}</dd>
        <dt>规则类型</dt><dd>{{ clue.detectorFamily }}</dd>
        <dt>规则根因</dt><dd>{{ clue.rootCauseLabel }}</dd>
        <dt>月报丢失概率</dt><dd>-</dd>
        <dt>损失价值</dt><dd>-</dd>
      </dl>
    </SectionCard>

    <SectionCard title="巡检证据" subtitle="巡检分只解释命中结果，不作为丢失概率使用">
      <div class="detector-result-grid">
        <article v-for="detector in detectorEvidence" :key="detector.id" class="detector-result-card">
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
    </SectionCard>

    <div v-if="isMonthlyHighRiskEntity" class="grid-2">
      <SectionCard title="月报丢失概率趋势" subtitle="X 轴为 report_month，Y 轴为 risk_probability">
        <div v-if="probabilityTrend.length" class="probability-trend">
          <svg viewBox="0 0 300 136" role="img" aria-label="月报丢失概率趋势">
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
              {{ point.reportMonth }} · {{ point.riskProbabilityText }} · 损失价值 {{ point.lossValueText }}
            </span>
          </div>
        </div>
        <div v-else class="empty">暂无月报趋势数据</div>
      </SectionCard>

      <SectionCard title="特征贡献摘要">
        <div class="evidence-list">
          <div v-for="item in activeRiskCard.shapHighlights || []" :key="item.feature" class="evidence-row">
            <span class="evidence-dot"></span>
            <p><strong>{{ item.feature }} {{ item.contribution }}</strong><br>{{ item.explanation }}</p>
          </div>
        </div>
      </SectionCard>
    </div>
  </div>
</template>
