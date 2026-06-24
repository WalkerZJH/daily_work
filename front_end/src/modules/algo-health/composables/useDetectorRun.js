import { computed, reactive, ref } from 'vue'

import { BackendApi } from '../../../services/backendApi'

function todayText() {
  return new Date().toISOString().slice(0, 10)
}

export function useDetectorRun(sharedApiBase) {
  const loading = ref(false)
  const catalogLoading = ref(false)
  const errorMessage = ref('')
  const catalog = ref([])
  const result = ref(null)
  const selectedRow = ref(null)
  const form = reactive({
    source_type: 'sample',
    dataset_name: 'sample',
    as_of_date: todayText(),
    days: 14,
    row_limit: 5000,
    category: '',
    enabled_detector: '',
    enterprise_code: '',
    province_code: ''
  })

  const api = computed(() => new BackendApi(sharedApiBase.value))
  const categories = computed(() => Array.from(new Set(catalog.value.map((item) => item.category))).sort())
  const visibleCatalog = computed(() => {
    if (!form.category) return catalog.value
    return catalog.value.filter((item) => item.category === form.category)
  })

  async function loadCatalog() {
    catalogLoading.value = true
    errorMessage.value = ''
    try {
      catalog.value = await api.value.detectorCatalog()
    } catch (error) {
      errorMessage.value = error.message || '获取 detector catalog 失败'
    } finally {
      catalogLoading.value = false
    }
  }

  function payload(runAll = false) {
    return {
      source_type: form.source_type,
      dataset_name: form.source_type === 'sample' ? form.dataset_name || 'sample' : 'database:BS_Agent_DingDan',
      as_of_date: form.as_of_date,
      days: Number(form.days) || 14,
      row_limit: Number(form.row_limit) || 5000,
      category: form.category || null,
      enabled_detectors: runAll || !form.enabled_detector ? null : [form.enabled_detector],
      enterprise_code: form.enterprise_code || null,
      province_code: form.province_code || null
    }
  }

  async function runDetectors(runAll = false) {
    loading.value = true
    errorMessage.value = ''
    selectedRow.value = null
    localStorage.setItem('backendApiBase', sharedApiBase.value)
    try {
      result.value = await api.value.runDetectors(payload(runAll))
    } catch (error) {
      errorMessage.value = error.message || '运行 detector 推理失败'
    } finally {
      loading.value = false
    }
  }

  return reactive({
    form,
    loading,
    catalogLoading,
    errorMessage,
    catalog,
    categories,
    visibleCatalog,
    result,
    selectedRow,
    loadCatalog,
    runDetectors
  })
}
