const DEFAULT_TIMEOUT_MS = 30000
const DATABASE_REQUEST_TIMEOUT_MS = 120000

export class BackendApi {
  constructor(baseUrl) {
    this.baseUrl = normalizeBaseUrl(baseUrl)
  }

  updateBaseUrl(baseUrl) {
    this.baseUrl = normalizeBaseUrl(baseUrl)
  }

  async health() {
    return getJson(this.baseUrl, '/health')
  }

  async config() {
    return getJson(this.baseUrl, '/api/v0/config')
  }

  async dataQuality(datasetName) {
    return postJson(this.baseUrl, '/api/v0/debug/data-quality', { dataset_name: datasetName })
  }

  async preprocessRun({ datasetName, asOfDate, enabledPreprocessors = null }) {
    return postJson(this.baseUrl, '/api/v0/debug/preprocess/run', {
      dataset_name: datasetName,
      as_of_date: asOfDate,
      enabled_preprocessors: enabledPreprocessors
    })
  }

  async detectorSpecs() {
    return getJson(this.baseUrl, '/api/v0/debug/detectors')
  }

  async detectorCatalog() {
    return getJson(this.baseUrl, '/api/v0/detectors/catalog')
  }

  async detectorConfigs() {
    return getJson(this.baseUrl, '/api/v0/detectors/config')
  }

  async detectorConfig(detectorId) {
    return getJson(this.baseUrl, `/api/v0/detectors/${detectorId}/config`)
  }

  async runDetectors(payload) {
    return postJson(this.baseUrl, '/api/v0/detectors/run', payload, undefined, {
      timeoutMs: payload?.source_type === 'database' ? DATABASE_REQUEST_TIMEOUT_MS : DEFAULT_TIMEOUT_MS
    })
  }

  async runDetector(detectorId, payload) {
    return postJson(this.baseUrl, `/api/v0/detectors/${detectorId}/run`, payload, undefined, {
      timeoutMs: payload?.source_type === 'database' ? DATABASE_REQUEST_TIMEOUT_MS : DEFAULT_TIMEOUT_MS
    })
  }

  async runDetectorsByCategory(payload) {
    return postJson(this.baseUrl, '/api/v0/detectors/run-by-category', payload, undefined, {
      timeoutMs: payload?.source_type === 'database' ? DATABASE_REQUEST_TIMEOUT_MS : DEFAULT_TIMEOUT_MS
    })
  }

  async optionEnterprises() {
    return getJson(this.baseUrl, '/api/v0/options/enterprises')
  }

  async optionProvinces() {
    return getJson(this.baseUrl, '/api/v0/options/provinces')
  }

  async optionProductLines(query = {}) {
    return getJson(this.baseUrl, '/api/v0/options/product-lines', query)
  }

  async optionDetectorCategories() {
    return getJson(this.baseUrl, '/api/v0/options/detector-categories')
  }

  async optionDetectors(category) {
    return getJson(this.baseUrl, '/api/v0/options/detectors', { category })
  }

  async featureSnapshot({ datasetName, asOfDate, orgCode, analysisGrain, targetCode }) {
    return getJson(
      this.baseUrl,
      `/api/v0/debug/features/${orgCode}/${analysisGrain}/${targetCode}`,
      {
        dataset_name: datasetName,
        as_of_date: asOfDate
      }
    )
  }

  async dryRun({ datasetName, asOfDate }) {
    return postJson(this.baseUrl, '/api/v0/inspection/dry-run', {
      dataset_name: datasetName,
      as_of_date: asOfDate
    })
  }

  async inspectUnit({ datasetName, asOfDate, orgCode, productLineCode }) {
    return getJson(this.baseUrl, `/api/v0/debug/unit/${orgCode}/${productLineCode}`, {
      dataset_name: datasetName,
      as_of_date: asOfDate
    })
  }

  async unitDebug({ datasetName, asOfDate, orgCode, productLineCode }) {
    return this.inspectUnit({ datasetName, asOfDate, orgCode, productLineCode })
  }

  async backtest({ datasetName, startDate, endDate, stepDays }) {
    return postJson(this.baseUrl, '/api/v0/backtest/walk-forward', {
      dataset_name: datasetName,
      start_date: startDate,
      end_date: endDate,
      step_days: stepDays
    })
  }

  async configDryRun({ datasetName, asOfDate, configPatch }) {
    return postJson(this.baseUrl, '/api/v0/config/dry-run', {
      dataset_name: datasetName,
      as_of_date: asOfDate,
      config_patch: configPatch
    })
  }

  async runDatabaseSmokeTest(payload) {
    return postJson(this.baseUrl, '/api/v0/smoke-test/database', payload, undefined, {
      timeoutMs: DATABASE_REQUEST_TIMEOUT_MS
    })
  }

  async checkDatabaseFreshness(payload) {
    return postJson(this.baseUrl, '/api/v0/smoke-test/freshness', payload, undefined, {
      timeoutMs: 60000
    })
  }

  async predictBackbone(payload) {
    return postJson(this.baseUrl, '/api/v0/backbone/predict', payload, undefined, {
      timeoutMs: payload?.source_type === 'database' ? DATABASE_REQUEST_TIMEOUT_MS : DEFAULT_TIMEOUT_MS
    })
  }

  async frontendWorkbench() {
    return getJson(this.baseUrl, '/api/v1/workbench')
  }

  async frontendRiskEntities() {
    return getJson(this.baseUrl, '/api/v1/risk-entities')
  }

  async frontendRiskEntityDetail(entityId) {
    return getJson(this.baseUrl, `/api/v1/risk-entities/${entityId}`)
  }

  async frontendOneshotTerminals() {
    return getJson(this.baseUrl, '/api/v1/oneshot-terminals')
  }

  async frontendMonthlyReports() {
    return getJson(this.baseUrl, '/api/v1/monthly-reports')
  }

  async frontendProofCases() {
    return getJson(this.baseUrl, '/api/v1/proof-cases')
  }
}

export async function requestJson(baseUrl, path, options = {}) {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), options.timeoutMs || DEFAULT_TIMEOUT_MS)
  const url = buildUrl(baseUrl, path, options.query)
  try {
    const response = await fetch(url, {
      method: options.method || 'GET',
      headers: options.body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: controller.signal
    })
    const text = await response.text()
    const payload = text ? JSON.parse(text) : null
    if (!response.ok) {
      throw new Error(payload?.detail || response.statusText || `HTTP ${response.status}`)
    }
    return payload
  } catch (error) {
    if (error?.name === 'AbortError') {
      throw new Error(`请求超时：${url} 超过 ${(options.timeoutMs || DEFAULT_TIMEOUT_MS) / 1000} 秒未返回。database 模式会读取真实库，请降低 row_limit 或缩短日期窗口后重试。`)
    }
    throw error
  } finally {
    window.clearTimeout(timeout)
  }
}

export function getJson(baseUrl, path, query) {
  return requestJson(baseUrl, path, { method: 'GET', query })
}

export function postJson(baseUrl, path, body, query, options = {}) {
  return requestJson(baseUrl, path, { method: 'POST', body, query, ...options })
}

export function normalizeBaseUrl(baseUrl) {
  return (baseUrl || 'http://127.0.0.1:8000').replace(/\/+$/, '')
}

function buildUrl(baseUrl, path, query) {
  const url = new URL(`${normalizeBaseUrl(baseUrl)}${path}`)
  Object.entries(query || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      url.searchParams.set(key, value)
    }
  })
  return url.toString()
}
