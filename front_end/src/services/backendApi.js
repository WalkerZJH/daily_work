const DEFAULT_TIMEOUT_MS = 30000
const DATABASE_REQUEST_TIMEOUT_MS = 120000
const DISPLAY_LOOKUP_STATUS_TIMEOUT_MS = 3000

export class BackendApi {
  constructor(baseUrl, userId) {
    this.baseUrl = normalizeBaseUrl(baseUrl)
    this.userId = userId || resolveDefaultUserId()
  }

  updateBaseUrl(baseUrl) {
    this.baseUrl = normalizeBaseUrl(baseUrl)
  }

  userOptions(options = {}) {
    return {
      ...options,
      headers: {
        ...(options.headers || {}),
        'X-User-Id': this.userId
      }
    }
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

  async frontendWorkbench(params = {}) {
    return getJson(this.baseUrl, '/api/v1/workbench', params, this.userOptions())
  }

  async getWorkbench(params = {}) {
    return this.frontendWorkbench(params)
  }

  async getReportContext(params = {}) {
    return getJson(this.baseUrl, '/api/v1/report-context', params, this.userOptions())
  }

  async frontendRiskEntities(params = {}) {
    return getJson(this.baseUrl, '/api/v1/risk-entities', params, this.userOptions())
  }

  async getRiskEntities(params = {}) {
    return this.frontendRiskEntities(params)
  }

  async frontendRiskEntityDetail(entityId, params = {}) {
    return getJson(this.baseUrl, `/api/v1/risk-entities/${entityId}`, params, this.userOptions())
  }

  async getRiskEntityDetail(entityId, params = {}) {
    return this.frontendRiskEntityDetail(entityId, params)
  }

  async frontendOneshotTerminals(params = {}) {
    return getJson(this.baseUrl, '/api/v1/oneshot-terminals', params, this.userOptions())
  }

  async frontendMonthlyReports(params = {}) {
    return getJson(this.baseUrl, '/api/v1/monthly-reports', params, this.userOptions())
  }

  async getMonthlyReports(params = {}) {
    return this.frontendMonthlyReports(params)
  }

  async frontendProofCases(params = {}) {
    return getJson(this.baseUrl, '/api/v1/proof-cases', params, this.userOptions())
  }

  async getProofCases(params = {}) {
    return this.frontendProofCases(params)
  }

  async displayLookupStatus(params = {}) {
    return getJson(this.baseUrl, '/api/v1/display-lookup/status', params, this.userOptions({
      timeoutMs: DISPLAY_LOOKUP_STATUS_TIMEOUT_MS
    }))
  }

  async getDisplayLookupStatus(params = {}) {
    return this.displayLookupStatus(params)
  }

  async getDetectorCatalog(params = {}) {
    return getJson(this.baseUrl, '/api/v1/detectors/catalog', params, this.userOptions())
  }

  async getDetectorRuns(params = {}) {
    return getJson(this.baseUrl, '/api/v1/detectors/runs', params, this.userOptions())
  }

  async getDetectorClues(params = {}) {
    return getJson(this.baseUrl, '/api/v1/detectors/clues', params)
  }

  async getMyManufacturers(params = {}) {
    return getJson(this.baseUrl, '/api/v1/my/manufacturers', params, this.userOptions())
  }

  async getDailyDetectorDates(params = {}) {
    return getJson(this.baseUrl, '/api/v1/daily-detector/dates', params, this.userOptions())
  }

  async getDailyDetectorStatus(params = {}) {
    return getJson(this.baseUrl, '/api/v1/daily-detector/status', params, this.userOptions())
  }

  async getDailyDetectorClues(params = {}) {
    return getJson(this.baseUrl, '/api/v1/daily-detector/clues', params, this.userOptions())
  }

  async getRiskEntityDetectorEvidence(riskEntityId, params = {}) {
    return getJson(this.baseUrl, `/api/v1/risk-entities/${riskEntityId}/detector-evidence`, params, this.userOptions())
  }

  async getDetectorConfigStatus(params = {}) {
    return getJson(this.baseUrl, '/api/v1/detectors/config-status', params, this.userOptions())
  }

  async getRiskEntityProbabilityTrend(riskEntityId, params = {}) {
    return getJson(this.baseUrl, `/api/v1/risk-entities/${riskEntityId}/probability-trend`, params, this.userOptions())
  }

  async getRuntimeProfile(params = {}) {
    return getJson(this.baseUrl, '/api/v1/runtime-profile', params, this.userOptions())
  }
}

export async function requestJson(baseUrl, path, options = {}) {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), options.timeoutMs || DEFAULT_TIMEOUT_MS)
  const url = buildUrl(baseUrl, path, options.query)
  try {
    const response = await fetch(url, {
      method: options.method || 'GET',
      headers: {
        ...(options.body === undefined ? {} : { 'Content-Type': 'application/json' }),
        ...(options.headers || {})
      },
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

export function getJson(baseUrl, path, query, options = {}) {
  return requestJson(baseUrl, path, { method: 'GET', query, ...options })
}

export function postJson(baseUrl, path, body, query, options = {}) {
  return requestJson(baseUrl, path, { method: 'POST', body, query, ...options })
}

export function normalizeBaseUrl(baseUrl) {
  return (baseUrl || 'http://127.0.0.1:18080').replace(/\/+$/, '')
}

function resolveDefaultUserId() {
  if (typeof window === 'undefined') return 'admin'
  const params = new URLSearchParams(window.location.search)
  try {
    return window.__USER_ID__ || params.get('user_id') || params.get('userId') || window.localStorage.getItem('userId') || 'admin'
  } catch (error) {
    return window.__USER_ID__ || params.get('user_id') || params.get('userId') || 'admin'
  }
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
