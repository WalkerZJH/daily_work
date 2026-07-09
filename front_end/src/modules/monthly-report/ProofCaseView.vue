<script setup>
import { computed, onMounted, ref } from 'vue'
import SectionCard from '../../components/SectionCard.vue'
import { createStaticProofCasesData, loadProofCasesData } from '../monthly-demo/pageDataAdapter'

const state = ref(createStaticProofCasesData())
const selectedHorizon = ref('H6')

const horizonTabs = computed(() => state.value.proofCaseHorizonTabs || [])
const horizonSets = computed(() => state.value.proofCaseHorizonSets || {})
const activeSet = computed(() => horizonSets.value[selectedHorizon.value] || horizonSets.value.H6 || { cases: [] })
const proofCases = computed(() => activeSet.value.cases || [])
const spotlight = computed(() => proofCases.value[0] || {})
const displayLookupStatus = computed(() => state.value.displayLookupStatus || { label: '接口未接通', message: '展示名映射未接通' })

const summaryMetrics = computed(() => [
  { label: '复盘月报', value: activeSet.value.reportMonth || '-', note: '闭合验证', tone: 'info' },
  { label: '命中案例', value: String(proofCases.value.length), note: '高价值对象', tone: 'success' },
  { label: '验证窗口', value: activeSet.value.validationDays || '-', note: '月报日至闭合日', tone: 'warning' },
  { label: '复盘口径', value: activeSet.value.label || '-', note: '按月报批次验证', tone: 'danger' }
])

const readingPath = computed(() => [
  {
    label: '月报日',
    date: activeSet.value.reportDate,
    title: '输出高价值风险清单',
    text: '主干月报给出丢失概率，并按涉及金额排序。'
  },
  {
    label: `${activeSet.value.label || '风险'}跟进窗口`,
    date: `${activeSet.value.reportDate} 至 ${activeSet.value.validationEnd}`,
    title: '持续观察采购恢复情况',
    text: '入选对象在验证窗口内保持 0 次续购，月报风险信号持续成立。'
  },
  {
    label: '闭合验证',
    date: activeSet.value.validationEnd,
    title: `${activeSet.value.label || ''}结果确认`,
    text: '验证窗口闭合后，案例进入历史命中复盘，用于呈现产品提前识别高价值风险的能力。'
  }
])

function selectHorizon(horizon) {
  selectedHorizon.value = horizon
}

function meterWidth(value) {
  const probability = Number(value || 0)
  return `${Math.round(Math.max(0.05, Math.min(0.98, probability)) * 100)}%`
}

function involvedAmount(item) {
  return item?.windowConsumption || item?.involvedAmount || '-'
}

onMounted(async () => {
  const data = await loadProofCasesData()
  if (data?.proofCaseHorizonSets && data?.proofCaseHorizonTabs) state.value = data
})
</script>

<template>
  <div class="page-shell proof-page">
    <section class="panel proof-hero">
      <div class="proof-hero-copy">
        <div class="proof-hero-topline">
          <span class="eyebrow">历史命中复盘</span>
          <div class="proof-hero-actions">
            <span class="status-badge status-badge-neutral">{{ displayLookupStatus.label }} · {{ displayLookupStatus.message }}</span>
            <div class="segmented-control proof-horizon-switcher" aria-label="风险窗口切换">
              <button
                v-for="tab in horizonTabs"
                :key="tab.id"
                type="button"
                :class="['segment-btn', { active: selectedHorizon === tab.id }]"
                @click="selectHorizon(tab.id)"
              >
                <strong>{{ tab.label }}</strong>
                <span>{{ tab.note }}</span>
              </button>
            </div>
          </div>
        </div>
        <h1>{{ activeSet.reportMonth }} 月报命中复盘</h1>
        <p>{{ activeSet.narrative }}</p>
      </div>
      <div class="proof-hero-card">
        <span>{{ activeSet.label }}核心样例涉及金额</span>
        <strong>{{ involvedAmount(spotlight) }}</strong>
        <p>{{ spotlight.hospital }} × {{ spotlight.drug }}</p>
      </div>
    </section>

    <div class="metric-grid proof-kpi-grid">
      <article v-for="metric in summaryMetrics" :key="metric.label" :class="['metric-card', `metric-card-${metric.tone}`]">
        <span>{{ metric.label }}</span>
        <strong>{{ metric.value }}</strong>
        <p>{{ metric.note }}</p>
      </article>
    </div>

    <div class="proof-spotlight-grid">
      <SectionCard title="核心命中案例" subtitle="按涉及金额排序">
        <article class="proof-spotlight-card">
          <div class="proof-spotlight-head">
            <span class="status-badge status-badge-ok">{{ spotlight.visible }}</span>
            <strong>{{ spotlight.horizonLabel }}</strong>
          </div>
          <h2>{{ spotlight.title }}</h2>
          <p>{{ spotlight.caseSummary }}</p>
          <div class="proof-score-grid">
            <div>
              <span>月报丢失概率</span>
              <strong>{{ spotlight.riskProbability }}</strong>
            </div>
            <div>
              <span>预测窗口消费规模</span>
              <strong>{{ spotlight.windowConsumption }}</strong>
            </div>
            <div>
              <span>涉及金额</span>
              <strong>{{ involvedAmount(spotlight) }}</strong>
            </div>
            <div>
              <span>窗口内续购</span>
              <strong>0 次</strong>
            </div>
          </div>
          <div class="proof-meter">
            <span :style="{ width: meterWidth(spotlight.riskProbabilityValue) }"></span>
          </div>
          <dl class="definition-grid compact">
            <dt>生产商</dt><dd>{{ spotlight.manufacturer }}</dd>
            <dt>月报日</dt><dd>{{ spotlight.reportDate }}</dd>
            <dt>上次采购</dt><dd>{{ spotlight.lastPurchase }} · 距月报日 {{ spotlight.daysSinceLastAtReport }}</dd>
            <dt>闭合结果</dt><dd>{{ spotlight.outcome }}</dd>
          </dl>
        </article>
      </SectionCard>

      <SectionCard title="验证时间线" subtitle="从月报输出到窗口闭合">
        <div class="proof-timeline">
          <article v-for="step in readingPath" :key="step.label" class="proof-timeline-step">
            <span>{{ step.label }}</span>
            <strong>{{ step.date }}</strong>
            <h3>{{ step.title }}</h3>
            <p>{{ step.text }}</p>
          </article>
        </div>
      </SectionCard>
    </div>

    <SectionCard title="高价值命中清单" :subtitle="`${activeSet.reportDate} ${activeSet.label}月报样例`">
      <div class="proof-case-grid">
        <article v-for="item in proofCases" :key="item.id" class="proof-case-card">
          <div class="proof-case-topline">
            <span class="status-badge status-badge-ok">{{ item.visible }}</span>
            <strong>{{ item.riskProbability }}</strong>
          </div>
          <h3>{{ item.hospital }} × {{ item.drug }}</h3>
          <p>{{ item.outcome }}</p>
          <dl class="definition-grid compact">
            <dt>生产商</dt><dd>{{ item.manufacturer }}</dd>
            <dt>涉及金额</dt><dd>{{ involvedAmount(item) }}</dd>
            <dt>窗口消费</dt><dd>{{ item.windowConsumption }}</dd>
            <dt>无续购</dt><dd>月报后 {{ item.noPurchaseAfterReport }} · 自上次采购 {{ item.noPurchaseFromLast }}</dd>
          </dl>
        </article>
      </div>
    </SectionCard>

    <SectionCard title="可核验证据链" subtitle="订单事实、月报概率与闭合结果对应">
      <div class="proof-evidence-grid">
        <article v-for="item in proofCases.slice(0, 3)" :key="`${item.id}-evidence`" class="proof-evidence-card">
          <h3>{{ item.hospital }} 证据摘要</h3>
          <ul>
            <li v-for="line in item.evidence" :key="line">{{ line }}</li>
          </ul>
        </article>
      </div>
    </SectionCard>
  </div>
</template>
