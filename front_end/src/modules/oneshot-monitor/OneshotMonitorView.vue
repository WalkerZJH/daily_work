<script setup>
import { onMounted, ref } from 'vue'
import MetricCard from '../../components/MetricCard.vue'
import SectionCard from '../../components/SectionCard.vue'
import { createStaticOneshotData, loadOneshotData } from '../monthly-demo/pageDataAdapter'

const state = ref(createStaticOneshotData())

onMounted(async () => {
  const data = await loadOneshotData()
  if (data) state.value = data
})
</script>

<template>
  <div class="page-shell oneshot-monitor">
    <div class="page-header">
      <h1>新进终端监测</h1>
      <div class="subtitle">本期新进终端 · 首采事实 · 后续复购证据</div>
    </div>

    <div class="grid-4">
      <MetricCard label="本期新进终端" :value="String(state.oneshotSummary.count)" tone="info" />
      <MetricCard v-if="state.oneshotSummary.evidenceReady" label="高复购倾向" :value="String(state.oneshotSummary.highPropensityCount)" tone="success" />
      <MetricCard v-if="state.oneshotSummary.evidenceReady" label="平均复购倾向" :value="state.oneshotSummary.averageRepurchasePropensity" tone="warning" />
      <MetricCard v-if="state.oneshotSummary.evidenceReady" label="预计复购金额" :value="state.oneshotSummary.expectedRepurchaseAmount" tone="danger" />
    </div>

    <SectionCard
      title="新进终端清单"
      :subtitle="state.oneshotSummary.evidenceReady ? '围绕首采事实和后续复购证据排序' : '当前仅展示首采事实'"
    >
      <div class="data-table-wrap">
        <table>
          <thead>
            <tr>
              <th>新进终端</th>
              <th>产品线</th>
              <th>首次采购</th>
              <th>首采金额</th>
              <th>首采后天数</th>
              <th v-if="state.oneshotSummary.evidenceReady">复购倾向</th>
              <th v-if="state.oneshotSummary.evidenceReady">预计复购金额</th>
              <th v-if="state.oneshotSummary.evidenceReady">复购促进优先级</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in state.oneshotTerminals" :key="row.id">
              <td>
                <strong>{{ row.hospital }}</strong>
                <div class="muted text-mono">{{ row.id }}</div>
              </td>
              <td>{{ row.drug }}<div class="muted">{{ row.region }}</div></td>
              <td>{{ row.firstPurchaseDate }}</td>
              <td>{{ row.firstPurchaseAmountText }}</td>
              <td>{{ row.daysSinceFirstPurchase }} 天</td>
              <td v-if="state.oneshotSummary.evidenceReady"><span class="risk-chip risk-chip-green">{{ row.repurchasePropensityText }}</span></td>
              <td v-if="state.oneshotSummary.evidenceReady">{{ row.expectedRepurchaseAmountText }}</td>
              <td v-if="state.oneshotSummary.evidenceReady">{{ row.priority }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!state.oneshotSummary.evidenceReady" class="empty">暂无复购原因或证据，仅展示新进终端首采记录</div>
    </SectionCard>

    <SectionCard v-if="state.oneshotSummary.evidenceReady" title="复购证据">
      <div class="observation-list">
        <article v-for="row in state.oneshotTerminals.filter((item) => item.reason)" :key="`${row.id}-reason`" class="observation-card">
          <div>
            <h3>{{ row.hospital }}</h3>
            <p>{{ row.reason }}</p>
          </div>
        </article>
      </div>
    </SectionCard>
  </div>
</template>
