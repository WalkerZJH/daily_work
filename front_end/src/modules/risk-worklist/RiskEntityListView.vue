<script setup>
import { computed, onMounted, ref } from 'vue'
import SectionCard from '../../components/SectionCard.vue'
import { createStaticRiskEntitiesData, loadRiskEntitiesData } from '../monthly-demo/pageDataAdapter'

const state = ref(createStaticRiskEntitiesData())
const sortedRiskEntities = computed(() => [...state.value.riskEntities].sort((a, b) => b.businessScore - a.businessScore))

onMounted(async () => {
  const data = await loadRiskEntitiesData()
  if (data) state.value = data
})

function formatMoney(value) {
  return `¥${value.toLocaleString('zh-CN')}`
}
</script>

<template>
  <div class="page-shell">
    <div class="page-header">
      <h1>风险实体清单</h1>
      <div class="subtitle">月报候选池 · 风险概率 · 预测窗口内平均消费金额 · 概率 × 预测窗口内平均消费金额排序 · 证据链摘要</div>
    </div>

    <SectionCard title="RiskEntity / RiskCard 工作清单" subtitle="按 businessScore 从高到低排序，优先处理高业务影响的高风险 entity">
      <div class="data-table-wrap">
        <table>
          <thead>
            <tr>
              <th>排序</th>
              <th>RiskEntity</th>
              <th>药品/产品线</th>
              <th>风险概率</th>
              <th>预测窗口内平均消费金额</th>
              <th>业务评分</th>
              <th>最近采购</th>
              <th>RiskCard</th>
              <th>人工复核</th>
              <th>主原因</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(entity, index) in sortedRiskEntities" :key="entity.id">
              <td><strong>#{{ index + 1 }}</strong></td>
              <td>
                <strong>{{ entity.hospital }}</strong>
                <div class="muted text-mono">{{ entity.id }}</div>
              </td>
              <td>{{ entity.drug }}</td>
              <td>
                <span class="risk-chip" :class="`risk-chip-${entity.riskColor}`">{{ entity.probabilityDisplay }}</span>
                <div class="muted">{{ entity.riskLevel }}</div>
              </td>
              <td>{{ formatMoney(entity.averageConsumptionInWindow) }}</td>
              <td><strong>{{ formatMoney(entity.businessScore) }}</strong></td>
              <td>{{ entity.lastPurchase }}<div class="muted">{{ entity.daysSinceLast }} 天</div></td>
              <td>{{ entity.cards }} 张</td>
              <td>{{ entity.status }}</td>
              <td>{{ entity.reason }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </SectionCard>
  </div>
</template>
