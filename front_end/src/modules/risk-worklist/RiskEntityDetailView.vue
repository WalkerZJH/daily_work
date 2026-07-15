<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import SectionCard from '../../components/SectionCard.vue'
import SquareDatePicker from '../../components/ui/SquareDatePicker.vue'
import {
  applyReportContextToQuery,
  buildPersistentParams,
  createEmptyClueDetailData,
  createEmptyRuleOnlyClueDetailData,
  createEmptyWorkbenchOptions,
  loadReportContext,
  loadRiskEntityDetailData,
  loadRuleOnlyClueDetailData,
  loadWorkbenchOptions,
  normalizeWorkbenchQuery
} from '../monthly-demo/pageDataAdapter'

const params = new URLSearchParams(window.location.search)
const riskEntityId = params.get('id') || params.get('riskEntityId')
const clueId = params.get('clueId')
// Candidate links may retain clueId for source traceability; candidate mode wins for compatibility.
const detailMode = riskEntityId ? 'candidate' : clueId ? 'rule-only' : 'invalid'
const draftQuery = reactive(normalizeWorkbenchQuery({
  backendBaseUrl: params.get('backendBaseUrl'),
  userId: params.get('user_id') || params.get('userId'),
  demoMode: params.get('demoMode'),
  observationDate: params.get('observation_date'),
  manufacturerCode: params.get('manufacturer_code'),
  reportMonth: params.get('report_month'),
  probabilityReportMonth: params.get('probability_report_month'),
  horizon: params.get('horizon'),
  sortBy: params.get('sort_by'),
  detectorRunDate: params.get('detector_run_date') || params.get('run_date')
}))
const appliedQuery = ref(normalizeWorkbenchQuery(draftQuery))
const options = ref(createEmptyWorkbenchOptions(draftQuery))
const candidateState = ref(createEmptyClueDetailData({ riskEntityId, query: appliedQuery.value }))
const ruleOnlyState = ref(createEmptyRuleOnlyClueDetailData({ clueId, query: appliedQuery.value }))
const reportContext = ref(candidateState.value.reportContext)
const isLoading = ref(false)

const entity = computed(() => candidateState.value.entity)
const profiles = computed(() => Object.values(candidateState.value.horizonProfiles || {}))
const evidence = computed(() => candidateState.value.detectorEvidence || [])
const ruleClue = computed(() => ruleOnlyState.value.clue)
const availableObservationDates = computed(() => (options.value.dailyDetectorDateOptions || []).map((item) => item.runDate).filter(Boolean))
const evidenceFields = computed(() => flattenEvidence(ruleClue.value?.evidencePayload))

function backHref() {
  const query = buildPersistentParams(appliedQuery.value)
  return `${detailMode === 'rule-only' ? 'clues.html' : 'index.html'}?${query.toString()}`
}

function updateUrl() {
  if (detailMode !== 'candidate') return
  window.history.replaceState({}, '', `${window.location.pathname}?${buildPersistentParams(appliedQuery.value, { id: riskEntityId, clueId }).toString()}`)
}

async function loadOptions() {
  const loaded = await loadWorkbenchOptions(draftQuery)
  options.value = loaded || createEmptyWorkbenchOptions(draftQuery)
}

async function refreshCandidateDetail() {
  isLoading.value = true
  try {
    const context = await loadReportContext(draftQuery)
    const effective = applyReportContextToQuery(draftQuery, context)
    appliedQuery.value = effective
    reportContext.value = context
    candidateState.value = await loadRiskEntityDetailData(riskEntityId, effective)
    reportContext.value = candidateState.value.reportContext || context
    updateUrl()
  } finally {
    isLoading.value = false
  }
}

async function loadRuleOnlyDetail() {
  isLoading.value = true
  try {
    ruleOnlyState.value = await loadRuleOnlyClueDetailData(clueId, appliedQuery.value)
  } finally {
    isLoading.value = false
  }
}

function formatEvidenceValue(value) {
  if (value === null || value === undefined || value === '') return '暂无数据'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function flattenEvidence(value, prefix = '') {
  if (value === null || value === undefined || value === '') return []
  if (Array.isArray(value)) return [{ key: prefix || 'evidence_payload', value }]
  if (typeof value !== 'object') return [{ key: prefix || 'evidence_payload', value }]
  return Object.entries(value).flatMap(([key, item]) => {
    const path = prefix ? `${prefix}.${key}` : key
    return item && typeof item === 'object' && !Array.isArray(item)
      ? flattenEvidence(item, path)
      : [{ key: path, value: item }]
  })
}

onMounted(async () => {
  if (detailMode === 'candidate') {
    isLoading.value = true
    try {
      await loadOptions()
    } finally {
      isLoading.value = false
    }
    await refreshCandidateDetail()
  } else if (detailMode === 'rule-only') {
    await loadRuleOnlyDetail()
  }
})
</script>

<template>
  <div class="page-shell">
    <a class="back-link" :href="backHref()">{{ detailMode === 'rule-only' ? '返回规则巡检结果' : '返回月度候选工作台' }}</a>

    <div v-if="detailMode === 'candidate'" class="page-header control-header">
      <div>
        <h1>候选对象详情</h1>
        <div class="subtitle">月度模型结果与当前观察日期的规则证据</div>
      </div>
      <div class="workbench-controls">
        <label class="control-field"><span>生产企业</span><select v-model="draftQuery.manufacturerCode"><option v-for="item in options.manufacturerOptions" :key="item.code" :value="item.code">{{ item.name }}</option></select></label>
        <SquareDatePicker v-model="draftQuery.observationDate" label="观察日期" :available-dates="availableObservationDates" />
        <button type="button" class="btn btn-primary" :disabled="isLoading" @click="refreshCandidateDetail">{{ isLoading ? '查询中…' : '刷新详情' }}</button>
      </div>
    </div>

    <div v-else-if="detailMode === 'rule-only'" class="page-header">
      <div><h1>规则线索详情</h1><div class="subtitle">Daily Detector 的事实型规则巡检记录</div></div>
    </div>

    <div v-if="detailMode === 'invalid'" class="empty"><strong>缺少详情标识</strong><p>请从月度候选工作台或规则巡检结果打开详情。</p></div>
    <div v-else-if="isLoading" class="empty">正在读取详情…</div>

    <template v-else-if="detailMode === 'rule-only'">
      <div v-if="!ruleClue" class="empty"><strong>{{ ruleOnlyState.emptyTitle }}</strong><p>{{ ruleOnlyState.emptyMessage }}</p></div>
      <template v-else>
        <SectionCard title="对象与观测上下文">
          <dl class="definition-grid">
            <dt>医院</dt><dd>{{ ruleClue.hospital || '暂无数据' }}</dd>
            <dt>药品</dt><dd>{{ ruleClue.drug || '暂无数据' }}</dd>
            <dt>生产企业</dt><dd>{{ ruleClue.manufacturer || '暂无数据' }}</dd>
            <dt>观测日期</dt><dd>{{ ruleClue.observationDate || '暂无数据' }}</dd>
            <dt>关联状态</dt><dd>{{ ruleClue.relationshipLabel }}</dd>
          </dl>
        </SectionCard>
        <SectionCard title="规则信息">
          <dl class="definition-grid">
            <dt>规则名称</dt><dd>{{ ruleClue.detectorName || '暂无数据' }}</dd>
            <dt>Detector ID</dt><dd>{{ ruleClue.detectorId || '暂无数据' }}</dd>
            <dt>Detector family</dt><dd>{{ ruleClue.detectorFamilyLabel || ruleClue.detectorFamily || '暂无数据' }}</dd>
            <dt>规则巡检分数</dt><dd>{{ ruleClue.detectorScoreText || '暂无数据' }}</dd>
            <dt v-if="ruleClue.detectorLevel">命中等级</dt><dd v-if="ruleClue.detectorLevel">{{ ruleClue.detectorLevel }}</dd>
            <dt v-if="ruleClue.confidence !== null && ruleClue.confidence !== undefined">置信信息</dt><dd v-if="ruleClue.confidence !== null && ruleClue.confidence !== undefined">{{ ruleClue.confidence }}</dd>
          </dl>
        </SectionCard>
        <SectionCard title="命中说明">
          <dl class="definition-grid"><dt>证据说明</dt><dd>{{ ruleClue.evidenceText || '当前规则未提供该字段' }}</dd><dt>规则原因</dt><dd>{{ ruleClue.rootCause || '当前规则未提供该字段' }}</dd></dl>
        </SectionCard>
        <SectionCard title="证据详情">
          <div v-if="!evidenceFields.length" class="empty">当前规则未提供证据 payload。</div>
          <dl v-else class="definition-grid"><template v-for="field in evidenceFields" :key="field.key"><dt>{{ field.key }}</dt><dd>{{ formatEvidenceValue(field.value) }}</dd></template></dl>
        </SectionCard>
        <section class="notice-strip context-notice"><strong>口径说明</strong><span>规则巡检分数不是月度风险概率。</span><span>仅规则命中不会创建 Recurring 风险候选对象。</span></section>
      </template>
    </template>

    <template v-else>
      <section v-if="reportContext?.displayTitle" class="notice-strip context-notice"><strong>{{ reportContext.displayTitle }}</strong><span v-for="line in reportContext.displayLines" :key="line">{{ line }}</span></section>
      <div v-if="!entity" class="empty"><strong>{{ candidateState.emptyTitle }}</strong><p>{{ candidateState.emptyMessage }}</p></div>
      <template v-else>
        <SectionCard title="对象与当前月度结果" subtitle="该结果来自月度候选排序，不由 detector 生成"><dl class="definition-grid"><dt>医院 × 药品</dt><dd>{{ entity.hospital }} × {{ entity.drug }}</dd><dt>生产企业</dt><dd>{{ entity.manufacturer }}</dd><dt>观察日期</dt><dd>{{ appliedQuery.observationDate }}</dd><dt>预测窗口</dt><dd>{{ entity.horizon }}</dd><dt>月度概率</dt><dd>{{ entity.probabilityDisplay }}</dd><dt>涉及金额</dt><dd>{{ entity.involvedAmountText }}</dd><dt>风险展示等级</dt><dd>{{ entity.riskLevel }}</dd></dl></SectionCard>
        <SectionCard title="H3 / H6 / H12 月度结果" subtitle="不同预测窗口相互独立"><div class="data-table-wrap"><table><thead><tr><th>窗口</th><th>月度概率</th><th>涉及金额</th><th>展示等级</th></tr></thead><tbody><tr v-for="profile in profiles" :key="profile.horizon"><td>{{ profile.horizon }}</td><td>{{ profile.riskProbabilityText }}</td><td>{{ profile.involvedAmountText }}</td><td>{{ profile.riskLevel }}</td></tr></tbody></table></div></SectionCard>
        <SectionCard title="当前日期命中的规则证据" subtitle="规则仅提供事实证据，不改变候选池、排序、概率或金额"><div v-if="!evidence.length" class="empty">当前 observation_date 没有该候选对象的 detector 命中。</div><div v-else class="definition-grid" v-for="item in evidence" :key="`${item.detectorId}-${item.detectorRunDate}`"><dt>规则名称</dt><dd>{{ item.detectorName }}</dd><dt>命中说明</dt><dd>{{ item.evidenceText || '-' }}</dd><dt>当前值</dt><dd>{{ item.currentValueText || '-' }}</dd><dt>历史基准</dt><dd>{{ item.baselineValueText || '-' }}</dd><dt>比较值 / 阈值</dt><dd>{{ item.comparisonText || '-' }}</dd><dt>备注</dt><dd>{{ item.caveat || '-' }}</dd></div></SectionCard>
      </template>
    </template>
  </div>
</template>
