<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import MetricCard from '../../components/MetricCard.vue'
import SectionCard from '../../components/SectionCard.vue'
import { useManufacturerScope } from '../../context/manufacturerScope'
import { createEmptyOneshotData, loadOneshotData, normalizeWorkbenchQuery } from '../monthly-demo/pageDataAdapter'

const params = new URLSearchParams(window.location.search)
const baseQuery = normalizeWorkbenchQuery({
  backendBaseUrl: params.get('backendBaseUrl'),
  userId: params.get('user_id') || params.get('userId'),
  demoMode: params.get('demoMode'),
  observationDate: params.get('observation_date'),
  manufacturerCode: params.get('manufacturer_code'),
  reportMonth: params.get('report_month')
})
const draftQuery = reactive({
  ...baseQuery,
  pageSize: Number(params.get('page_size')) || 50,
  sortBy: params.get('sort_by') || 'first_purchase_date',
  sortOrder: params.get('sort_order') || 'desc'
})
const appliedQuery = ref({ ...draftQuery, page: Math.max(1, Number(params.get('page')) || 1) })
const state = ref(createEmptyOneshotData())
const isLoading = ref(false)
const manufacturerScope = useManufacturerScope()
const manufacturerCode = manufacturerScope.manufacturerCode
let requestSequence = 0
let pageReady = false

const pagination = computed(() => state.value.pagination)
const canGoPrevious = computed(() => !isLoading.value && pagination.value.page > 1)
const canGoNext = computed(() => !isLoading.value && pagination.value.page < pagination.value.totalPages)

function syncUrl() {
  const next = new URLSearchParams(window.location.search)
  next.set('page', String(appliedQuery.value.page))
  next.set('page_size', String(appliedQuery.value.pageSize))
  next.set('sort_by', appliedQuery.value.sortBy)
  next.set('sort_order', appliedQuery.value.sortOrder)
  if (appliedQuery.value.manufacturerCode) next.set('manufacturer_code', appliedQuery.value.manufacturerCode)
  window.history.replaceState({}, '', `${window.location.pathname}?${next.toString()}`)
}

async function loadPage(query = appliedQuery.value) {
  const sequence = ++requestSequence
  isLoading.value = true
  state.value = createEmptyOneshotData()
  try {
    const loadedState = await loadOneshotData(query, { allowDemo: query.demoMode })
    if (sequence !== requestSequence) return
    state.value = loadedState
    syncUrl()
  } finally {
    if (sequence === requestSequence) isLoading.value = false
  }
}

async function submitQuery() {
  appliedQuery.value = { ...draftQuery, page: 1 }
  await loadPage()
}

async function goToPage(page) {
  if (page < 1 || (pagination.value.totalPages && page > pagination.value.totalPages)) return
  appliedQuery.value = { ...appliedQuery.value, page }
  await loadPage()
}

onMounted(async () => {
  await manufacturerScope.initialize()
  draftQuery.manufacturerCode = manufacturerCode.value
  appliedQuery.value = { ...appliedQuery.value, manufacturerCode: manufacturerCode.value }
  pageReady = true
  await loadPage()
})

watch(manufacturerCode, async (nextCode) => {
  if (!pageReady || !nextCode || nextCode === draftQuery.manufacturerCode) return
  draftQuery.manufacturerCode = nextCode
  appliedQuery.value = { ...draftQuery, page: 1 }
  await loadPage()
})
</script>

<template>
  <div class="page-shell oneshot-monitor">
    <div class="page-header">
      <h1>新进终端工作台</h1>
      <div class="subtitle">展示截至当前数据截止月仅有一个活跃采购月份的医院—药品采购关系</div>
    </div>

    <SectionCard title="查询条件">
      <div class="control-grid">
        <label class="control-field">
          <span>事实排序</span>
          <select v-model="draftQuery.sortBy">
            <option value="first_purchase_date">首次采购日期</option>
            <option value="first_purchase_amount">首次采购时点金额</option>
            <option value="days_since_first_purchase">距首购天数</option>
          </select>
        </label>
        <label class="control-field">
          <span>顺序</span>
          <select v-model="draftQuery.sortOrder">
            <option value="desc">由高/新到低/早</option>
            <option value="asc">由低/早到高/新</option>
          </select>
        </label>
        <label class="control-field">
          <span>每页条数</span>
          <select v-model.number="draftQuery.pageSize">
            <option :value="20">20</option>
            <option :value="50">50</option>
            <option :value="100">100</option>
            <option :value="200">200</option>
          </select>
        </label>
        <button type="button" class="btn btn-primary" :disabled="isLoading" @click="submitQuery">
          {{ isLoading ? '查询中…' : '查询' }}
        </button>
      </div>
    </SectionCard>

    <div class="grid-3">
      <MetricCard label="当前企业新进关系" :value="String(state.oneshotSummary.count)" tone="info" />
      <MetricCard label="数据月份" :value="state.reportMonth || '-'" tone="neutral" />
      <MetricCard label="数据截止日" :value="state.scoreCutoffDate || '-'" tone="neutral" />
    </div>

    <SectionCard title="新进终端事实列表" :subtitle="state.resultBatchId ? `正式批次：${state.resultBatchId}` : ''">
      <div v-if="isLoading" class="empty">正在读取当前生产企业的新进终端事实…</div>
      <div v-else-if="!state.oneshotTerminals.length" class="empty" :class="{ 'state-error': state.status === 'error' }">
        <strong>{{ state.emptyTitle }}</strong>
        <p>{{ state.emptyMessage }}</p>
        <button v-if="state.status === 'error'" type="button" class="btn btn-primary btn-sm" @click="loadPage()">重试</button>
      </div>
      <div v-else class="data-table-wrap">
        <table>
          <thead>
            <tr>
              <th>医院 × 药品</th>
              <th>生产企业</th>
              <th>首次采购日期</th>
              <th>首次采购时点金额</th>
              <th>距首购天数</th>
              <th>区域</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in state.oneshotTerminals" :key="row.id">
              <td><strong>{{ row.hospital }} × {{ row.drug }}</strong></td>
              <td>{{ row.manufacturer }}</td>
              <td>{{ row.firstPurchaseDate || '-' }}</td>
              <td>{{ row.firstPurchaseAmountText }}</td>
              <td>{{ row.daysSinceFirstPurchase }} 天</td>
              <td>{{ row.region || '暂无区域信息' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="state.ready && pagination.totalPages" class="oneshot-pagination">
        <span>第 {{ pagination.page }} / {{ pagination.totalPages }} 页，共 {{ pagination.total }} 条</span>
        <div>
          <button type="button" class="btn btn-sm" :disabled="!canGoPrevious" @click="goToPage(pagination.page - 1)">上一页</button>
          <button type="button" class="btn btn-sm" :disabled="!canGoNext" @click="goToPage(pagination.page + 1)">下一页</button>
        </div>
      </div>
    </SectionCard>

    <section class="notice-strip">
      <strong>事实口径</strong>
      <span>新进终端表示截至当前数据截止月仅有一个活跃采购月份的医院—药品采购关系。</span>
      <span>尚未形成跨月复购历史，不等于已经流失，也不代表未来一定会或不会复购。</span>
    </section>
  </div>
</template>

<style scoped>
.oneshot-pagination {
  align-items: center;
  display: flex;
  justify-content: space-between;
  margin-top: 16px;
}

.oneshot-pagination > div {
  display: flex;
  gap: 8px;
}

.state-error {
  color: var(--color-danger, #b42318);
}
</style>
