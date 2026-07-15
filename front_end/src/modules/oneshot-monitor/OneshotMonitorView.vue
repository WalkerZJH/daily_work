<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import MetricCard from '../../components/MetricCard.vue'
import SectionCard from '../../components/SectionCard.vue'
import { useManufacturerScope } from '../../context/manufacturerScope'
import { createEmptyOneshotData, loadOneshotData, normalizeWorkbenchQuery } from '../monthly-demo/pageDataAdapter'

const sortOptions = [
  { id: 'first_purchase_date', label: '首次采购日期' },
  { id: 'first_purchase_amount', label: '首次采购时点金额' },
  { id: 'days_since_first_purchase', label: '距首购天数' }
]
const pageSizeOptions = [20, 50, 100]
const params = new URLSearchParams(window.location.search)
const query = reactive(
  normalizeWorkbenchQuery({
    backendBaseUrl: params.get('backendBaseUrl'),
    userId: params.get('user_id') || params.get('userId'),
    demoMode: params.get('demoMode'),
    observationDate: params.get('observation_date'),
    manufacturerCode: params.get('manufacturer_code'),
    reportMonth: params.get('report_month'),
    runDate: params.get('run_date'),
    probabilityReportMonth: params.get('probability_report_month')
  })
)
const initialSortBy = sortOptions.some((item) => item.id === params.get('sort_by'))
  ? params.get('sort_by')
  : 'first_purchase_date'
const initialSortOrder = ['asc', 'desc'].includes(params.get('sort_order')) ? params.get('sort_order') : 'desc'
const initialPageSize = pageSizeOptions.includes(Number(params.get('page_size'))) ? Number(params.get('page_size')) : 20
const draftQuery = reactive({ sortBy: initialSortBy, sortOrder: initialSortOrder, pageSize: initialPageSize })
const appliedQuery = reactive({ ...draftQuery })
const currentPage = ref(Math.max(Number(params.get('page')) || 1, 1))
const state = ref(createEmptyOneshotData())
const isLoading = ref(false)
const manufacturerScope = useManufacturerScope()
const manufacturerCode = manufacturerScope.manufacturerCode
let requestSequence = 0
let pageReady = false

function syncUrl() {
  const next = new URLSearchParams(window.location.search)
  next.set('sort_by', appliedQuery.sortBy)
  next.set('sort_order', appliedQuery.sortOrder)
  next.set('page_size', String(appliedQuery.pageSize))
  next.set('page', String(currentPage.value))
  window.history.replaceState({}, '', `${window.location.pathname}?${next.toString()}`)
}

async function loadPage() {
  const sequence = ++requestSequence
  isLoading.value = true
  state.value = createEmptyOneshotData()
  try {
    const loadedState = await loadOneshotData(
      {
        ...query,
        ...appliedQuery,
        page: currentPage.value
      },
      { allowDemo: query.demoMode }
    )
    if (sequence !== requestSequence) return
    state.value = loadedState
    syncUrl()
  } finally {
    if (sequence === requestSequence) isLoading.value = false
  }
}

async function submitQuery() {
  Object.assign(appliedQuery, draftQuery)
  currentPage.value = 1
  await loadPage()
}

async function goToPage(page) {
  if (isLoading.value || page < 1 || page > state.value.pagination.totalPages || page === currentPage.value) return
  currentPage.value = page
  await loadPage()
}

onMounted(async () => {
  await manufacturerScope.initialize()
  query.manufacturerCode = manufacturerCode.value
  pageReady = true
  await loadPage()
})

watch(manufacturerCode, async (nextCode) => {
  if (!pageReady || !nextCode || nextCode === query.manufacturerCode) return
  query.manufacturerCode = nextCode
  currentPage.value = 1
  await loadPage()
})
</script>

<template>
  <div class="page-shell oneshot-monitor">
    <div class="page-header">
      <h1>新进终端工作台</h1>
      <div class="subtitle">展示截至当前数据截止月仅有一个活跃采购月份的医院—药品采购关系。</div>
    </div>

    <div class="grid-3">
      <MetricCard label="新进终端关系数" :value="String(state.oneshotSummary.count)" tone="info" />
      <MetricCard label="当前数据月份" :value="state.oneshotSummary.reportMonth || '-'" tone="info" />
      <MetricCard label="数据截止日" :value="state.oneshotSummary.cutoffDate || '-'" tone="success" />
    </div>

    <SectionCard title="查询条件" subtitle="生产企业由页面顶部统一选择">
      <div class="control-grid">
        <label class="control-field">
          <span>数据月份</span>
          <input :value="state.oneshotSummary.reportMonth || query.reportMonth || '-'" disabled />
        </label>
        <label class="control-field">
          <span>事实排序</span>
          <select v-model="draftQuery.sortBy">
            <option v-for="item in sortOptions" :key="item.id" :value="item.id">{{ item.label }}</option>
          </select>
        </label>
        <label class="control-field">
          <span>排序方向</span>
          <select v-model="draftQuery.sortOrder">
            <option value="desc">由近/高/多到远/低/少</option>
            <option value="asc">由远/低/少到近/高/多</option>
          </select>
        </label>
        <label class="control-field">
          <span>每页数量</span>
          <select v-model.number="draftQuery.pageSize">
            <option v-for="size in pageSizeOptions" :key="size" :value="size">{{ size }} 条</option>
          </select>
        </label>
        <button type="button" class="btn btn-primary" :disabled="isLoading" @click="submitQuery">
          {{ isLoading ? '查询中…' : '查询' }}
        </button>
      </div>
    </SectionCard>

    <SectionCard
      title="新进终端事实列表"
      :subtitle="state.oneshotSummary.resultBatchId ? `正式批次：${state.oneshotSummary.resultBatchId}` : '仅展示正式 One-shot 结果'"
    >
      <div v-if="isLoading" class="empty">正在读取当前生产企业的新进终端事实…</div>
      <div v-else-if="state.status === 'error'" class="empty">
        <strong>新进终端数据读取失败，请稍后重试。</strong>
        <p>{{ state.errorMessage }}</p>
      </div>
      <div v-else-if="state.status === 'ONESHOT_RESULT_NOT_AVAILABLE'" class="empty">
        <strong>当前正式批次尚未发布新进终端结果。</strong>
        <p>页面不会使用 Recurring 候选或其他兼容数据填充。</p>
      </div>
      <div v-else-if="!state.oneshotTerminals.length" class="empty">
        <strong>{{ state.emptyTitle }}</strong>
        <p>{{ state.emptyMessage }}</p>
      </div>
      <div v-else class="data-table-wrap">
        <table>
          <thead>
            <tr>
              <th>医院 × 药品</th>
              <th>首次采购日期</th>
              <th>首次采购时点金额</th>
              <th>距首购天数</th>
              <th>区域</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in state.oneshotTerminals" :key="row.id">
              <td>
                <strong>{{ row.hospital }} × {{ row.drug }}</strong>
                <div class="muted">{{ row.manufacturer }}</div>
              </td>
              <td>{{ row.firstPurchaseDate || '暂无数据' }}</td>
              <td>{{ row.firstPurchaseAmountText }}</td>
              <td>{{ row.daysSinceFirstPurchase === null || row.daysSinceFirstPurchase === undefined ? '暂无数据' : `${row.daysSinceFirstPurchase} 天` }}</td>
              <td>{{ row.region || '暂无区域信息' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="!isLoading && state.ready && state.pagination.totalPages" class="button-row">
        <button type="button" class="btn btn-outline" :disabled="currentPage <= 1" @click="goToPage(currentPage - 1)">上一页</button>
        <span class="muted">第 {{ state.pagination.page }} / {{ state.pagination.totalPages }} 页，共 {{ state.pagination.total }} 条</span>
        <button type="button" class="btn btn-outline" :disabled="currentPage >= state.pagination.totalPages" @click="goToPage(currentPage + 1)">下一页</button>
      </div>
    </SectionCard>

    <section class="notice-strip">
      新进终端表示截至当前数据截止月仅有一个活跃采购月份的医院—药品采购关系。尚未形成跨月复购历史，不等于已经流失，也不代表未来一定会或不会复购。
    </section>
  </div>
</template>
