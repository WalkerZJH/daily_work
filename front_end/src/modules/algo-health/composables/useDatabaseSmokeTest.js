import { computed, reactive, ref } from 'vue'

import { BackendApi } from '../../../services/backendApi'

function todayText() {
  return new Date().toISOString().slice(0, 10)
}

export function useDatabaseSmokeTest() {
  const apiBase = ref(localStorage.getItem('backendApiBase') || 'http://127.0.0.1:8000')
  const loading = ref(false)
  const errorMessage = ref('')
  const result = ref(null)
  const freshness = ref(null)
  const selectedRow = ref(null)
  const form = reactive({
    source_type: 'database',
    as_of_date: todayText(),
    lookback_days: 30,
    baseline_days: 180,
    history_start_date: '',
    row_limit: 500,
    enterprise_code: '',
    enterprise_name: '',
    province: '',
    province_code: '',
    province_name: '',
    product_line_code: '',
    include_debug_features: false
  })

  const api = computed(() => new BackendApi(apiBase.value))

  function payload() {
    return {
      source_type: form.source_type,
      as_of_date: form.as_of_date,
      lookback_days: Number(form.lookback_days) || 30,
      baseline_days: Number(form.baseline_days) || 180,
      history_start_date: form.history_start_date || null,
      row_limit: Number(form.row_limit) || 500,
      enterprise_code: form.enterprise_code || null,
      enterprise_name: form.enterprise_name || null,
      province: form.province || null,
      province_code: form.province_code || null,
      province_name: form.province_name || null,
      product_line_code: form.product_line_code || null,
      include_debug_features: Boolean(form.include_debug_features)
    }
  }

  async function runSmokeTest() {
    loading.value = true
    errorMessage.value = ''
    selectedRow.value = null
    localStorage.setItem('backendApiBase', apiBase.value)
    try {
      result.value = await api.value.runDatabaseSmokeTest(payload())
    } catch (error) {
      errorMessage.value = error.message || '请求后端失败'
    } finally {
      loading.value = false
    }
  }

  async function checkFreshness() {
    loading.value = true
    errorMessage.value = ''
    localStorage.setItem('backendApiBase', apiBase.value)
    try {
      freshness.value = await api.value.checkDatabaseFreshness({
        as_of_date: form.as_of_date,
        days: Number(form.lookback_days) || 30,
        row_limit: Number(form.row_limit) || 500,
        enterprise_code: form.enterprise_code || null,
        province: form.province || null,
        province_code: form.province_code || null
      })
    } catch (error) {
      errorMessage.value = error.message || '请求后端失败'
    } finally {
      loading.value = false
    }
  }

  return {
    apiBase,
    form,
    loading,
    errorMessage,
    result,
    freshness,
    selectedRow,
    runSmokeTest,
    checkFreshness
  }
}
