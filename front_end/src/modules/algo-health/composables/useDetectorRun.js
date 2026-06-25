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
  const enterpriseOptions = ref([])
  const provinceOptions = ref([])
  const productLineOptions = ref([])
  const categoryOptions = ref([])
  const detectorOptions = ref([])
  const selectedConfig = ref(null)
  const result = ref(null)
  const selectedRow = ref(null)
  const form = reactive({
    source_type: 'database',
    dataset_name: 'sample',
    as_of_date: todayText(),
    lookback_days: 30,
    baseline_days: 180,
    row_limit: 500,
    category: '',
    enabled_detector: '',
    enterprise_code: '',
    province_code: '',
    product_line_code: ''
  })

  const api = computed(() => new BackendApi(sharedApiBase.value))
  const categories = computed(() => categoryOptions.value.map((item) => item.category_id))
  const visibleCatalog = computed(() => detectorOptions.value)

  async function loadCatalog() {
    catalogLoading.value = true
    errorMessage.value = ''
    try {
      const [catalogPayload, enterprises, provinces, categoriesPayload] = await Promise.all([
        api.value.detectorCatalog(),
        api.value.optionEnterprises(),
        api.value.optionProvinces(),
        api.value.optionDetectorCategories()
      ])
      catalog.value = catalogPayload
      enterpriseOptions.value = enterprises
      provinceOptions.value = provinces
      categoryOptions.value = categoriesPayload
      if (!form.category && categoriesPayload.length) {
        form.category = categoriesPayload[0].category_id
      }
      await loadDetectorsForCategory()
      await loadProductLines()
    } catch (error) {
      errorMessage.value = error.message || '获取 detector 与下拉选项失败'
    } finally {
      catalogLoading.value = false
    }
  }

  async function loadDetectorsForCategory() {
    detectorOptions.value = await api.value.optionDetectors(form.category || undefined)
    if (!detectorOptions.value.some((item) => item.detector_id === form.enabled_detector)) {
      form.enabled_detector = detectorOptions.value[0]?.detector_id || ''
    }
    await loadSelectedConfig()
  }

  async function loadSelectedConfig() {
    selectedConfig.value = form.enabled_detector ? await api.value.detectorConfig(form.enabled_detector) : null
  }

  async function loadProductLines() {
    productLineOptions.value = await api.value.optionProductLines({
      enterprise_code: form.enterprise_code || undefined,
      province_code: form.province_code || undefined
    })
    if (!productLineOptions.value.some((item) => item.code === form.product_line_code)) {
      form.product_line_code = ''
    }
  }

  function payload(runAll = false) {
    return {
      source_type: form.source_type,
      dataset_name: form.source_type === 'sample' ? form.dataset_name || 'sample' : 'database:BS_Agent_DingDan',
      as_of_date: form.as_of_date,
      days: Number(form.lookback_days) || 30,
      lookback_days: Number(form.lookback_days) || 30,
      baseline_days: Number(form.baseline_days) || 180,
      row_limit: Number(form.row_limit) || 500,
      category: form.category || null,
      enabled_detectors: runAll || !form.enabled_detector ? null : [form.enabled_detector],
      enterprise_code: form.enterprise_code || null,
      province_code: form.province_code || null,
      product_line_code: form.product_line_code || null
    }
  }

  async function runDetectors(runAll = false, byCategory = false) {
    loading.value = true
    errorMessage.value = ''
    selectedRow.value = null
    localStorage.setItem('backendApiBase', sharedApiBase.value)
    try {
      if (!runAll && form.enabled_detector) {
        result.value = await api.value.runDetector(form.enabled_detector, payload(false))
      } else if (byCategory || form.category) {
        result.value = await api.value.runDetectorsByCategory(payload(true))
      } else {
        result.value = await api.value.runDetectors(payload(runAll))
      }
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
    enterpriseOptions,
    provinceOptions,
    productLineOptions,
    categoryOptions,
    detectorOptions,
    selectedConfig,
    categories,
    visibleCatalog,
    result,
    selectedRow,
    loadCatalog,
    loadDetectorsForCategory,
    loadProductLines,
    loadSelectedConfig,
    runDetectors
  })
}
