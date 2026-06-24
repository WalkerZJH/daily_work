import { computed, ref, watch } from 'vue'

import { BackendApi } from '../../../services/backendApi'

export const endpoints = [
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

export function useAlgoConfigApi() {
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
      const payload = await callApi(() => api.health(), { keepRawHidden: true })
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
    unitDebugResult.value = await callApi(() => api.inspectUnit({
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
      const [configPayload, qualityPayload, dryRunPayload, unitPayload] = await Promise.all([
        api.config(),
        api.dataQuality(datasetName.value),
        api.dryRun({ datasetName: datasetName.value, asOfDate: asOfDate.value }),
        api.inspectUnit({
          datasetName: datasetName.value,
          asOfDate: asOfDate.value,
          orgCode: parsedUnit.value.orgCode,
          productLineCode: parsedUnit.value.productLineCode
        })
      ])
      config.value = configPayload
      qualityReport.value = qualityPayload
      dryRunResult.value = dryRunPayload
      unitDebugResult.value = unitPayload
      lastPayload.value = {
        config: configPayload,
        quality_report: qualityPayload,
        dry_run_result: dryRunPayload,
        unit_debug_result: unitPayload
      }
    } catch (error) {
      errorMessage.value = error.message || String(error)
    } finally {
      loading.value = false
    }
  }

  return {
    apiBase,
    datasetName,
    asOfDate,
    unitKey,
    loading,
    backendStatus,
    backendStatusText,
    errorMessage,
    config,
    qualityReport,
    dryRunResult,
    unitDebugResult,
    configDryRunResult,
    lastPayload,
    configPatch,
    checkHealth,
    loadConfig,
    runQuality,
    runDryRun,
    runUnitDebug,
    runConfigDryRun,
    refreshAll
  }
}
