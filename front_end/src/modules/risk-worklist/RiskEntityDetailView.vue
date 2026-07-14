<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import SectionCard from '../../components/SectionCard.vue'
import SquareDatePicker from '../../components/ui/SquareDatePicker.vue'
import {
  applyReportContextToQuery,
  buildPersistentParams,
  createEmptyClueDetailData,
  createEmptyWorkbenchOptions,
  loadReportContext,
  loadRiskEntityDetailData,
  loadWorkbenchOptions,
  normalizeWorkbenchQuery
} from '../monthly-demo/pageDataAdapter'

const params = new URLSearchParams(window.location.search)
const riskEntityId = params.get('id') || params.get('riskEntityId')
const draftQuery = reactive(normalizeWorkbenchQuery({
  backendBaseUrl: params.get('backendBaseUrl'),
  userId: params.get('user_id') || params.get('userId'),
  demoMode: params.get('demoMode'),
  observationDate: params.get('observation_date'),
  manufacturerCode: params.get('manufacturer_code'),
  reportMonth: params.get('report_month'),
  probabilityReportMonth: params.get('probability_report_month'),
  horizon: params.get('horizon'),
  sortBy: params.get('sort_by')
}))
const appliedQuery = ref(normalizeWorkbenchQuery(draftQuery))
const options = ref(createEmptyWorkbenchOptions(draftQuery))
const state = ref(createEmptyClueDetailData({ riskEntityId, query: appliedQuery.value }))
const reportContext = ref(state.value.reportContext)
const isLoading = ref(false)

const entity = computed(() => state.value.entity)
const profiles = computed(() => Object.values(state.value.horizonProfiles || {}))
const evidence = computed(() => state.value.detectorEvidence || [])
const availableObservationDates = computed(() => (options.value.dailyDetectorDateOptions || []).map((item) => item.runDate).filter(Boolean))

function backHref() {
  return `clues.html?${buildPersistentParams(appliedQuery.value).toString()}`
}

function updateUrl() {
  window.history.replaceState({}, '', `${window.location.pathname}?${buildPersistentParams(appliedQuery.value, { id: riskEntityId }).toString()}`)
}

async function loadOptions() {
  const loaded = await loadWorkbenchOptions(draftQuery)
  options.value = loaded || createEmptyWorkbenchOptions(draftQuery)
}

async function refreshDetail() {
  if (!riskEntityId) return
  isLoading.value = true
  try {
    const context = await loadReportContext(draftQuery)
    const effective = applyReportContextToQuery(draftQuery, context)
    appliedQuery.value = effective
    reportContext.value = context
    state.value = await loadRiskEntityDetailData(riskEntityId, effective)
    reportContext.value = state.value.reportContext || context
    updateUrl()
  } finally {
    isLoading.value = false
  }
}

onMounted(async () => {
  isLoading.value = true
  try {
    await loadOptions()
  } finally {
    isLoading.value = false
  }
  await refreshDetail()
})
</script>

<template>
  <div class="page-shell">
    <a class="back-link" :href="backHref()">返回规则巡检结果</a>
    <div class="page-header control-header">
      <div>
        <h1>候选对象详情</h1>
        <div class="subtitle">月度模型结果与当前观察日期的规则证据</div>
      </div>
      <div class="workbench-controls">
        <label class="control-field"><span>生产企业</span><select v-model="draftQuery.manufacturerCode"><option v-for="item in options.manufacturerOptions" :key="item.code" :value="item.code">{{ item.name }}</option></select></label>
        <SquareDatePicker v-model="draftQuery.observationDate" label="观察日期" :available-dates="availableObservationDates" />
        <button type="button" class="btn btn-primary" :disabled="isLoading" @click="refreshDetail">{{ isLoading ? '查询中…' : '刷新详情' }}</button>
      </div>
    </div>

    <section v-if="reportContext?.displayTitle" class="notice-strip context-notice">
      <strong>{{ reportContext.displayTitle }}</strong>
      <span v-for="line in reportContext.displayLines" :key="line">{{ line }}</span>
    </section>

    <div v-if="!riskEntityId" class="empty"><strong>缺少候选对象标识</strong><p>请从候选对象排序工作台或列表打开详情。</p></div>
    <div v-else-if="isLoading" class="empty">正在读取候选对象详情…</div>
    <div v-else-if="!entity" class="empty"><strong>{{ state.emptyTitle }}</strong><p>{{ state.emptyMessage }}</p></div>

    <template v-else>
      <SectionCard title="对象与当前月度结果" subtitle="该结果来自月度候选排序，不由 detector 生成">
        <dl class="definition-grid">
          <dt>医院 × 药品</dt><dd>{{ entity.hospital }} × {{ entity.drug }}</dd>
          <dt>生产企业</dt><dd>{{ entity.manufacturer }}</dd>
          <dt>观察日期</dt><dd>{{ appliedQuery.observationDate }}</dd>
          <dt>预测窗口</dt><dd>{{ entity.horizon }}</dd>
          <dt>月度概率</dt><dd>{{ entity.probabilityDisplay }}</dd>
          <dt>涉及金额</dt><dd>{{ entity.involvedAmountText }}</dd>
          <dt>风险展示等级</dt><dd>{{ entity.riskLevel }}</dd>
        </dl>
      </SectionCard>

      <SectionCard title="H3 / H6 / H12 月度结果" subtitle="不同预测窗口相互独立">
        <div class="data-table-wrap"><table><thead><tr><th>窗口</th><th>月度概率</th><th>涉及金额</th><th>展示等级</th></tr></thead><tbody><tr v-for="profile in profiles" :key="profile.horizon"><td>{{ profile.horizon }}</td><td>{{ profile.riskProbabilityText }}</td><td>{{ profile.involvedAmountText }}</td><td>{{ profile.riskLevel }}</td></tr></tbody></table></div>
      </SectionCard>

      <SectionCard title="当前日期命中的规则证据" subtitle="规则仅提供事实证据，不改变候选池、排序、概率或金额">
        <div v-if="!evidence.length" class="empty">当前 observation_date 没有该候选对象的 detector 命中。</div>
        <div v-else class="definition-grid" v-for="item in evidence" :key="`${item.detectorId}-${item.detectorRunDate}`">
          <dt>规则名称</dt><dd>{{ item.detectorName }}</dd>
          <dt>命中说明</dt><dd>{{ item.evidenceText || '-' }}</dd>
          <dt>当前值</dt><dd>{{ item.currentValueText || '-' }}</dd>
          <dt>历史基准</dt><dd>{{ item.baselineValueText || '-' }}</dd>
          <dt>比较值 / 阈值</dt><dd>{{ item.comparisonText || '-' }}</dd>
          <dt>备注</dt><dd>{{ item.caveat || '-' }}</dd>
        </div>
      </SectionCard>
    </template>
  </div>
</template>
