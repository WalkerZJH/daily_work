<script setup>
import { computed, onMounted, ref } from 'vue'
import MetricCard from '../../components/MetricCard.vue'
import SectionCard from '../../components/SectionCard.vue'
import { createStaticWorkbenchData, loadWorkbenchData } from '../monthly-demo/pageDataAdapter'

const state = ref(createStaticWorkbenchData())

const dailyDetectorMetrics = computed(() => [
  { label: '今日巡检日期', value: state.value.dailyDetectorStatus.runDate || '-', tone: 'info' },
  { label: '今日规则线索', value: String(state.value.dailyDetectorStatus.clueCount ?? '-'), tone: 'warning' },
  { label: '已附着规则证据', value: String(state.value.dailyDetectorStatus.attachedHighRiskCount ?? '-'), tone: 'success' },
  { label: '巡检对象', value: String(state.value.dailyDetectorStatus.scannedEntityCount ?? '-'), tone: 'neutral' }
])

onMounted(async () => {
  const data = await loadWorkbenchData()
  if (data) state.value = data
})
</script>

<template>
  <div class="page-shell monthly-workbench">
    <div class="page-header">
      <h1>月报高风险工作台</h1>
      <div class="subtitle">
        report_month={{ state.batchContext.reportMonth }} · score_as_of_date={{ state.batchContext.scoreAsOfDate }} · {{ state.batchContext.primaryHorizon }}
      </div>
    </div>

    <section class="workbench-hero panel">
      <div>
        <span class="eyebrow">Monthly Risk + Daily Rule Inspection</span>
        <h2>月报主风险保持稳定复现，今日变化来自规则巡检结果</h2>
        <p>
          本页展示生产商 {{ state.workbenchFillPolicy.manufacturer }} 视角下的月报高风险医院 × 药品对象。月报丢失概率来自低频稳定批次；
          每日变化来自规则巡检结果，巡检分只用于筛选值得注意的对象，不代表业务紧迫度。
        </p>
      </div>
      <div class="batch-card">
        <div class="batch-row"><span>月报批次</span><strong>{{ state.batchContext.scoreBatchId }}</strong></div>
        <div class="batch-row"><span>数据水位</span><strong>{{ state.batchContext.dataWatermarkAt }}</strong></div>
        <div class="batch-row"><span>默认风险窗口</span><strong>{{ state.batchContext.primaryHorizon }}</strong></div>
        <div class="batch-row"><span>损失价值</span><strong>{{ state.batchContext.scoreFormula }}</strong></div>
        <div class="batch-row"><span>工作台容量</span><strong>{{ state.workbenchFillPolicy.workbenchTargetCount }} 个医院 × 药品</strong></div>
      </div>
    </section>

    <div class="grid-4">
      <MetricCard
        v-for="item in state.overviewMetrics"
        :key="item.label"
        :label="item.label"
        :value="item.value"
        :tone="item.tone"
      />
    </div>

    <SectionCard title="今日规则巡检摘要" subtitle="今日巡检结果每天变化，月报批次结论保持稳定">
      <div class="grid-4">
        <MetricCard
          v-for="item in dailyDetectorMetrics"
          :key="item.label"
          :label="item.label"
          :value="item.value"
          :tone="item.tone"
        />
      </div>
      <div class="detector-status-row">
        <span class="status-badge status-badge-neutral">{{ state.dailyDetectorStatus.sourceLabel }}</span>
        <strong>{{ state.dailyDetectorStatus.statusText }}</strong>
        <span>{{ state.dailyDetectorStatus.caveat }}</span>
      </div>
      <div class="catalog-strip">
        <article v-for="detector in state.detectorCatalogSummary" :key="detector.id" class="catalog-chip">
          <strong>{{ detector.name }}</strong>
          <span>{{ detector.family }} · {{ detector.statusLabel }}</span>
        </article>
      </div>
      <div class="notice-strip">{{ state.detectorConfigStatus.message }}</div>
    </SectionCard>

    <SectionCard title="月报高风险对象 20 个医院 × 药品行为" subtitle="按损失价值排序：月报丢失概率 × 预测窗口内平均消费金额">
      <div class="data-table-wrap">
        <table>
          <thead>
            <tr>
              <th>排序</th>
              <th>生产商</th>
              <th>医院 × 药品</th>
              <th>来源</th>
              <th>月报丢失概率</th>
              <th>预测窗口消费</th>
              <th>损失价值</th>
              <th>动作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in state.workbenchDisplayRows" :key="row.id">
              <td><strong>#{{ index + 1 }}</strong></td>
              <td>{{ row.manufacturer }}</td>
              <td>
                <strong>{{ row.hospitalDrugKey }}</strong>
                <div class="muted">{{ row.region }}</div>
              </td>
              <td>
                <span class="status-badge status-badge-info">{{ row.sourceType }}</span>
                <div class="muted">{{ row.fillSource }}</div>
              </td>
              <td>{{ row.probabilityDisplay }}</td>
              <td>{{ row.averageConsumptionText }}</td>
              <td><strong>{{ row.lossValueText || row.businessScoreText }}</strong></td>
              <td>
                <a v-if="row.entityId" class="btn btn-primary btn-sm" :href="`clue-detail.html?id=${row.entityId}`">查看月报风险详情</a>
                <span v-else class="status-badge status-badge-neutral">{{ row.action }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </SectionCard>
  </div>
</template>
