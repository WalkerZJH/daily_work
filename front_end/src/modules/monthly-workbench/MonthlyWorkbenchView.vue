<script setup>
import { onMounted, ref } from 'vue'
import MetricCard from '../../components/MetricCard.vue'
import SectionCard from '../../components/SectionCard.vue'
import { createStaticWorkbenchData, loadWorkbenchData } from '../monthly-demo/pageDataAdapter'

const state = ref(createStaticWorkbenchData())

onMounted(async () => {
  const data = await loadWorkbenchData()
  if (data) state.value = data
})
</script>

<template>
  <div class="page-shell monthly-workbench">
    <div class="page-header">
      <h1>月报工作清单</h1>
      <div class="subtitle">
        report_month={{ state.batchContext.reportMonth }} · score_as_of_date={{ state.batchContext.scoreAsOfDate }} · {{ state.batchContext.primaryHorizon }}
      </div>
    </div>

    <section class="workbench-hero panel">
      <div>
        <span class="eyebrow">MonthlyReport / RiskResultBatch</span>
        <h2>生产商主视角：按医院 × 药品行为排序，默认每期推荐20到50个</h2>
        <p>
          用户视角是生产商 {{ state.workbenchFillPolicy.manufacturer }} 看到的医院采购药品行为。global 当月医院 × 药品数量为
          {{ state.globalCurrentMonthHospitalDrugCount }}，主视角直接用补充算法填充到 20 个，再按“概率 × 预测窗口内平均消费金额”的业务评分排序。
          高价值终端可继续进入 RiskEntity 和 RiskCard 详情生成建议动作。
        </p>
      </div>
      <div class="batch-card">
        <div class="batch-row"><span>score_batch_id</span><strong>{{ state.batchContext.scoreBatchId }}</strong></div>
        <div class="batch-row"><span>data_watermark_at</span><strong>{{ state.batchContext.dataWatermarkAt }}</strong></div>
        <div class="batch-row"><span>默认风险窗口</span><strong>{{ state.batchContext.primaryHorizon }}</strong></div>
        <div class="batch-row"><span>score_formula</span><strong>{{ state.batchContext.scoreFormula }}</strong></div>
        <div class="batch-row"><span>workbench_target</span><strong>{{ state.workbenchFillPolicy.workbenchTargetCount }} 个医院 × 药品</strong></div>
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

    <SectionCard title="模型关键指标" subtitle="主干模型、新进终端复购倾向与证据模块的回测表现">
      <div class="data-table-wrap">
        <table>
          <thead>
            <tr>
              <th>模型</th>
              <th>窗口</th>
              <th>AUC</th>
              <th>PRAUC</th>
              <th>PR-AUC Lift</th>
              <th>ECE</th>
              <th>Brier</th>
              <th>前列名单表现</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="metric in state.modelMetrics" :key="metric.id">
              <td>
                <strong>{{ metric.name }}</strong>
                <div class="muted">{{ metric.role }}</div>
              </td>
              <td>
                <strong>{{ metric.horizon }}</strong>
                <div class="muted">{{ metric.window }}</div>
              </td>
              <td>{{ metric.auc }}</td>
              <td>{{ metric.prauc }}</td>
              <td>{{ metric.praucLift }}</td>
              <td>{{ metric.ece }}</td>
              <td>{{ metric.brier }}</td>
              <td>
                <strong>{{ metric.topK }}</strong>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </SectionCard>

    <SectionCard title="主工作台 20 个医院 × 药品行为" subtitle="6月主视角 · global 当月数量不足时，直接由补充算法填充到 20 个">
      <div class="data-table-wrap">
        <table>
          <thead>
            <tr>
              <th>排序</th>
              <th>生产商</th>
              <th>医院 × 药品</th>
              <th>来源算法</th>
              <th>风险概率</th>
              <th>预测窗口消费</th>
              <th>业务评分</th>
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
              <td><strong>{{ row.businessScoreText }}</strong></td>
              <td>
                <a v-if="row.entityId" class="btn btn-primary btn-sm" :href="`clue-detail.html?id=${row.entityId}`">查看风险卡</a>
                <span v-else class="status-badge status-badge-neutral">{{ row.action }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </SectionCard>
  </div>
</template>
