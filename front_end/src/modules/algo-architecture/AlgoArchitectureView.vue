<script setup>
import { onMounted, ref } from 'vue'
import SectionCard from '../../components/SectionCard.vue'
import { BackendApi } from '../../services/backendApi'
import { normalizeWorkbenchQuery } from '../monthly-demo/pageDataAdapter'

const params = new URLSearchParams(window.location.search)
const query = normalizeWorkbenchQuery(Object.fromEntries(params.entries()))
const catalog = ref([])
const runtimeProfile = ref(null)
const configStatus = ref(null)
const isLoading = ref(false)

onMounted(async () => {
  if (!query.backendBaseUrl) return
  isLoading.value = true
  try {
    const api = new BackendApi(query.backendBaseUrl, query.userId)
    const [catalogPayload, configPayload, runtimePayload] = await Promise.allSettled([
      api.getDetectorCatalog({ manufacturer_code: query.manufacturerCode }),
      api.getDetectorConfigStatus({
        observation_date: query.observationDate,
        report_month: query.probabilityReportMonth || query.reportMonth,
        run_date: query.detectorRunDate || query.runDate,
        horizon: query.horizon,
        manufacturer_code: query.manufacturerCode,
        user_id: query.userId
      }),
      api.getRuntimeProfile({ report_month: query.probabilityReportMonth || query.reportMonth })
    ])
    if (catalogPayload.status === 'fulfilled') {
      catalog.value = catalogPayload.value?.items || catalogPayload.value?.detectors || []
    }
    if (configPayload.status === 'fulfilled') configStatus.value = configPayload.value
    if (runtimePayload.status === 'fulfilled') runtimeProfile.value = runtimePayload.value
  } finally {
    isLoading.value = false
  }
})

const modules = [
  { key: 'M0', title: '观察上下文', text: '由 Project API 解析观察日期、概率基准月与规则巡检日期。' },
  { key: 'M1-M3', title: '月报概率链路', text: '读取后端 formal result batch 对应的月报风险对象，不在前端读取本地结果文件。' },
  { key: 'M4-M6', title: '规则巡检链路', text: '使用 daily detector API 展示规则线索、证据与巡检状态。' },
  { key: 'M7-M8', title: '展示与复盘', text: '工作台、详情页、复盘页只展示 Project API 返回的正式数据或空状态。' }
]
</script>

<template>
  <div class="page-shell">
    <div class="page-header">
      <h1>算法链路说明</h1>
      <div class="subtitle">内部说明页 · 不进入客户主导航</div>
    </div>

    <div class="grid-4">
      <article v-for="item in modules" :key="item.key" class="metric-card metric-card-info">
        <span>{{ item.key }}</span>
        <strong>{{ item.title }}</strong>
        <p>{{ item.text }}</p>
      </article>
    </div>

    <SectionCard title="观察上下文语义" subtitle="日期字段由 /api/v1/report-context 或页面 API 内嵌上下文决定">
      <dl class="definition-grid compact">
        <dt>观察日期</dt><dd>{{ query.observationDate || '-' }}</dd>
        <dt>概率基准月</dt><dd>{{ query.probabilityReportMonth || query.reportMonth || '-' }}</dd>
        <dt>规则巡检日期</dt><dd>{{ query.detectorRunDate || query.runDate || '-' }}</dd>
        <dt>预测窗口</dt><dd>{{ query.horizon }}</dd>
      </dl>
    </SectionCard>

    <SectionCard title="规则能力目录" subtitle="仅在内部模式查看 detector 状态">
      <div v-if="isLoading" class="empty">刷新中</div>
      <div v-else-if="!catalog.length" class="empty">接口未就绪或暂无规则能力目录</div>
      <div v-else class="data-table-wrap">
        <table>
          <thead>
            <tr>
              <th>规则</th>
              <th>大类</th>
              <th>状态</th>
              <th>说明</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in catalog" :key="item.detector_id || item.id">
              <td>{{ item.detector_name || item.name || item.detector_id }}</td>
              <td>{{ item.detector_family || '-' }}</td>
              <td>{{ item.status || '-' }}</td>
              <td>{{ item.caveat || item.method || '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </SectionCard>

    <SectionCard title="内部运行摘要" subtitle="runtime-profile 仅供内部 diagnostics">
      <dl class="definition-grid compact">
        <dt>月报耗时</dt><dd>{{ runtimeProfile?.monthly_probability_total_seconds ?? '-' }}</dd>
        <dt>规则巡检耗时</dt><dd>{{ runtimeProfile?.detector_total_seconds ?? '-' }}</dd>
        <dt>端到端耗时</dt><dd>{{ runtimeProfile?.end_to_end_seconds ?? '-' }}</dd>
        <dt>配置状态</dt><dd>{{ configStatus?.config_edit_semantics || configStatus?.effective_config_version || '接口未就绪' }}</dd>
      </dl>
    </SectionCard>
  </div>
</template>
