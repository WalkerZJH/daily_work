import { BackendApi } from '../../services/backendApi'

export const horizonOptions = [
  { id: 'H3', label: '3月' },
  { id: 'H6', label: '6月' },
  { id: 'H12', label: '12月' }
]

export const topNOptions = [10, 20, 50, 100]

export const RULE_CATEGORY_DEFINITIONS = [
  { id: 'price', label: '价格异常', families: ['price'] },
  { id: 'fulfillment', label: '配送异常', families: ['fulfillment'], unavailable: true },
  { id: 'terminal', label: '终端变动', families: ['interval', 'assortment'] },
  { id: 'sales', label: '销量波动', families: ['quantity', 'frequency'] }
]

export function ruleCategoryForDetectorFamily(family) {
  return RULE_CATEGORY_DEFINITIONS.find((item) => item.families.includes(family))?.id || ''
}

export const sortOptions = [
  { id: 'risk_probability', label: '丢失概率' },
  { id: 'involved_amount', label: '涉及金额' },
  { id: 'loss_value', label: '损失价值' },
  { id: 'detector_score', label: '规则巡检分' }
]

export const defaultWorkbenchQuery = {
  manufacturerCode: '',
  observationDate: defaultRunDate(),
  reportMonth: '',
  runDate: defaultRunDate(),
  probabilityReportMonth: '',
  detectorRunDate: '',
  detectorFamily: '',
  detectorId: '',
  horizon: 'H6',
  topN: 20,
  sortBy: 'risk_probability'
}

const FORMAL_EMPTY_STATUS = {
  ready: false,
  sourceLabel: '接口未就绪',
  runDate: '-',
  clueCount: 0,
  attachedHighRiskCount: 0,
  scannedEntityCount: 0,
  statusText: '接口未就绪',
  caveat: ''
}

const DISPLAY_LOOKUP_EMPTY_STATUS = {
  ready: false,
  label: '展示名映射未接通',
  message: ''
}

export function normalizeWorkbenchQuery(query = {}) {
  const observationDate = firstText(query.observationDate, query.observation_date, query.runDate, query.run_date, defaultWorkbenchQuery.observationDate)
  const reportMonth = firstText(query.reportMonth, query.report_month, query.probabilityReportMonth, query.probability_report_month, '')
  const probabilityReportMonth = firstText(query.probabilityReportMonth, query.probability_report_month, reportMonth)
  const detectorRunDate = firstText(query.detectorRunDate, query.detector_run_date, observationDate)
  const horizon = horizonOptions.some((item) => item.id === query.horizon) ? query.horizon : defaultWorkbenchQuery.horizon
  const topN = topNOptions.includes(Number(query.topN ?? query.top_n)) ? Number(query.topN ?? query.top_n) : defaultWorkbenchQuery.topN
  const sortByCandidate = query.sortBy || query.sort_by
  const sortBy = sortOptions.some((item) => item.id === sortByCandidate) ? sortByCandidate : defaultWorkbenchQuery.sortBy
  const demoModeParam = query.demoMode ?? query.demo_mode

  return {
    backendBaseUrl: query.backendBaseUrl || query.backend_base_url || undefined,
    userId: query.userId || query.user_id || query.userID || undefined,
    demoMode: parseBoolean(demoModeParam),
    demoModeParam: demoModeParam === undefined || demoModeParam === null ? undefined : String(demoModeParam),
    manufacturerCode: firstText(query.manufacturerCode, query.manufacturer_code, ''),
    observationDate,
    reportMonth,
    runDate: observationDate,
    probabilityReportMonth,
    detectorRunDate,
    detectorFamily: firstText(query.detectorFamily, query.detector_family, ''),
    detectorId: firstText(query.detectorId, query.detector_id, ''),
    horizon,
    topN,
    sortBy
  }
}

export function buildPersistentParams(query = {}, extra = {}) {
  const normalized = normalizeWorkbenchQuery({ ...query, ...extra })
  const params = new URLSearchParams()
  setParam(params, 'backendBaseUrl', normalized.backendBaseUrl)
  setParam(params, 'user_id', normalized.userId)
  setParam(params, 'observation_date', normalized.observationDate)
  setParam(params, 'report_month', normalized.reportMonth || normalized.probabilityReportMonth)
  setParam(params, 'run_date', normalized.runDate || normalized.observationDate)
  setParam(params, 'probability_report_month', normalized.probabilityReportMonth || normalized.reportMonth)
  setParam(params, 'detector_run_date', normalized.detectorRunDate || normalized.observationDate)
  setParam(params, 'manufacturer_code', normalized.manufacturerCode)
  setParam(params, 'detector_family', normalized.detectorFamily)
  setParam(params, 'detector_id', normalized.detectorId)
  setParam(params, 'horizon', normalized.horizon)
  setParam(params, 'top_n', normalized.topN)
  setParam(params, 'sort_by', normalized.sortBy)
  if (normalized.demoMode || normalized.demoModeParam !== undefined) {
    setParam(params, 'demoMode', normalized.demoMode ? 'true' : normalized.demoModeParam || 'false')
  }
  Object.entries(extra || {}).forEach(([key, value]) => {
    if (!['backendBaseUrl', 'userId', 'demoMode'].includes(key)) setParam(params, key, value)
  })
  return params
}

export function createEmptyReportContext(query = {}) {
  const normalized = normalizeWorkbenchQuery(query)
  return {
    ready: false,
    observationDate: normalized.observationDate,
    probabilityReportMonth: normalized.probabilityReportMonth || normalized.reportMonth,
    detectorRunDate: normalized.detectorRunDate || normalized.observationDate,
    probabilityBatchAvailable: false,
    detectorRunAvailable: false,
    contextStatus: 'interface_unavailable',
    manualSelectionRequired: false,
    availableReportMonths: [],
    availableDetectorRunDates: [],
    effectiveHorizon: normalized.horizon,
    requestedReportMonth: normalized.reportMonth,
    requestedRunDate: normalized.runDate,
    requestedHorizon: normalized.horizon,
    effectiveReportMonth: null,
    effectiveRunDate: null,
    fallbackUsed: false,
    title: '接口未就绪',
    message: '当前数据接口未返回可用月报结果',
    displayTitle: '接口未就绪',
    displayLines: []
  }
}

export async function loadReportContext(query = {}) {
  const normalized = normalizeWorkbenchQuery(query)
  if (normalized.demoMode) return loadDemo('reportContext', normalized)
  const reportContext = await tryLoad(
    () => api(normalized).getReportContext(queryToReportContextParams(normalized)),
    (payload) => mapReportContextPayload(payload, normalized)
  )
  return reportContext || createEmptyReportContext(normalized)
}

export function applyReportContextToQuery(query = {}, reportContext = {}) {
  const normalized = normalizeWorkbenchQuery(query)
  if (!reportContext.ready && !reportContext.probabilityReportMonth) return normalized
  return normalizeWorkbenchQuery({
    ...normalized,
    observationDate: reportContext.observationDate || normalized.observationDate,
    runDate: reportContext.observationDate || reportContext.effectiveRunDate || normalized.runDate,
    reportMonth: reportContext.probabilityReportMonth || reportContext.effectiveReportMonth || normalized.reportMonth,
    probabilityReportMonth: reportContext.probabilityReportMonth || normalized.probabilityReportMonth,
    detectorRunDate: reportContext.detectorRunDate || normalized.detectorRunDate,
    horizon: reportContext.effectiveHorizon || normalized.horizon
  })
}

export function createEmptyWorkbenchOptions(query = {}) {
  const normalized = normalizeWorkbenchQuery(query)
  return {
    manufacturerOptions: currentManufacturerOption(normalized),
    defaultManufacturerCode: normalized.manufacturerCode,
    dailyDetectorDateOptions: [{ runDate: normalized.observationDate, label: normalized.observationDate }],
    detectorCatalog: [],
    reportMonthOptions: normalized.probabilityReportMonth ? [normalized.probabilityReportMonth] : [],
    horizonOptions,
    topNOptions,
    sortOptions,
    sourceLabel: '接口未就绪'
  }
}

export function createEmptyWorkbenchData(query = {}, reportContext = createEmptyReportContext(query)) {
  const normalized = normalizeWorkbenchQuery(query)
  const detectorSummary = {
    runDate: reportContext.detectorRunDate || normalized.detectorRunDate || normalized.observationDate,
    clueCount: 0,
    attachedHighRiskCount: 0,
    scannedEntityCount: 0,
    highestRuleScore: null,
    priorityRiskEntityCount: 0,
    ready: reportContext.detectorRunAvailable === true
  }
  return {
    ready: false,
    reportContext,
    displayLookupStatus: DISPLAY_LOOKUP_EMPTY_STATUS,
    query: normalized,
    scope: {
      manufacturerCode: normalized.manufacturerCode,
      manufacturerName: normalized.manufacturerCode || '未选择生产企业',
      reportMonth: normalized.probabilityReportMonth || normalized.reportMonth
    },
    overviewMetrics: buildTodayMetrics([], detectorSummary, normalized, reportContext),
    dailyDetectorStatus: { ...FORMAL_EMPTY_STATUS, runDate: detectorSummary.runDate },
    detectorSummary,
    workbenchDisplayRows: [],
    topRuleClues: [],
    emptyTitle: reportContext.displayTitle || '接口未就绪',
    emptyMessage: reportContext.message || '当前没有可展示的风险对象'
  }
}

export function createEmptyRuleCluesData(query = {}, reportContext = createEmptyReportContext(query)) {
  const normalized = normalizeWorkbenchQuery(query)
  return {
    ready: false,
    reportContext,
    query: normalized,
    dailyDetectorStatus: { ...FORMAL_EMPTY_STATUS, runDate: reportContext.detectorRunDate || normalized.detectorRunDate },
    dailyDetectorClues: [],
    total: 0,
    emptyTitle: reportContext.detectorRunAvailable === false ? '该观察日期暂无规则巡检结果' : reportContext.displayTitle || '接口未就绪',
    emptyMessage: reportContext.message || '当前没有可展示的规则线索'
  }
}

export function createEmptyClueDetailData({ clueId, riskEntityId, query, reportContext } = {}) {
  const normalized = normalizeWorkbenchQuery(query)
  return {
    ready: false,
    reportContext: reportContext || createEmptyReportContext(normalized),
    query: normalized,
    clueId,
    riskEntityId,
    dailyDetectorStatus: { ...FORMAL_EMPTY_STATUS, runDate: normalized.detectorRunDate },
    clue: {},
    entity: null,
    isMonthlyHighRiskEntity: Boolean(riskEntityId),
    detectorEvidence: [],
    probabilityTrend: [],
    horizonProfiles: {},
    emptyTitle: '接口未就绪',
    emptyMessage: '当前没有可展示的详情'
  }
}

export function createEmptyRuleOnlyClueDetailData({ clueId, query } = {}) {
  return {
    ready: false,
    query: normalizeWorkbenchQuery(query),
    clueId,
    clue: null,
    semanticCaveats: [],
    emptyTitle: '规则线索不可用',
    emptyMessage: '当前查询条件下没有可展示的规则线索详情'
  }
}

export function createEmptyOneshotData() {
  return {
    ready: false,
    oneshotSummary: {
      reportMonth: '',
      count: 0,
      dailyNewTerminalCount: 0,
      monthlyNewTerminalCount: 0,
      highPropensityCount: 0,
      averageRepurchasePropensity: '-',
      expectedRepurchaseAmount: '-',
      evidenceReady: false
    },
    oneshotTerminals: [],
    emptyTitle: '接口未就绪',
    emptyMessage: '当前没有可展示的新进终端记录'
  }
}

export function createEmptyMonthlyReportsData(query = {}) {
  const normalized = normalizeWorkbenchQuery(query)
  return {
    ready: false,
    displayLookupStatus: DISPLAY_LOOKUP_EMPTY_STATUS,
    reportContext: createEmptyReportContext(normalized),
    runtimeProfile: null,
    overviewMetrics: [],
    dailyDetectorStatus: { ...FORMAL_EMPTY_STATUS, runDate: normalized.detectorRunDate },
    dailyReportOptions: [],
    monthlyReports: [],
    emptyTitle: '接口未就绪',
    emptyMessage: '当前没有可展示的月报与批次记录'
  }
}

export function createEmptyProofCasesData() {
  return {
    ready: false,
    displayLookupStatus: DISPLAY_LOOKUP_EMPTY_STATUS,
    proofCaseHorizonTabs: [],
    proofCaseHorizonSets: {},
    proofCases: [],
    emptyTitle: '暂无正式复盘数据',
    emptyMessage: '当前接口未返回可核验的历史命中复盘'
  }
}

export async function loadWorkbenchOptions(query = {}, { allowDemo = false } = {}) {
  const normalizedQuery = normalizeWorkbenchQuery(query)
  if (allowDemo || normalizedQuery.demoMode) return loadDemo('workbenchOptions', normalizedQuery)
  const [manufacturers, context, catalog] = await Promise.all([
    tryLoad(() => api(normalizedQuery).getMyManufacturers(catalogQueryToApiParams(normalizedQuery)), mapManufacturersPayload),
    tryLoad(() => api(normalizedQuery).getReportContext(queryToReportContextParams(normalizedQuery)), (payload) => mapReportContextPayload(payload, normalizedQuery)),
    tryLoad(() => api(normalizedQuery).getDetectorCatalog(), mapDetectorCatalogPayload)
  ])
  const fallback = createEmptyWorkbenchOptions(normalizedQuery)
  return {
    ...fallback,
    manufacturerOptions: manufacturers?.manufacturerOptions?.length ? manufacturers.manufacturerOptions : fallback.manufacturerOptions,
    defaultManufacturerCode: manufacturers?.defaultManufacturerCode || fallback.defaultManufacturerCode,
    dailyDetectorDateOptions: context?.availableDetectorRunDates?.length
      ? context.availableDetectorRunDates.map((date) => ({ runDate: date, label: date }))
      : fallback.dailyDetectorDateOptions,
    detectorCatalog: catalog?.detectorCatalog || fallback.detectorCatalog,
    reportMonthOptions: context?.availableReportMonths || fallback.reportMonthOptions,
    sourceLabel: manufacturers || context ? '后端数据' : '接口未就绪'
  }
}

export async function loadWorkbenchData(query = {}, { allowDemo = false } = {}) {
  const normalizedQuery = normalizeWorkbenchQuery(query)
  if (allowDemo || normalizedQuery.demoMode) return loadDemo('workbenchData', normalizedQuery)
  const params = queryToApiParams(normalizedQuery)
  const workbenchPayload = await tryLoad(() => api(normalizedQuery).getWorkbench(params), (payload) => payload)
  if (!workbenchPayload || workbenchPayload.ready === false) {
    const context = mapReportContextPayload(workbenchPayload?.report_context || workbenchPayload, normalizedQuery)
    return createEmptyWorkbenchData(normalizedQuery, context)
  }
  return mapWorkbenchPayload(workbenchPayload, normalizedQuery)
}

export async function loadCandidateRankingData(query = {}, { page = 1, pageSize = 50 } = {}) {
  const normalizedQuery = normalizeWorkbenchQuery(query)
  if (normalizedQuery.demoMode) return createEmptyCandidateRankingData(normalizedQuery)
  const payload = await tryLoad(
    () => api(normalizedQuery).getRiskEntities({
      ...queryToApiParams(normalizedQuery),
      page,
      page_size: pageSize,
      sort_order: 'desc'
    }),
    (result) => result
  )
  return payload ? mapCandidateRankingPayload(payload, normalizedQuery) : createEmptyCandidateRankingData(normalizedQuery)
}

export function createEmptyCandidateRankingData(query = {}) {
  return {
    ready: false,
    query: normalizeWorkbenchQuery(query),
    items: [],
    pagination: { page: 1, pageSize: 50, total: 0, totalPages: 0 },
    emptyTitle: '暂无候选对象排序结果',
    emptyMessage: '当前查询条件下没有可展示的 recurring 候选对象。'
  }
}

export async function loadRuleCluesData(query = {}, { allowDemo = false } = {}) {
  const normalizedQuery = normalizeWorkbenchQuery(query)
  if (allowDemo || normalizedQuery.demoMode) return loadDemo('ruleCluesData', normalizedQuery)
  const params = queryToApiParams(normalizedQuery)
  const [context, status, clues] = await Promise.all([
    loadReportContext(normalizedQuery),
    tryLoad(() => api(normalizedQuery).getDailyDetectorStatus(params), normalizeDailyRuleStatus),
    tryLoad(() => api(normalizedQuery).getDailyDetectorClues({ ...params, sort_by: 'detector_score', page_size: normalizedQuery.topN }), mapDailyRuleCluesPayload)
  ])
  if (!status?.ready && !clues?.dailyDetectorClues?.length) return createEmptyRuleCluesData(normalizedQuery, context)
  return {
    ready: true,
    reportContext: context,
    query: normalizedQuery,
    dailyDetectorStatus: status || { ...FORMAL_EMPTY_STATUS, runDate: context.detectorRunDate },
    dailyDetectorClues: clues?.dailyDetectorClues || [],
    total: clues?.total || clues?.dailyDetectorClues?.length || 0,
    emptyTitle: '',
    emptyMessage: ''
  }
}

export async function loadClueDetailData({ clueId, riskEntityId, query } = {}, { allowDemo = false } = {}) {
  const normalizedQuery = normalizeWorkbenchQuery(query)
  if (allowDemo || normalizedQuery.demoMode) return loadDemo('clueDetailData', { clueId, riskEntityId, query: normalizedQuery })
  const context = await loadReportContext(normalizedQuery)
  if (!riskEntityId) return createEmptyClueDetailData({ query: normalizedQuery, reportContext: context })
  const detail = await loadRiskEntityDetailData(riskEntityId, normalizedQuery)
  if (!detail?.entity) return createEmptyClueDetailData({ riskEntityId, query: normalizedQuery, reportContext: context })
  return {
    ...detail,
    clue: detail.detectorEvidence[0] || {},
    isMonthlyHighRiskEntity: true,
    emptyTitle: '',
    emptyMessage: ''
  }
}

export async function loadRuleOnlyClueDetailData(clueId, query = {}) {
  const normalizedQuery = normalizeWorkbenchQuery(query)
  if (!clueId || normalizedQuery.demoMode) return createEmptyRuleOnlyClueDetailData({ clueId, query: normalizedQuery })
  const payload = await tryLoad(
    () => api(normalizedQuery).getDetectorClueDetail(clueId, queryToClueDetailParams(normalizedQuery)),
    (result) => result
  )
  if (!payload?.item) return createEmptyRuleOnlyClueDetailData({ clueId, query: normalizedQuery })
  return {
    ready: true,
    query: normalizedQuery,
    clueId,
    clue: mapRuleOnlyClueDetail(payload.item),
    semanticCaveats: Array.isArray(payload.semantic_caveats) ? payload.semantic_caveats : [],
    emptyTitle: '',
    emptyMessage: ''
  }
}

export async function loadRiskEntityDetailData(entityId, query = {}) {
  const normalizedQuery = normalizeWorkbenchQuery(query)
  const params = queryToApiParams(normalizedQuery)
  const detailPayload = await tryLoad(
    () => api(normalizedQuery).getRiskEntityDetail(entityId, params),
    (payload) => payload
  )
  if (!detailPayload || detailPayload.ready === false) return createEmptyClueDetailData({ riskEntityId: entityId, query: normalizedQuery })
  const [evidenceData, trendData] = await Promise.all([
    tryLoad(
      () => api(normalizedQuery).getRiskEntityDetectorEvidence(entityId, queryToEvidenceParams(normalizedQuery, query)),
      mapRiskEntityRuleEvidence
    ),
    tryLoad(
      () => api(normalizedQuery).getRiskEntityProbabilityTrend(entityId, params),
      mapProbabilityTrendPayload
    )
  ])
  return {
    ready: true,
    reportContext: mapReportContextPayload(detailPayload.report_context, normalizedQuery),
    query: normalizedQuery,
    entity: mapRiskEntity(detailPayload.entity || detailPayload, normalizedQuery),
    dailyDetectorStatus: { ...FORMAL_EMPTY_STATUS, ready: true, sourceLabel: '后端数据', runDate: normalizedQuery.detectorRunDate },
    detectorEvidence: evidenceData?.detectorEvidence || [],
    probabilityTrend: trendData?.probabilityTrend || [],
    horizonProfiles: mapHorizonProfiles(detailPayload.horizon_profiles || detailPayload.horizonProfiles || {}),
    emptyTitle: '',
    emptyMessage: ''
  }
}

export async function loadOneshotData(query = {}, { allowDemo = false } = {}) {
  const normalizedQuery = normalizeWorkbenchQuery(query)
  if (allowDemo || normalizedQuery.demoMode) return loadDemo('oneshotData', normalizedQuery)
  const data = await tryLoad(() => api(normalizedQuery).frontendOneshotTerminals(queryToApiParams(normalizedQuery)), mapOneshotPayload)
  return data || createEmptyOneshotData()
}

export async function loadMonthlyReportsData(query = {}, { allowDemo = false } = {}) {
  const normalizedQuery = normalizeWorkbenchQuery(query)
  if (allowDemo || normalizedQuery.demoMode) return loadDemo('monthlyReportsData', normalizedQuery)
  const [context, reports, runtime] = await Promise.all([
    loadReportContext(normalizedQuery),
    tryLoad(() => api(normalizedQuery).getMonthlyReports(queryToApiParams(normalizedQuery)), mapMonthlyReportsPayload),
    tryLoad(() => api(normalizedQuery).getRuntimeProfile({ report_month: normalizedQuery.probabilityReportMonth || normalizedQuery.reportMonth }), (payload) => payload)
  ])
  return reports || { ...createEmptyMonthlyReportsData(normalizedQuery), reportContext: context, runtimeProfile: runtime || null }
}

export async function loadProofCasesData(query = {}, { allowDemo = false } = {}) {
  const normalizedQuery = normalizeWorkbenchQuery(query)
  if (allowDemo || normalizedQuery.demoMode) return loadDemo('proofCasesData', normalizedQuery)
  const data = await tryLoad(() => api(normalizedQuery).getProofCases(queryToApiParams(normalizedQuery)), mapProofCasesPayload)
  return data || createEmptyProofCasesData()
}

function api(query = {}) {
  const normalized = normalizeWorkbenchQuery(query)
  return new BackendApi(resolveBackendBaseUrl(normalized), resolveUserId(normalized))
}

function resolveBackendBaseUrl(query = {}) {
  if (query.backendBaseUrl) return query.backendBaseUrl
  if (typeof window === 'undefined') return undefined
  const params = new URLSearchParams(window.location.search)
  try {
    return window.__BACKEND_BASE_URL__ || params.get('backendBaseUrl') || undefined
  } catch (error) {
    return window.__BACKEND_BASE_URL__ || params.get('backendBaseUrl') || undefined
  }
}

function resolveUserId(query = {}) {
  if (query.userId) return query.userId
  if (typeof window === 'undefined') return undefined
  const params = new URLSearchParams(window.location.search)
  try {
    return window.__USER_ID__ || params.get('user_id') || params.get('userId') || window.localStorage.getItem('userId') || undefined
  } catch (error) {
    return window.__USER_ID__ || params.get('user_id') || params.get('userId') || undefined
  }
}

async function tryLoad(loader, mapper) {
  try {
    return mapper(await loader())
  } catch (error) {
    return null
  }
}

async function loadDemo(loaderName, argument) {
  const demo = await import('./demoPageDataAdapter')
  return demo.demoPageLoaders[loaderName](argument)
}

function mapReportContextPayload(payload, fallbackQuery) {
  const query = normalizeWorkbenchQuery(fallbackQuery)
  if (!payload) return createEmptyReportContext(query)
  const observationDate = firstText(payload.observation_date, payload.effective_run_date, payload.requested_run_date, query.observationDate)
  const probabilityReportMonth = firstText(payload.probability_report_month, payload.effective_report_month, query.probabilityReportMonth, query.reportMonth)
  const detectorRunDate = firstText(payload.detector_run_date, payload.effective_run_date, observationDate)
  const probabilityBatchAvailable = payload.probability_batch_available !== false && Boolean(probabilityReportMonth || payload.ready === true)
  const detectorRunAvailable = payload.detector_run_available === true || payload.ready === true
  const contextStatus = payload.context_status || payload.date_resolution_status || (probabilityBatchAvailable ? 'ready' : 'probability_month_unavailable')
  const ready = payload.ready === true || probabilityBatchAvailable
  const context = {
    ready,
    observationDate,
    probabilityReportMonth,
    detectorRunDate,
    probabilityBatchAvailable,
    detectorRunAvailable,
    contextStatus,
    manualSelectionRequired: payload.manual_selection_required === true,
    availableReportMonths: payload.available_report_months || [],
    availableDetectorRunDates: payload.available_detector_run_dates || payload.available_run_dates || [],
    effectiveHorizon: payload.effective_horizon || payload.requested_horizon || query.horizon,
    requestedReportMonth: payload.requested_report_month || query.reportMonth,
    requestedRunDate: payload.requested_run_date || query.runDate,
    requestedHorizon: payload.requested_horizon || query.horizon,
    effectiveReportMonth: probabilityReportMonth || null,
    effectiveRunDate: observationDate || null,
    fallbackUsed: false,
    title: ready ? '' : '接口未就绪',
    message: contextMessage({ probabilityBatchAvailable, detectorRunAvailable, manualSelectionRequired: payload.manual_selection_required === true }),
    displayTitle: '',
    displayLines: []
  }
  if (!probabilityBatchAvailable) {
    context.displayTitle = context.message
  } else if (!detectorRunAvailable) {
    context.displayTitle = '该观察日期暂无规则巡检结果'
  } else if (context.manualSelectionRequired) {
    context.displayTitle = context.message
  }
  context.displayLines = [
    `观察日期：${context.observationDate || '-'}`,
    `规则巡检日期：${context.detectorRunDate || '-'}`
  ]
  return context
}

function contextMessage({ probabilityBatchAvailable, detectorRunAvailable, manualSelectionRequired }) {
  if (!probabilityBatchAvailable) return '该观察日期对应的月报基准尚未生成，请选择可用日期或月份'
  if (!detectorRunAvailable) return '该观察日期暂无规则巡检结果'
  if (manualSelectionRequired) return '请选择可用月份或规则巡检日期'
  return ''
}

function mapWorkbenchPayload(payload, fallbackQuery, related = {}) {
  const reportContext = mapReportContextPayload(payload.report_context, fallbackQuery)
  const query = normalizeWorkbenchQuery({
    ...fallbackQuery,
    manufacturer_code: payload.query?.manufacturer_code || payload.current_manufacturer_code,
    observation_date: reportContext.observationDate || payload.query?.observation_date,
    report_month: reportContext.probabilityReportMonth || payload.query?.report_month,
    probability_report_month: reportContext.probabilityReportMonth,
    detector_run_date: reportContext.detectorRunDate,
    horizon: reportContext.effectiveHorizon || payload.query?.horizon || payload.horizon,
    topN: payload.query?.top_n || payload.top_n,
    sortBy: payload.query?.sort_by || payload.sort_by
  })
  const rows = (payload.risk_entities || payload.rows || payload.today_focus?.risk_entities || []).map((row) => mapWorkbenchRow(row, query))
  const topRuleClues = (payload.top_rule_clues || related.clues?.dailyDetectorClues || []).map(mapDailyRuleClue)
  const detectorSummary = normalizeDetectorSummary(payload.daily_detector_summary || payload.detector_summary, related.status, topRuleClues, rows, query, reportContext)
  const emptyCopy = workbenchEmptyCopy(payload.empty_reason)
  const scope = mapScope(payload.scope, query)
  return {
    ready: true,
    reportContext,
    displayLookupStatus: related.displayLookupStatus || normalizeDisplayLookupStatus(payload.display_lookup_status),
    query,
    scope,
    overviewMetrics: buildTodayMetrics(rows, detectorSummary, { ...query, manufacturerName: scope.manufacturerName }, reportContext),
    dailyDetectorStatus: related.status || {
      ...FORMAL_EMPTY_STATUS,
      ready: detectorSummary.ready,
      sourceLabel: '后端数据',
      runDate: detectorSummary.runDate,
      clueCount: detectorSummary.clueCount,
      attachedHighRiskCount: detectorSummary.attachedHighRiskCount,
      scannedEntityCount: detectorSummary.scannedEntityCount,
      statusText: detectorSummary.ready ? '规则巡检结果已更新' : '该观察日期暂无规则巡检结果'
    },
    detectorSummary,
    workbenchDisplayRows: rows,
    topRuleClues,
    emptyTitle: rows.length ? '' : emptyCopy.title,
    emptyMessage: rows.length ? '' : emptyCopy.message
  }
}

function mapCandidateRankingPayload(payload, fallbackQuery) {
  const query = normalizeWorkbenchQuery({
    ...fallbackQuery,
    manufacturer_code: payload.query?.manufacturer_code || payload.scope?.effective_manufacturer_code,
    horizon: payload.query?.horizon || fallbackQuery.horizon,
    sortBy: payload.query?.sort_by || fallbackQuery.sortBy
  })
  const items = (payload.items || payload.entities || []).map((item) => ({
    ...mapWorkbenchRow(item, query),
    rank: Number(item.rank || 0)
  }))
  const pagination = payload.pagination || {}
  return {
    ready: true,
    query,
    items,
    pagination: {
      page: Number(pagination.page || 1),
      pageSize: Number(pagination.page_size || items.length || 50),
      total: Number(pagination.total || 0),
      totalPages: Number(pagination.total_pages || 0)
    },
    emptyTitle: items.length ? '' : '暂无候选对象排序结果',
    emptyMessage: items.length ? '' : '当前查询条件下没有可展示的 recurring 候选对象。'
  }
}

function mapScope(scope = {}, query) {
  const code = scope.manufacturer_code || scope.effective_manufacturer_code || query.manufacturerCode
  return {
    manufacturerCode: code,
    manufacturerName: resolveManufacturerPresentation({
      manufacturerCode: code,
      manufacturerDisplayName: scope.manufacturer_display_name,
      manufacturerName: scope.manufacturer_name,
      fallbackLabel: code ? '生产企业（名称未接入）' : '未选择生产企业'
    }).displayName,
    reportMonth: scope.report_month || query.probabilityReportMonth || query.reportMonth
  }
}

function workbenchEmptyCopy(emptyReason) {
  if (emptyReason === 'NO_RISK_ENTITIES_IN_SELECTED_SCOPE' || emptyReason === 'NO_RISK_ENTITIES_IN_SELECTED_MANUFACTURER_SCOPE') {
    return {
      title: '当前条件下暂无风险对象',
      message: '该生产企业、观察日期和预测窗口下没有可展示的重点风险对象。'
    }
  }
  return { title: '', message: '' }
}

function normalizeDisplayLookupStatus(payload) {
  if (!payload) return DISPLAY_LOOKUP_EMPTY_STATUS
  return {
    ready: payload.ready === true,
    label: payload.ready === true ? '展示名映射已接通' : '展示名映射未接通',
    message: payload.message || ''
  }
}

function normalizeDailyRuleStatus(payload) {
  if (payload?.ready !== true) {
    return {
      ...FORMAL_EMPTY_STATUS,
      ready: false,
      runDate: payload?.detector_run_date || payload?.run_date || '-',
      statusText: payload?.context_status === 'detector_run_unavailable' ? '该观察日期暂无规则巡检结果' : '接口未就绪'
    }
  }
  return {
    ready: true,
    sourceLabel: '后端数据',
    runDate: payload.detector_run_date || payload.run_date || payload.effective_run_date,
    reportMonth: payload.probability_report_month || payload.report_month || payload.effective_report_month,
    clueCount: payload.clue_count ?? payload.total ?? 0,
    attachedHighRiskCount: payload.attached_high_risk_count ?? 0,
    scannedEntityCount: payload.scanned_entity_count ?? 0,
    statusText: '规则巡检结果已更新',
    caveat: ''
  }
}

function normalizeDetectorSummary(summary = {}, status = {}, clues = [], rows = [], query, context) {
  const clueCount = summary?.clue_count ?? summary?.detector_clue_count ?? status?.clueCount ?? clues.length ?? 0
  return {
    ready: summary?.ready !== false && status?.ready !== false && context.detectorRunAvailable !== false,
    runDate: summary?.detector_run_date || summary?.run_date || status?.runDate || context.detectorRunDate || query.detectorRunDate,
    clueCount,
    attachedHighRiskCount: summary?.attached_high_risk_count ?? status?.attachedHighRiskCount ?? clues.filter((item) => item.isMonthlyHighRiskEntity).length,
    scannedEntityCount: summary?.scanned_entity_count ?? status?.scannedEntityCount ?? 0,
    highestRuleScore: summary?.highest_detector_score ?? highestRuleScore(clues),
    priorityRiskEntityCount: summary?.priority_risk_entity_count ?? rows.length
  }
}

function mapWorkbenchRow(row, query) {
  const manufacturer = resolveManufacturerPresentation({
    manufacturerCode: row.manufacturer_code || query.manufacturerCode,
    manufacturerDisplayName: row.manufacturer_display_name,
    manufacturerName: row.manufacturer_name
  }).displayName
  const hospital = firstDisplayText(row.hospital_display_name, row.hospital_name, row.hospital_code)
  const drug = firstDisplayText(row.drug_display_name, row.drug_name, row.drug_code, row.drug_group)
  const involvedAmount = firstNullableNumber(row.involved_amount, row.average_consumption_in_window, row.window_consumption)
  const lossValue = firstNullableNumber(row.loss_value, row.monthly_loss_value)
  return {
    id: row.row_id || row.entity_id || `${hospital}-${drug}`,
    entityId: row.entity_id || row.risk_entity_id || '',
    rank: Number(row.rank || 0),
    manufacturer,
    manufacturerCode: row.manufacturer_code || query.manufacturerCode,
    hospital,
    drug,
    hospitalDrugKey: `${hospital} × ${drug}`,
    region: firstDisplayText(row.region_display_name, row.region, row.region_code),
    horizon: row.horizon || query.horizon,
    riskProbability: firstNumber(row.risk_probability),
    probabilityDisplay: formatPercent(firstNumber(row.risk_probability)),
    involvedAmount,
    involvedAmountText: formatMoney(involvedAmount),
    lossValue,
    lossValueText: lossValue === null || lossValue === undefined ? '-' : formatMoney(lossValue),
    riskBand: row.risk_band || row.riskLevel || '',
    reason: replaceHorizonCodes(row.reason || row.primary_reason || ''),
    fillSource: '月报高风险',
    sourceType: '月报高风险',
    action: row.action || '查看详情'
  }
}

function mapRiskEntity(item, query = defaultWorkbenchQuery) {
  const profile = item.selected_horizon_profile || item
  const involvedAmount = firstNullableNumber(profile.involved_amount, item.involved_amount, profile.average_consumption_in_window, item.average_consumption_in_window)
  const lossValue = firstNullableNumber(profile.loss_value, item.loss_value)
  return {
    id: item.entity_id || item.risk_entity_id || item.id,
    hospital: firstDisplayText(item.hospital_display_name, item.hospital_name, item.hospital_code, item.hospital),
    drug: firstDisplayText(item.drug_display_name, item.drug_name, item.drug_code, item.drug_group, item.drug),
    manufacturer: resolveManufacturerPresentation({
      manufacturerCode: item.manufacturer_code || query.manufacturerCode,
      manufacturerDisplayName: item.manufacturer_display_name,
      manufacturerName: item.manufacturer_name || item.manufacturer
    }).displayName,
    manufacturerCode: item.manufacturer_code || query.manufacturerCode,
    region: firstDisplayText(item.region_display_name, item.region, item.region_code),
    horizon: profile.horizon || item.horizon || query.horizon,
    riskLevel: profile.risk_band || item.risk_band || item.riskLevel || '-',
    riskColor: item.risk_color || item.riskColor || 'red',
    riskProbability: firstNumber(profile.risk_probability, item.risk_probability),
    probabilityDisplay: formatPercent(firstNumber(profile.risk_probability, item.risk_probability)),
    involvedAmount,
    involvedAmountText: formatMoney(involvedAmount),
    lossValue,
    lossValueText: lossValue === null || lossValue === undefined ? '-' : formatMoney(lossValue),
    status: item.status || item.monthly_status || '',
    reason: replaceHorizonCodes(profile.reason || item.primary_reason || item.reason || '')
  }
}

function mapHorizonProfiles(profiles) {
  return Object.fromEntries(Object.entries(profiles || {}).map(([horizon, profile]) => [horizon, mapHorizonProfile(profile)]))
}

function mapHorizonProfile(profile) {
  const involvedAmount = firstNullableNumber(profile.involved_amount, profile.average_consumption_in_window, profile.window_consumption)
  const lossValue = firstNullableNumber(profile.loss_value)
  return {
    horizon: profile.horizon,
    horizonLabel: formatHorizonLabel(profile.horizon),
    riskProbability: firstNumber(profile.risk_probability),
    probabilityDisplay: formatPercent(firstNumber(profile.risk_probability)),
    involvedAmount,
    involvedAmountText: formatMoney(involvedAmount),
    lossValue,
    lossValueText: lossValue === null || lossValue === undefined ? '-' : formatMoney(lossValue),
    reason: replaceHorizonCodes(profile.reason)
  }
}

function mapOneshotPayload(payload) {
  if (payload?.ready === false) return createEmptyOneshotData()
  const items = payload.items || payload.rows || []
  const hasEvidence = items.some((item) => item.reason || item.evidence_text || item.ranking_basis)
  return {
    ready: true,
    oneshotSummary: {
      reportMonth: payload.report_month || payload.probability_report_month || '',
      count: payload.summary?.oneshot_count ?? items.length ?? 0,
      dailyNewTerminalCount: payload.summary?.daily_new_terminal_count ?? 0,
      monthlyNewTerminalCount: payload.summary?.monthly_new_terminal_count ?? 0,
      highPropensityCount: payload.summary?.high_repurchase_propensity_count ?? 0,
      averageRepurchasePropensity: formatPercent(payload.summary?.average_repurchase_propensity),
      expectedRepurchaseAmount: formatMoney(payload.summary?.expected_repurchase_amount),
      evidenceReady: hasEvidence
    },
    oneshotTerminals: items.map((item) => ({
      id: item.oneshot_id || item.id,
      manufacturer: resolveManufacturerPresentation({
        manufacturerCode: item.manufacturer_code,
        manufacturerDisplayName: item.manufacturer_display_name,
        manufacturerName: item.manufacturer_name
      }).displayName,
      manufacturerCode: item.manufacturer_code || '',
      hospital: firstDisplayText(item.hospital_display_name, item.hospital_name, item.hospital_code),
      drug: firstDisplayText(item.drug_display_name, item.drug_name, item.drug_code, item.drug_group),
      region: firstDisplayText(item.region_display_name, item.region, item.region_code),
      firstPurchaseDate: item.first_purchase_date,
      firstPurchaseAmount: item.first_purchase_amount,
      firstPurchaseAmountText: formatMoney(item.first_purchase_amount),
      daysSinceFirstPurchase: item.days_since_first_purchase,
      repurchasePropensity: item.repurchase_propensity,
      repurchasePropensityText: formatPercent(item.repurchase_propensity),
      expectedRepurchaseAmountText: formatMoney(item.expected_repurchase_amount),
      priority: item.priority,
      reason: hasEvidence ? replaceHorizonCodes(item.ranking_basis || item.reason || item.evidence_text) : ''
    })),
    emptyTitle: items.length ? '' : '当前条件下暂无新进终端记录',
    emptyMessage: items.length ? '' : '该观察日期和生产企业范围内没有可展示的新进终端。'
  }
}

function mapMonthlyReportsPayload(payload) {
  if (!payload || payload.ready === false) return null
  return {
    ready: true,
    displayLookupStatus: normalizeDisplayLookupStatus(payload.display_lookup_status),
    reportContext: mapReportContextPayload(payload.report_context, {}),
    runtimeProfile: null,
    overviewMetrics: payload.overview_metrics || [],
    dailyDetectorStatus: normalizeDailyRuleStatus(payload.daily_detector_status || payload.detector_status || {}),
    dailyReportOptions: (payload.daily_report_options || []).map((item) => ({
      id: item.daily_report_id || item.id,
      date: item.date || item.observation_date,
      label: item.label,
      title: item.title,
      reportMonth: item.report_month || item.probability_report_month,
      scoreBatchId: item.score_batch_id || item.batch_id,
      dataWatermarkAt: item.data_watermark_at || item.observation_date,
      highRiskEntities: String(item.high_risk_entities ?? '-'),
      oneshotCount: String(item.oneshot_count ?? '-'),
      detectorAlerts: String(item.detector_alerts ?? item.rule_clue_count ?? '-'),
      summary: replaceHorizonCodes(item.summary)
    })),
    monthlyReports: (payload.monthly_reports || payload.items || []).map((item) => ({
      id: item.monthly_report_id || item.id,
      title: item.title,
      reportMonth: item.report_month || item.probability_report_month,
      scoreBatchId: item.score_batch_id || item.batch_id,
      dataWatermarkAt: item.data_watermark_at || item.observation_date,
      summary: replaceHorizonCodes(item.summary)
    })),
    emptyTitle: '',
    emptyMessage: ''
  }
}

function mapProofCasesPayload(payload) {
  if (!payload || payload.ready === false) return null
  return {
    ready: true,
    displayLookupStatus: normalizeDisplayLookupStatus(payload.display_lookup_status),
    proofCaseHorizonTabs: payload.horizon_tabs || [],
    proofCaseHorizonSets: payload.horizon_sets || {},
    proofCases: payload.items || payload.proof_cases || [],
    emptyTitle: '',
    emptyMessage: ''
  }
}

function mapDailyRuleCluesPayload(payload) {
  if (payload?.ready === false) return { dailyDetectorClues: [], total: 0 }
  const items = payload.items || payload.rows || payload.clues || []
  return {
    dailyDetectorClues: items.map(mapDailyRuleClue),
    total: payload.total ?? items.length
  }
}

function mapDailyRuleClue(item, index = 0) {
  if (item.detectorScoreLabel === '规则巡检分') return item
  const isMonthly = item.is_monthly_high_risk_entity === true || Boolean(item.risk_entity_id)
  const involvedAmount = firstNullableNumber(item.involved_amount, item.monthly_involved_amount)
  const title = item.display_name || item.title || `规则线索 #${item.display_rank || index + 1}`
  return {
    id: item.detector_clue_id || item.id || title,
    riskEntityId: item.risk_entity_id || '',
    sourceType: isMonthly ? 'monthly_high_risk' : 'daily_rule_clue',
    sourceTypeLabel: isMonthly ? '月报高风险' : '仅规则命中',
    isMonthlyHighRiskEntity: isMonthly,
    hospital: firstDisplayText(item.hospital_display_name, item.hospital_name, title),
    drug: firstDisplayText(item.drug_display_name, item.drug_name, item.drug_group, '规则线索'),
    manufacturer: resolveManufacturerPresentation({
      manufacturerCode: item.manufacturer_code,
      manufacturerDisplayName: item.manufacturer_display_name,
      manufacturerName: item.manufacturer_name
    }).displayName,
    region: firstDisplayText(item.region_display_name, item.region_code),
    detectorName: item.detector_name_label || item.detector_name || item.detector_id || '规则',
    detectorFamily: item.detector_family || '',
    detectorFamilyLabel: item.detector_family_label || detectorFamilyLabel(item.detector_family),
    detectorId: item.detector_id || '',
    detectorRunId: item.detector_run_id || '',
    detectorScore: item.detector_score,
    detectorScoreText: formatRuleScore(item.detector_score),
    detectorScoreLabel: '规则巡检分',
    detectorLevel: item.detector_level || item.confidence || '-',
    rootCauseLabel: item.root_cause_label || '规则命中',
    evidenceText: item.evidence_text || item.caveat || '',
    evidencePayload: item.evidence_payload,
    detectorRunDate: item.detector_run_date || item.run_date,
    monthlyRiskProbability: item.monthly_risk_probability ?? item.risk_probability,
    monthlyRiskProbabilityText:
      item.monthly_risk_probability === null || item.monthly_risk_probability === undefined
        ? item.risk_probability === null || item.risk_probability === undefined
          ? '-'
          : formatPercent(item.risk_probability)
        : formatPercent(item.monthly_risk_probability),
    involvedAmount,
    involvedAmountText: involvedAmount === null || involvedAmount === undefined ? '-' : formatMoney(involvedAmount),
    lossValue: firstNullableNumber(item.loss_value),
    lossValueText: formatMoney(firstNullableNumber(item.loss_value)),
    actionText: isMonthly ? '查看风险详情' : '查看线索详情'
  }
}

function mapRuleOnlyClueDetail(item) {
  const clue = mapDailyRuleClue(item)
  return {
    ...clue,
    confidence: item.confidence,
    hitFlag: item.hit_flag === true,
    rootCause: item.root_cause_label || '',
    evidencePayload: normalizeEvidencePayload(item.evidence_payload),
    observationDate: item.run_date || '',
    manufacturer: firstDisplayText(item.manufacturer_display_name, item.manufacturer_name, item.manufacturer_code),
    hospital: firstDisplayText(item.hospital_display_name, item.hospital_name, item.hospital_code),
    drug: firstDisplayText(item.drug_display_name, item.drug_name, item.drug_group),
    relationshipLabel: '未关联月度风险候选'
  }
}

function normalizeEvidencePayload(value) {
  if (value === null || value === undefined || value === '') return null
  if (typeof value === 'string') {
    try {
      return JSON.parse(value)
    } catch {
      return value
    }
  }
  return value
}

function mapRiskEntityRuleEvidence(payload) {
  return {
    detectorEvidence: (payload.items || []).map((item, index) => ({
      ...mapDailyRuleClue(
        {
          detector_clue_id: `${item.risk_entity_id}-${item.detector_id}-${index}`,
          detector_run_id: item.detector_run_id,
          run_date: item.run_date,
          detector_id: item.detector_id,
          detector_name_label: item.detector_name_label,
          detector_name: item.detector_name,
          detector_family: item.detector_family,
          detector_family_label: item.detector_family_label,
          detector_score: item.detector_score,
          detector_level: item.confidence,
          root_cause_label: item.root_cause_label,
          evidence_text: item.evidence_text,
          is_monthly_high_risk_entity: true,
          risk_entity_id: item.risk_entity_id,
          monthly_risk_probability: payload.monthly_risk_probability,
          monthly_involved_amount: payload.monthly_involved_amount ?? payload.involved_amount,
          caveat: item.caveat
        },
        index
      ),
      detectorName: item.detector_name_label || payload.catalog_by_detector_id?.[item.detector_id]?.detector_name || item.detector_name || item.detector_id,
      detectorFamilyLabel: item.detector_family_label || detectorFamilyLabel(item.detector_family),
      monitoringLogic: item.monitoring_logic || {},
      observedValues: item.observed_values || {},
      decision: item.decision || {},
      currentValueText: evidenceCurrentValue(item.observed_values || {}),
      baselineValueText: evidenceBaselineValue(item.observed_values || {}),
      comparisonText: evidenceComparison(item.decision || {})
    }))
  }
}

function evidenceCurrentValue(values) {
  return firstDisplayText(values.current_gap_days, values.recent_quantity, values.recent_frequency) || '-'
}

function evidenceBaselineValue(values) {
  return firstDisplayText(values.historical_median_interval_days, values.baseline_quantity, values.baseline_frequency) || '-'
}

function evidenceComparison(decision) {
  const value = decision.comparison_value
  const threshold = decision.threshold_value
  const operator = decision.threshold_operator || ''
  if (value === null || value === undefined) return '-'
  return threshold === null || threshold === undefined ? String(value) : `${value} ${operator} ${threshold}`
}

function mapProbabilityTrendPayload(payload) {
  return {
    probabilityTrend: (payload.items || payload.trend || []).map((item) => {
      const involvedAmount = firstNullableNumber(item.involved_amount, item.average_consumption_in_window)
      return {
        reportMonth: item.report_month,
        riskProbability: firstNumber(item.risk_probability),
        riskProbabilityText: formatPercent(firstNumber(item.risk_probability)),
        involvedAmount,
        involvedAmountText: involvedAmount === null || involvedAmount === undefined ? '-' : formatMoney(involvedAmount),
        lossValue: firstNullableNumber(item.loss_value),
        lossValueText: formatMoney(firstNullableNumber(item.loss_value))
      }
    })
  }
}

export function queryToReportContextParams(query) {
  const params = {
    observation_date: query.observationDate,
    manufacturer_code: query.manufacturerCode,
    horizon: query.horizon,
    top_n: query.topN,
    sort_by: query.sortBy,
    user_id: query.userId
  }
  if (query.observationDate) return params
  return {
    ...params,
    report_month: query.probabilityReportMonth || query.reportMonth,
    run_date: query.runDate,
    probability_report_month: query.probabilityReportMonth || query.reportMonth,
    detector_run_date: query.detectorRunDate
  }
}

function queryToApiParams(query) {
  return {
    observation_date: query.observationDate,
    report_month: query.probabilityReportMonth || query.reportMonth,
    run_date: query.runDate || query.observationDate,
    probability_report_month: query.probabilityReportMonth || query.reportMonth,
    detector_run_date: query.detectorRunDate || query.observationDate,
    manufacturer_code: query.manufacturerCode,
    detector_family: query.detectorFamily,
    detector_id: query.detectorId,
    horizon: query.horizon,
    top_n: query.topN,
    sort_by: query.sortBy,
    user_id: query.userId
  }
}

function queryToClueDetailParams(query) {
  return {
    detector_run_id: query.detectorRunId || undefined,
    run_date: query.detectorRunDate || query.observationDate || undefined,
    manufacturer_code: query.manufacturerCode || undefined
  }
}

function catalogQueryToApiParams(query) {
  return {
    user_id: query.userId
  }
}

function queryToEvidenceParams(query, source = {}) {
  return {
    ...queryToApiParams(query),
    detector_family: source.detectorFamily || source.detector_family,
    detector_id: source.detectorId || source.detector_id,
    detector_run_id: source.detectorRunId || source.detector_run_id
  }
}

function mapManufacturersPayload(payload) {
  const items = payload?.manufacturers || payload?.items || []
  if (!items.length && payload?.ready !== true && payload?.ready !== 'conditional') return null
  const manufacturerOptions = items.map((item, index) => ({
    code: item.manufacturer_code || item.code || item.id,
    name: manufacturerDisplayName(item, index)
  }))
  return {
    manufacturerCount: payload?.manufacturer_count ?? items.length,
    defaultManufacturerCode: payload?.default_manufacturer_code || manufacturerOptions[0]?.code,
    manufacturerOptions
  }
}

function mapDetectorCatalogPayload(payload) {
  const items = payload?.items || []
  return {
    detectorCatalog: items.map((item) => ({
      detectorId: item.detector_id,
      detectorFamily: item.detector_family,
      detectorFamilyLabel: detectorFamilyLabel(item.detector_family),
      detectorName: item.detector_name || item.detector_id,
      status: item.status
    }))
  }
}

function buildTodayMetrics(rows, detectorSummary, query, context = {}) {
  const manufacturer = resolveManufacturerPresentation({
    manufacturerCode: query.manufacturerCode,
    manufacturerDisplayName: query.manufacturerDisplayName,
    manufacturerName: query.manufacturerName
  }).displayName
  return [
    { label: '当前生产企业', value: manufacturer || '未选择', tone: 'info' },
    { label: '观察日期', value: context.observationDate || query.observationDate || '-', tone: 'neutral' },
    { label: '规则巡检日期', value: context.detectorRunDate || query.detectorRunDate || '-', tone: 'success' },
    { label: '当前预测窗口', value: formatHorizonLabel(query.horizon), tone: 'warning' },
    { label: '今日线索总数', value: String(detectorSummary.clueCount ?? 0), tone: 'success' },
    { label: '最高规则巡检分', value: detectorSummary.highestRuleScore === null || detectorSummary.highestRuleScore === undefined ? '-' : String(detectorSummary.highestRuleScore), tone: 'danger' },
    { label: '重点风险对象数量', value: String(detectorSummary.priorityRiskEntityCount ?? rows.length), tone: 'info' }
  ]
}

function manufacturerDisplayName(item, index) {
  const code = item.manufacturer_code || item.code || item.id || ''
  const name = item.manufacturer_display_name || item.manufacturer_name || item.name || ''
  return resolveManufacturerPresentation({
    manufacturerCode: code,
    manufacturerDisplayName: name,
    manufacturerName: name,
    fallbackLabel: `生产企业 ${index + 1}（名称未接入）`
  }).displayName
}

export function resolveManufacturerPresentation({
  manufacturerCode,
  manufacturerDisplayName,
  manufacturerName,
  fallbackLabel = '生产企业（名称未接入）'
} = {}) {
  const code = String(manufacturerCode || '').trim()
  const candidates = [manufacturerDisplayName, manufacturerName]
    .map((value) => String(value || '').trim())
    .filter(Boolean)
  const name = candidates.find((value) => value !== code && !looksLikeCode(value))
  return {
    code,
    displayName: name || fallbackLabel,
    hasDisplayName: Boolean(name)
  }
}

function looksLikeCode(value) {
  const text = String(value || '').trim()
  return /^[A-F0-9]{24,}$/i.test(text) || /^[0-9a-f]{8}-[0-9a-f-]{27,}$/i.test(text)
}

function detectorFamilyLabel(family) {
  const labels = {
    interval: '采购间隔',
    purchase_interval: '采购间隔',
    quantity: '采购数量',
    purchase_quantity: '采购数量',
    frequency: '采购频次',
    purchase_frequency: '采购频次',
    assortment: 'SKU 结构',
    fulfillment: '履约交付',
    price: '价格',
    peer: '同群对比'
  }
  return labels[family] || family || '未分类'
}

function currentManufacturerOption(query) {
  return query.manufacturerCode
    ? [{ code: query.manufacturerCode, name: resolveManufacturerPresentation({ manufacturerCode: query.manufacturerCode }).displayName }]
    : []
}

function highestRuleScore(items = []) {
  const scores = items.map((item) => Number(item.detectorScore ?? item.detector_score)).filter((value) => !Number.isNaN(value))
  if (!scores.length) return null
  const max = Math.max(...scores)
  return max <= 1 ? Math.round(max * 100) : Math.round(max)
}

function firstDisplayText(...values) {
  return values.find((value) => value !== undefined && value !== null && String(value).trim() !== '') || ''
}

function firstText(...values) {
  return values.find((value) => value !== undefined && value !== null && String(value).trim() !== '') || ''
}

function firstNumber(...values) {
  for (const value of values) {
    if (value === undefined || value === null || value === '') continue
    const number = Number(value)
    if (!Number.isNaN(number)) return number
  }
  return 0
}

function firstNullableNumber(...values) {
  for (const value of values) {
    if (value === undefined || value === null || value === '') continue
    const number = Number(value)
    if (!Number.isNaN(number)) return number
  }
  return null
}

function parseBoolean(value) {
  if (value === true) return true
  if (value === false) return false
  return String(value || '').toLowerCase() === 'true'
}

function setParam(params, key, value) {
  if (value !== undefined && value !== null && value !== '') params.set(key, String(value))
}

function defaultRunDate() {
  const now = new Date()
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
  return local.toISOString().slice(0, 10)
}

function formatRuleScore(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-'
  const score = Number(value)
  return score <= 1 ? String(Math.round(score * 100)) : String(Math.round(score))
}

function formatHorizonLabel(value) {
  const labels = { H3: '3月', H6: '6月', H12: '12月' }
  return labels[value] || replaceHorizonCodes(value || '-')
}

function replaceHorizonCodes(value) {
  if (value === null || value === undefined) return value
  return String(value).replaceAll('H12', '12月').replaceAll('H6', '6月').replaceAll('H3', '3月')
}

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-'
  return `${Math.round(Number(value) * 100)}%`
}

function formatMoney(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-'
  return `¥${Math.round(Number(value)).toLocaleString('zh-CN')}`
}
