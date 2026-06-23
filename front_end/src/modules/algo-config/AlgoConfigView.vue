<script setup>
import { computed, onMounted, ref, watch } from 'vue'

import { BackendApi } from '../../services/backendApi'
import ApiControlPanel from './components/ApiControlPanel.vue'
import ArchitectureDiagram from './components/ArchitectureDiagram.vue'
import ConfigPanel from './components/ConfigPanel.vue'
import DebugPanel from './components/DebugPanel.vue'
import RuntimeWarnings from './components/RuntimeWarnings.vue'

const apiBase = ref('http://127.0.0.1:8000')
const datasetName = ref('sample')
const asOfDate = ref('2025-12-31')
const unitKey = ref('ORG_A|PL_A')
const loading = ref(false)
const backendStatus = ref('unknown')
const backendStatusText = ref('后端未检测')
const errorMessage = ref('')
const config = ref(null)
const qualityReport = ref(null)
const dryRunResult = ref(null)
const unitDebugResult = ref(null)
const configDryRunResult = ref(null)
const lastPayload = ref(null)
const configPatch = ref(JSON.stringify({
  fusion: {
    yellow_score: 25,
    orange_score: 45,
    red_score: 70
  }
}, null, 2))

const api = new BackendApi(apiBase.value)

const endpoints = [
  { method: 'GET', path: '/health', desc: '健康检查' },
  { method: 'GET', path: '/api/v0/config', desc: '配置查看' },
  { method: 'POST', path: '/api/v0/debug/data-quality', desc: '数据质量检查' },
  { method: 'GET', path: '/api/v0/debug/detectors', desc: 'Detector 依赖查看' },
  { method: 'POST', path: '/api/v0/debug/preprocess/run', desc: '预处理链路调试' },
  { method: 'GET', path: '/api/v0/debug/features/{org}/{grain}/{target}', desc: 'FeatureSnapshot 查看' },
  { method: 'GET', path: '/api/v0/debug/unit/{org_code}/{product_line_code}', desc: '兼容单分析单元调试' },
  { method: 'GET', path: '/api/v0/debug/unit/{org}/{grain}/{target}', desc: '通用单元调试' },
  { method: 'POST', path: '/api/v0/inspection/dry-run', desc: '全量巡检 dry-run' },
  { method: 'POST', path: '/api/v0/config/dry-run', desc: '配置影响 dry-run' },
  { method: 'POST', path: '/api/v0/backtest/walk-forward', desc: '回测 skeleton' }
]

const parsedUnit = computed(() => {
  const [orgCode, productLineCode] = unitKey.value.split('|')
  return { orgCode, productLineCode }
})

watch(apiBase, (value) => {
  api.updateBaseUrl(value)
})

async function callApi(task, options = {}) {
  loading.value = true
  errorMessage.value = ''
  try {
    const payload = await task()
    if (!options.keepRawHidden) {
      lastPayload.value = payload
    }
    return payload
  } catch (error) {
    errorMessage.value = error.message || String(error)
    throw error
  } finally {
    loading.value = false
  }
}

async function checkHealth() {
  try {
    const payload = await callApi(() => api.health())
    backendStatus.value = 'ok'
    backendStatusText.value = `${payload.service || 'backend'} 已连接`
    return true
  } catch {
    backendStatus.value = 'error'
    backendStatusText.value = '后端未连接'
    return false
  }
}

async function loadConfig() {
  config.value = await callApi(() => api.config())
}

async function runQuality() {
  qualityReport.value = await callApi(() => api.dataQuality(datasetName.value))
}

async function runDryRun() {
  dryRunResult.value = await callApi(() => api.dryRun({
    datasetName: datasetName.value,
    asOfDate: asOfDate.value
  }))
}

async function runUnitDebug() {
  unitDebugResult.value = await callApi(() => api.unitDebug({
    datasetName: datasetName.value,
    asOfDate: asOfDate.value,
    orgCode: parsedUnit.value.orgCode,
    productLineCode: parsedUnit.value.productLineCode
  }))
}

async function runConfigDryRun() {
  let patch
  try {
    patch = JSON.parse(configPatch.value || '{}')
  } catch {
    errorMessage.value = '配置 patch 不是合法 JSON'
    return
  }
  configDryRunResult.value = await callApi(() => api.configDryRun({
    datasetName: datasetName.value,
    asOfDate: asOfDate.value,
    configPatch: patch
  }))
}

async function refreshAll() {
  const ok = await checkHealth()
  if (!ok) return
  loading.value = true
  errorMessage.value = ''
  try {
    config.value = await api.config()
    qualityReport.value = await api.dataQuality(datasetName.value)
    dryRunResult.value = await api.dryRun({
      datasetName: datasetName.value,
      asOfDate: asOfDate.value
    })
    unitDebugResult.value = await api.unitDebug({
      datasetName: datasetName.value,
      asOfDate: asOfDate.value,
      orgCode: parsedUnit.value.orgCode,
      productLineCode: parsedUnit.value.productLineCode
    })
    lastPayload.value = {
      config: config.value,
      quality_report: qualityReport.value,
      dry_run_result: dryRunResult.value,
      unit_debug_result: unitDebugResult.value
    }
  } catch (error) {
    errorMessage.value = error.message || String(error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  refreshAll()
})
</script>

<template>
  <div class="algo-config-view">
    <div class="page-header">
      <h1>算法接口诊断</h1>
      <div class="subtitle">
        后端健康检查 · dry-run · 单元调试 · FeatureSnapshot 验证 · 仅供开发联调使用
      </div>
    </div>

    <ApiControlPanel
      v-model:api-base="apiBase"
      v-model:dataset-name="datasetName"
      v-model:as-of-date="asOfDate"
      v-model:unit-key="unitKey"
      :loading="loading"
      :backend-status="backendStatus"
      :backend-status-text="backendStatusText"
      @refresh-all="refreshAll"
      @run-quality="runQuality"
      @run-dry-run="runDryRun"
      @run-unit-debug="runUnitDebug"
      @run-config-dry-run="runConfigDryRun"
    />

    <RuntimeWarnings />

    <div v-if="errorMessage" class="error-banner">
      {{ errorMessage }}
    </div>

    <ArchitectureDiagram />

    <div class="grid-2 content-grid">
      <DebugPanel
        :quality-report="qualityReport"
        :dry-run-result="dryRunResult"
        :unit-debug-result="unitDebugResult"
        :last-payload="lastPayload"
      />

      <aside class="side-stack">
        <ConfigPanel
          v-model:config-patch="configPatch"
          :config="config"
          :config-dry-run-result="configDryRunResult"
          @run-config-dry-run="runConfigDryRun"
        />

        <section class="panel">
          <div class="panel-title">
            <h2>已暴露接口</h2>
            <span class="muted">用于页面观察和测试</span>
          </div>
          <table class="table">
            <tbody>
              <tr v-for="endpoint in endpoints" :key="endpoint.path">
                <th>{{ endpoint.method }}</th>
                <td>
                  <code>{{ endpoint.path }}</code>
                  <div class="muted">{{ endpoint.desc }}</div>
                </td>
              </tr>
            </tbody>
          </table>
        </section>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.algo-config-view {
  max-width: 1440px;
}

.content-grid {
  margin-top: 16px;
}

.side-stack {
  display: grid;
  gap: 16px;
}

.error-banner {
  border: 1px solid #fecaca;
  border-radius: var(--radius-sm);
  background: var(--red-bg);
  color: #b91c1c;
  padding: 10px 12px;
  margin-bottom: 16px;
  font-size: 13px;
  font-weight: 800;
}

code {
  color: var(--blue-deep);
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
  font-size: 12px;
}
</style>
