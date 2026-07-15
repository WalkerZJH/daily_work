import { computed, inject, provide, readonly, ref } from 'vue'
import {
  loadManufacturerOptions,
  normalizeWorkbenchQuery
} from '../modules/monthly-demo/pageDataAdapter'

const manufacturerScopeKey = Symbol('manufacturer-scope')

export function provideManufacturerScope(query = {}) {
  const normalizedQuery = normalizeWorkbenchQuery(query)
  const manufacturerCode = ref(normalizedQuery.manufacturerCode)
  const manufacturerOptions = ref([])
  const isLoading = ref(false)
  const isReady = ref(false)
  let initializePromise = null

  const selectedManufacturer = computed(() => {
    const selected = manufacturerOptions.value.find((item) => item.code === manufacturerCode.value)
    return selected || {
      code: manufacturerCode.value,
      name: manufacturerCode.value ? '当前生产企业' : '未选择生产企业'
    }
  })

  function selectManufacturer(nextCode) {
    const code = String(nextCode || '').trim()
    if (!code || code === manufacturerCode.value) return
    manufacturerCode.value = code
    replaceManufacturerInUrl(code)
  }

  async function initialize() {
    if (initializePromise) return initializePromise
    isLoading.value = true
    initializePromise = loadManufacturerOptions(normalizedQuery)
      .then((directory) => {
        if (directory.manufacturerOptions?.length) {
          const includesCurrent = directory.manufacturerOptions.some((item) => item.code === manufacturerCode.value)
          manufacturerOptions.value = manufacturerCode.value && !includesCurrent
            ? [{ code: manufacturerCode.value, name: '当前生产企业' }, ...directory.manufacturerOptions]
            : directory.manufacturerOptions
        }
        if (!manufacturerCode.value) {
          const codes = manufacturerOptions.value.map((item) => item.code).filter(Boolean)
          const defaultCode = codes.includes(directory.defaultManufacturerCode)
            ? directory.defaultManufacturerCode
            : codes[0]
          if (defaultCode) {
            manufacturerCode.value = defaultCode
            replaceManufacturerInUrl(defaultCode)
          }
        }
        isReady.value = true
        return manufacturerCode.value
      })
      .finally(() => {
        isLoading.value = false
      })
    return initializePromise
  }

  const scope = {
    manufacturerCode: readonly(manufacturerCode),
    manufacturerOptions: readonly(manufacturerOptions),
    selectedManufacturer,
    isLoading: readonly(isLoading),
    isReady: readonly(isReady),
    initialize,
    selectManufacturer
  }
  provide(manufacturerScopeKey, scope)
  void initialize()
  return scope
}

export function useManufacturerScope() {
  const scope = inject(manufacturerScopeKey)
  if (!scope) throw new Error('Manufacturer scope must be provided by App.vue')
  return scope
}

function replaceManufacturerInUrl(manufacturerCode) {
  const params = new URLSearchParams(window.location.search)
  params.set('manufacturer_code', manufacturerCode)
  const query = params.toString()
  window.history.replaceState({}, '', `${window.location.pathname}${query ? `?${query}` : ''}`)
}
