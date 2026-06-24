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
    as_of_date: todayText(),
    days: 14,
    row_limit: 5000,
    enterprise_code: '',
    province: '',
    province_code: '',
    include_debug_features: true
  })

  const api = computed(() => new BackendApi(apiBase.value))

  function payload() {
    return {
      as_of_date: form.as_of_date,
      days: Number(form.days) || 14,
      row_limit: Number(form.row_limit) || 5000,
      enterprise_code: form.enterprise_code || null,
      province: form.province || null,
      province_code: form.province_code || null,
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
      freshness.value = await api.value.checkDatabaseFreshness(payload())
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
