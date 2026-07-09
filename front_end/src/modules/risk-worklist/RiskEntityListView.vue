<script setup>
import { computed, onMounted, ref } from 'vue'
import SectionCard from '../../components/SectionCard.vue'
import { createStaticRuleCluesData, loadRuleCluesData } from '../monthly-demo/pageDataAdapter'

const state = ref(createStaticRuleCluesData())
const activeFilter = ref('all')

const filterTabs = [
  { id: 'all', label: '全部规则线索' },
  { id: 'monthly', label: '月报高风险对象' },
  { id: 'rule_only', label: '仅规则命中' }
]

const filteredClues = computed(() => {
  const items = state.value.dailyDetectorClues || []
  if (activeFilter.value === 'monthly') return items.filter((item) => item.isMonthlyHighRiskEntity)
  if (activeFilter.value === 'rule_only') return items.filter((item) => !item.isMonthlyHighRiskEntity)
  return items
})

onMounted(async () => {
  const data = await loadRuleCluesData()
  if (data) state.value = data
})

function detailHref(clue) {
  const params = new URLSearchParams({ clueId: clue.id })
  if (clue.riskEntityId) params.set('id', clue.riskEntityId)
  return `clue-detail.html?${params.toString()}`
}
</script>

<template>
  <div class="page-shell">
    <div class="page-header">
      <h1>今日规则线索</h1>
      <div class="subtitle">
        {{ state.dailyDetectorStatus.runDate }} · detector 纯规则巡检 · 非月报对象仅作为今日规则线索展示
      </div>
    </div>

    <section class="panel clue-hero">
      <div>
        <span class="eyebrow">Daily Rule Clues</span>
        <h2>今日巡检结果每天更新，月报批次结论保持稳定</h2>
        <p>
          月报高风险对象上的 detector 命中会附着到风险卡；未进入月报高风险清单但被规则命中的对象，进入今日规则线索池并按巡检证据单独观察。
        </p>
      </div>
      <div class="batch-card">
        <div class="batch-row"><span>巡检日期</span><strong>{{ state.dailyDetectorStatus.runDate }}</strong></div>
        <div class="batch-row"><span>今日规则线索</span><strong>{{ state.dailyDetectorStatus.clueCount }}</strong></div>
        <div class="batch-row"><span>已附着规则证据</span><strong>{{ state.dailyDetectorStatus.attachedHighRiskCount }}</strong></div>
        <div class="batch-row"><span>数据状态</span><strong>{{ state.dailyDetectorStatus.sourceLabel }}</strong></div>
      </div>
    </section>

    <SectionCard title="线索筛选" subtitle="巡检分只用于规则筛选，也不代表业务紧迫度">
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
    </SectionCard>

    <SectionCard title="全部规则线索" subtitle="包含月报高风险对象和仅规则命中对象">
      <div class="data-table-wrap">
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
                <span
                  class="status-badge"
                  :class="clue.isMonthlyHighRiskEntity ? 'status-badge-error' : 'status-badge-neutral'"
                >
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
                  <span>月报丢失概率 {{ clue.monthlyRiskProbabilityText }}</span>
                  <div class="muted">损失价值 {{ clue.lossValueText }}</div>
                </template>
                <span v-else class="muted">今日规则线索，按巡检证据单独观察</span>
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
