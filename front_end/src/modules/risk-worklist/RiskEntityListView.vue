<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import SectionCard from '../../components/SectionCard.vue'
import {
  createStaticRuleCluesData,
  createStaticWorkbenchOptions,
  loadRuleCluesData,
  loadWorkbenchOptions,
  normalizeWorkbenchQuery
} from '../monthly-demo/pageDataAdapter'

const params = new URLSearchParams(window.location.search)
const query = reactive(
  normalizeWorkbenchQuery({
    manufacturerCode: params.get('manufacturer_code'),
    reportMonth: params.get('report_month'),
    runDate: params.get('run_date'),
    horizon: params.get('horizon') || params.get('h')
  })
)

const options = ref(createStaticWorkbenchOptions())
const state = ref(createStaticRuleCluesData(query))
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

function detailHref(clue) {
  const next = new URLSearchParams({
    clueId: clue.id,
    manufacturer_code: query.manufacturerCode,
    report_month: query.reportMonth,
    run_date: query.runDate,
    horizon: query.horizon
  })
  if (clue.riskEntityId) next.set('id', clue.riskEntityId)
  return `clue-detail.html?${next.toString()}`
}

async function refreshClues() {
  const fallback = createStaticRuleCluesData(query)
  const data = await loadRuleCluesData(query)
  state.value = data || fallback
}

onMounted(async () => {
  const loadedOptions = await loadWorkbenchOptions(query)
  if (loadedOptions) options.value = loadedOptions
  await refreshClues()
})

watch(() => [query.runDate, query.horizon, query.manufacturerCode], refreshClues)
</script>

<template>
  <div class="page-shell">
    <div class="page-header control-header">
      <div>
        <h1>今日巡检线索</h1>
        <div class="subtitle">{{ query.runDate }} · 规则巡检 · {{ options.horizonOptions.find((item) => item.id === query.horizon)?.label }}</div>
      </div>
      <div class="workbench-controls">
        <label class="control-field">
          <span>生产企业</span>
          <select v-model="query.manufacturerCode">
            <option v-for="item in options.manufacturerOptions" :key="item.code" :value="item.code">{{ item.name }}</option>
          </select>
        </label>
        <label class="control-field">
          <span>日报日期</span>
          <select v-model="query.runDate">
            <option v-for="item in options.dailyDetectorDateOptions" :key="item.runDate" :value="item.runDate">{{ item.label }}</option>
          </select>
        </label>
      </div>
    </div>

    <section class="panel clue-hero">
      <div>
        <span class="eyebrow">今日巡检线索</span>
        <h2>今日巡检线索</h2>
        <p>
          月报高风险对象上的规则命中会附着到风险卡；未进入月报高风险清单但被规则命中的对象，仅作为今日巡检线索展示。
        </p>
      </div>
      <div class="batch-card">
        <div class="batch-row"><span>日报日期</span><strong>{{ state.dailyDetectorStatus.runDate }}</strong></div>
        <div class="batch-row"><span>今日巡检线索</span><strong>{{ state.dailyDetectorStatus.clueCount }}</strong></div>
        <div class="batch-row"><span>已附着证据</span><strong>{{ state.dailyDetectorStatus.attachedHighRiskCount }}</strong></div>
        <div class="batch-row"><span>数据来源</span><strong>{{ state.dailyDetectorStatus.sourceLabel }}</strong></div>
      </div>
    </section>

    <SectionCard title="线索筛选" subtitle="按线索来源查看今日巡检结果">
      <div class="control-grid">
        <div class="control-group">
          <span class="control-label">预测窗口</span>
          <div class="segmented-control">
            <button
              v-for="item in options.horizonOptions"
              :key="item.id"
              type="button"
              class="segment-btn"
              :class="{ active: query.horizon === item.id }"
              @click="query.horizon = item.id"
            >
              {{ item.label }}
            </button>
          </div>
        </div>
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
                <span class="status-badge" :class="clue.isMonthlyHighRiskEntity ? 'status-badge-error' : 'status-badge-neutral'">
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
                  <span>丢失概率 {{ clue.monthlyRiskProbabilityText }}</span>
                  <div class="muted">涉及金额 {{ clue.involvedAmountText }}</div>
                </template>
                <span v-else class="muted">今日巡检线索，按规则证据单独观察</span>
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
