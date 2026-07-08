<script setup>
import { computed, onMounted, ref } from 'vue'
import SectionCard from '../../components/SectionCard.vue'
import { createStaticRiskEntityDetailData, loadRiskEntityDetailData } from '../monthly-demo/pageDataAdapter'

const params = new URLSearchParams(window.location.search)
const initialData = createStaticRiskEntityDetailData(params.get('id'))
const entity = ref(initialData.entity)
const riskCardHorizonTabs = ['H3', 'H6', 'H12']
const requestedHorizon = params.get('horizon') || params.get('h')
const selectedHorizon = ref(riskCardHorizonTabs.includes(requestedHorizon) ? requestedHorizon : entity.value.horizon)
const horizonProfiles = ref(initialData.horizonProfiles)
const activeRiskCard = computed(() => horizonProfiles.value[selectedHorizon.value] || horizonProfiles.value.H6)

onMounted(async () => {
  const data = await loadRiskEntityDetailData(entity.value.id)
  if (!data) return
  entity.value = data.entity
  horizonProfiles.value = data.horizonProfiles
  if (!horizonProfiles.value[selectedHorizon.value]) selectedHorizon.value = entity.value.horizon || 'H6'
})
</script>

<template>
  <div class="page-shell">
    <a class="back-link" href="clues.html">返回风险实体清单</a>
    <div class="page-header">
      <h1>风险实体详情 · {{ entity.hospital }}</h1>
      <div class="subtitle">RiskCard 详情 · RiskEvidence 业务可见证据 · 全量 detector 结果 · XGBoost SHAP · detector 结果自然语言聚合</div>
    </div>

    <div class="grid-2">
      <SectionCard title="RiskEntity 摘要" subtitle="终端风险画像">
        <dl class="definition-grid">
          <dt>实体 ID</dt><dd class="text-mono">{{ entity.id }}</dd>
          <dt>药品</dt><dd>{{ entity.drug }}</dd>
          <dt>风险等级</dt><dd><span class="risk-chip" :class="`risk-chip-${entity.riskColor}`">{{ entity.riskLevel }}</span></dd>
          <dt>风险概率</dt><dd>{{ entity.probabilityDisplay }}</dd>
          <dt>预测窗口消费</dt><dd>{{ entity.averageConsumptionText }}</dd>
          <dt>业务评分</dt><dd>{{ entity.businessScoreText }}</dd>
          <dt>跟进状态</dt><dd>{{ entity.status }}</dd>
        </dl>
      </SectionCard>

      <SectionCard title="RiskCard 主卡">
        <div class="riskcard-toolbar">
          <div>
            <span class="eyebrow">风险卡 H 切换</span>
            <h3>{{ activeRiskCard.horizon }} · {{ activeRiskCard.label }}</h3>
          </div>
          <div class="segmented-control horizon-switcher" aria-label="风险卡 H 切换">
            <button
              v-for="horizon in riskCardHorizonTabs"
              :key="horizon"
              type="button"
              class="segment-btn"
              :class="{ active: selectedHorizon === horizon }"
              @click="selectedHorizon = horizon"
            >
              {{ horizon }}
            </button>
          </div>
        </div>
        <dl class="definition-grid compact riskcard-score-grid">
          <dt>风险概率</dt><dd>{{ activeRiskCard.probabilityDisplay }}</dd>
          <dt>预测窗口消费</dt><dd>{{ activeRiskCard.averageConsumptionText }}</dd>
          <dt>业务评分</dt><dd>{{ activeRiskCard.businessScoreText }}</dd>
        </dl>
        <p class="body-copy">{{ activeRiskCard.reason }}</p>
        <div class="notice-strip">建议动作：优先联系采购与配送负责人，确认需求节奏、竞品替代和履约稳定性。</div>
      </SectionCard>
    </div>

    <SectionCard title="Detector 结果明细" :subtitle="`${selectedHorizon} 视角 · 入选 entity 展示所有 detector 计算结果`">
      <div class="detector-result-grid">
        <article v-for="detector in activeRiskCard.detectorResults" :key="detector.id" class="detector-result-card">
          <div class="detector-result-head">
            <h3>{{ detector.name }}</h3>
            <span class="status-badge status-badge-info">{{ detector.signal }}</span>
          </div>
          <dl class="definition-grid compact">
            <dt>score</dt><dd>{{ detector.score }}</dd>
            <dt>status</dt><dd>{{ detector.status }}</dd>
            <dt>evidence</dt><dd>{{ detector.evidence }}</dd>
            <dt>action</dt><dd>{{ detector.action }}</dd>
          </dl>
        </article>
      </div>
    </SectionCard>

    <div class="grid-2">
      <SectionCard title="XGBoost SHAP">
        <div class="evidence-list">
          <div v-for="item in activeRiskCard.shapHighlights" :key="item.feature" class="evidence-row">
            <span class="evidence-dot"></span>
            <p><strong>{{ item.feature }} {{ item.contribution }}</strong><br>{{ item.explanation }}</p>
          </div>
        </div>
      </SectionCard>

      <SectionCard title="detector 结果自然语言聚合">
        <p class="body-copy">{{ activeRiskCard.detectorNarrative }}</p>
      </SectionCard>
    </div>
  </div>
</template>
