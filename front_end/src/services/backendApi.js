const DEFAULT_TIMEOUT_MS = 12000

export class BackendApi {
  constructor(baseUrl) {
    this.baseUrl = normalizeBaseUrl(baseUrl)
  }

  updateBaseUrl(baseUrl) {
    this.baseUrl = normalizeBaseUrl(baseUrl)
  }

  async health() {
    return this.request('/health')
  }

  async config() {
    return this.request('/api/v0/config')
  }

  async dataQuality(datasetName) {
    return this.request('/api/v0/debug/data-quality', {
      method: 'POST',
      body: { dataset_name: datasetName }
    })
  }

  async dryRun({ datasetName, asOfDate }) {
    return this.request('/api/v0/inspection/dry-run', {
      method: 'POST',
      body: {
        dataset_name: datasetName,
        as_of_date: asOfDate
      }
    })
  }

  async unitDebug({ datasetName, asOfDate, orgCode, productLineCode }) {
    const params = new URLSearchParams({
      dataset_name: datasetName,
      as_of_date: asOfDate
    })
    return this.request(`/api/v0/debug/unit/${orgCode}/${productLineCode}?${params.toString()}`)
  }

  async configDryRun({ datasetName, asOfDate, configPatch }) {
    return this.request('/api/v0/config/dry-run', {
      method: 'POST',
      body: {
        dataset_name: datasetName,
        as_of_date: asOfDate,
        config_patch: configPatch
      }
    })
  }

  async request(path, options = {}) {
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS)
    try {
      const response = await fetch(`${this.baseUrl}${path}`, {
        method: options.method || 'GET',
        headers: { 'Content-Type': 'application/json' },
        body: options.body ? JSON.stringify(options.body) : undefined,
        signal: controller.signal
      })
      const text = await response.text()
      const payload = text ? JSON.parse(text) : null
      if (!response.ok) {
        throw new Error(payload?.detail || response.statusText || `HTTP ${response.status}`)
      }
      return payload
    } finally {
      window.clearTimeout(timeout)
    }
  }
}

export function normalizeBaseUrl(baseUrl) {
  return (baseUrl || 'http://127.0.0.1:8000').replace(/\/+$/, '')
}
