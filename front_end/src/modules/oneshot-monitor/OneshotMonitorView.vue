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
      <div class="subtitle">oneshot · 本期新进终端 · 首次采购后复购倾向 · 复购促进优先级</div>
    </div>

    <div class="grid-4">
      <MetricCard label="本期新进终端" :value="String(state.oneshotSummary.count)" tone="info" />
      <MetricCard label="高复购倾向" :value="String(state.oneshotSummary.highPropensityCount)" tone="success" />
      <MetricCard label="平均复购倾向" :value="state.oneshotSummary.averageRepurchasePropensity" tone="warning" />
      <MetricCard label="预计复购金额" :value="state.oneshotSummary.expectedRepurchaseAmount" tone="danger" />
    </div>

    <SectionCard title="oneshot 复购倾向清单" subtitle="围绕首采金额、首采后天数、区域同类终端表现和预计复购金额排序">
      <div class="data-table-wrap">
        <table>
          <thead>
            <tr>
              <th>新进终端</th>
              <th>产品线</th>
              <th>首次采购</th>
              <th>首采金额</th>
              <th>首采后天数</th>
              <th>复购倾向</th>
              <th>预计复购金额</th>
              <th>复购促进优先级</th>
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
              <td><span class="risk-chip risk-chip-green">{{ row.repurchasePropensityText }}</span></td>
              <td>{{ row.expectedRepurchaseAmountText }}</td>
              <td>{{ row.priority }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </SectionCard>

    <SectionCard title="复购倾向解释">
      <div class="observation-list">
        <article v-for="row in state.oneshotTerminals" :key="`${row.id}-reason`" class="observation-card">
          <div>
            <h3>{{ row.hospital }}</h3>
            <p>{{ row.reason }}</p>
          </div>
        </article>
      </div>
    </SectionCard>
  </div>
</template>
