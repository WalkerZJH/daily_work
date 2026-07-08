<script setup>
import { onMounted, ref } from 'vue'
import SectionCard from '../../components/SectionCard.vue'
import { createStaticProofCasesData, loadProofCasesData } from '../monthly-demo/pageDataAdapter'

const state = ref(createStaticProofCasesData())

onMounted(async () => {
  const data = await loadProofCasesData()
  if (data) state.value = data
})
</script>

<template>
  <div class="page-shell">
    <div class="page-header">
      <h1>Proof-case 历史命中案例</h1>
      <div class="subtitle">成功案例集中呈现产品提前识别价值，案例复盘不足 20 条时展示实际数量。</div>
    </div>

    <SectionCard title="Proof-case Report" subtitle="成功案例沉淀产品效果，支撑月报复盘与客户沟通">
      <div class="report-list">
        <article v-for="item in state.proofCases" :key="item.id" class="report-card">
          <span class="status-badge status-badge-ok">{{ item.visible }}</span>
          <h3>{{ item.title }}</h3>
          <p>{{ item.outcome }}</p>
          <div class="notice-strip">{{ item.caveat }}</div>
        </article>
      </div>
    </SectionCard>
  </div>
</template>
