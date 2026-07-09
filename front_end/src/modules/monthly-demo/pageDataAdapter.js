import { BackendApi } from '../../services/backendApi'
import {
  batchContext,
  dailyDetectorClues,
  dailyDetectorDateOptions,
  dailyDetectorStatus,
  dailyReportOptions,
  defaultWorkbenchQuery,
  horizonOptions,
  manufacturerOptions,
  monthlyReports,
  oneshotSummary,
  oneshotTerminals,
  overviewMetrics,
  probabilityTrendByEntityId,
  proofCaseHorizonSets,
  proofCaseHorizonTabs,
  proofCases,
  riskCardHorizonProfiles,
  riskEntities,
  sortOptions,
  topNOptions,
  workbenchDisplayRows
} from './demoData'

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
  const reportMonth = query.reportMonth || query.report_month || defaultReportMonth()
  const runDate = query.runDate || query.run_date || defaultRunDate()
  const horizon = horizonOptions.some((item) => item.id === query.horizon) ? query.horizon : defaultWorkbenchQuery.horizon
  const topN = topNOptions.includes(Number(query.topN)) ? Number(query.topN) : defaultWorkbenchQuery.topN
  const sortBy = sortOptions.some((item) => item.id === query.sortBy) ? query.sortBy : defaultWorkbenchQuery.sortBy
  const demoModeParam = query.demoMode ?? query.demo_mode
  return {
    backendBaseUrl: query.backendBaseUrl || query.backend_base_url || undefined,
    userId: query.userId || query.user_id || query.userID || undefined,
    demoMode: parseBoolean(demoModeParam),
    demoModeParam: demoModeParam === undefined || demoModeParam === null ? undefined : String(demoModeParam),
    manufacturerCode: query.manufacturerCode || query.manufacturer_code || defaultWorkbenchQuery.manufacturerCode,
    reportMonth,
    runDate,
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
  setParam(params, 'manufacturer_code', normalized.manufacturerCode)
  setParam(params, 'report_month', normalized.reportMonth)
  setParam(params, 'run_date', normalized.runDate)
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
    requestedReportMonth: normalized.reportMonth,
    requestedRunDate: normalized.runDate,
    requestedHorizon: normalized.horizon,
    effectiveReportMonth: null,
    effectiveRunDate: null,
    effectiveHorizon: null,
    fallbackUsed: false,
    title: '接口未就绪',
    message: '当前数据接口未返回可用月报结果',
    displayTitle: '接口未就绪',
    displayLines: []
  }
}

export async function loadReportContext(query = {}) {
  const normalized = normalizeWorkbenchQuery(query)
  if (normalized.demoMode) return createDemoReportContext(normalized)
  const reportContext = await tryLoad(
    () => api(normalized).getReportContext(queryToApiParams(normalized)),
    (payload) => mapReportContextPayload(payload, normalized)
  )
  return reportContext || createEmptyReportContext(normalized)
}

export function applyReportContextToQuery(query = {}, reportContext = {}) {
  const normalized = normalizeWorkbenchQuery(query)
  if (!reportContext.ready) return normalized
  return normalizeWorkbenchQuery({
    ...normalized,
    reportMonth: reportContext.effectiveReportMonth || normalized.reportMonth,
    runDate: reportContext.effectiveRunDate || normalized.runDate,
    horizon: reportContext.effectiveHorizon || normalized.horizon
  })
}

export function createEmptyWorkbenchOptions(query = {}) {
  const normalized = normalizeWorkbenchQuery(query)
  return {
    manufacturerOptions: currentManufacturerOption(normalized),
    defaultManufacturerCode: normalized.manufacturerCode,
    dailyDetectorDateOptions: [{ runDate: normalized.runDate, label: normalized.runDate }],
    horizonOptions,
    topNOptions,
    sortOptions,
    sourceLabel: '接口未就绪'
  }
}

export function createStaticWorkbenchOptions() {
  return {
    manufacturerOptions,
    defaultManufacturerCode: manufacturerOptions[0]?.code || defaultWorkbenchQuery.manufacturerCode,
    dailyDetectorDateOptions,
    horizonOptions,
    topNOptions,
    sortOptions,
    sourceLabel: '演示模式'
  }
}

export function createEmptyWorkbenchData(query = {}, reportContext = createEmptyReportContext(query)) {
  const normalized = normalizeWorkbenchQuery(query)
  return {
    ready: false,
    reportContext,
    displayLookupStatus: DISPLAY_LOOKUP_EMPTY_STATUS,
    query: normalized,
    scope: {
      manufacturerCode: normalized.manufacturerCode,
      manufacturerName: manufacturerName(normalized.manufacturerCode),
      reportMonth: normalized.reportMonth
    },
    batchContext: {
      ...batchContext,
      reportMonth: normalized.reportMonth,
      primaryHorizon: formatHorizonLabel(normalized.horizon)
    },
    overviewMetrics: buildTodayMetrics([], { clueCount: 0 }, normalized),
    dailyDetectorStatus: { ...FORMAL_EMPTY_STATUS, runDate: normalized.runDate },
    detectorSummary: {
      runDate: normalized.runDate,
      clueCount: 0,
      attachedHighRiskCount: 0,
      scannedEntityCount: 0,
      highestRuleScore: null,
      priorityRiskEntityCount: 0
    },
    workbenchDisplayRows: [],
    emptyTitle: reportContext.displayTitle || '接口未就绪',
    emptyMessage: reportContext.message || '当前没有可展示的风险对象'
  }
}

export function createStaticWorkbenchData(query = {}) {
  const normalizedQuery = normalizeWorkbenchQuery({ ...query, demoMode: true })
  const rows = buildStaticWorkbenchRows(normalizedQuery)
  const detectorSummary = {
    runDate: normalizedQuery.runDate,
    clueCount: dailyDetectorStatus.clueCount,
    attachedHighRiskCount: dailyDetectorStatus.attachedHighRiskCount,
    scannedEntityCount: dailyDetectorStatus.scannedEntityCount,
    highestRuleScore: highestRuleScore(dailyDetectorClues),
    priorityRiskEntityCount: rows.length
  }
  return {
    ready: true,
    reportContext: createDemoReportContext(normalizedQuery),
    displayLookupStatus: { ready: false, label: '演示模式', message: '' },
    query: normalizedQuery,
    scope: {
      manufacturerCode: normalizedQuery.manufacturerCode,
      manufacturerName: manufacturerName(normalizedQuery.manufacturerCode),
      reportMonth: normalizedQuery.reportMonth
    },
    batchContext: {
      ...batchContext,
      reportMonth: normalizedQuery.reportMonth,
      primaryHorizon: formatHorizonLabel(normalizedQuery.horizon)
    },
    overviewMetrics: buildTodayMetrics(rows, detectorSummary, normalizedQuery),
    dailyDetectorStatus: {
      ...dailyDetectorStatus,
      sourceLabel: '演示模式',
      runDate: normalizedQuery.runDate
    },
    detectorSummary,
    workbenchDisplayRows: rows,
    emptyTitle: '',
    emptyMessage: ''
  }
}

export function createEmptyRuleCluesData(query = {}, reportContext = createEmptyReportContext(query)) {
  const normalized = normalizeWorkbenchQuery(query)
  return {
    ready: false,
    reportContext,
    query: normalized,
    dailyDetectorStatus: { ...FORMAL_EMPTY_STATUS, runDate: normalized.runDate },
    dailyDetectorClues: [],
    emptyTitle: reportContext.displayTitle || '接口未就绪',
    emptyMessage: reportContext.message || '当前没有可展示的规则线索'
  }
}

export function createStaticRuleCluesData(query = {}) {
  const normalizedQuery = normalizeWorkbenchQuery({ ...query, demoMode: true })
  return {
    ready: true,
    reportContext: createDemoReportContext(normalizedQuery),
    query: normalizedQuery,
    dailyDetectorStatus: { ...dailyDetectorStatus, sourceLabel: '演示模式', runDate: normalizedQuery.runDate },
    dailyDetectorClues: buildStaticRuleClues(normalizedQuery),
    emptyTitle: '',
    emptyMessage: ''
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
    dailyDetectorStatus: { ...FORMAL_EMPTY_STATUS, runDate: normalized.runDate },
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

export function createStaticClueDetailData({ clueId, riskEntityId, query } = {}) {
  const normalizedQuery = normalizeWorkbenchQuery({ ...query, demoMode: true })
  const clues = buildStaticRuleClues(normalizedQuery)
  const clue = clues.find((item) => item.id === clueId) || clues.find((item) => item.riskEntityId === riskEntityId) || clues[0]
  const entity = clue?.riskEntityId ? riskEntities.find((item) => item.id === clue.riskEntityId) : null
  const selectedProfile = entity ? riskCardHorizonProfiles[entity.id]?.[normalizedQuery.horizon] : null
  return {
    ready: true,
    reportContext: createDemoReportContext(normalizedQuery),
    query: normalizedQuery,
    clue: clue || {},
    entity: entity && selectedProfile ? mergeEntityProfile(entity, selectedProfile) : entity || null,
    isMonthlyHighRiskEntity: Boolean(entity),
    detectorEvidence: entity ? mapStaticRuleEvidence(entity, normalizedQuery) : clue ? [clue] : [],
    probabilityTrend: entity ? probabilityTrendByEntityId[entity.id] || [] : [],
    horizonProfiles: entity ? riskCardHorizonProfiles[entity.id] || {} : {},
    emptyTitle: '',
    emptyMessage: ''
  }
}

export function createStaticOneshotData() {
  return {
    ready: true,
    displayLookupStatus: { ready: false, label: '演示模式', message: '' },
    oneshotSummary: {
      ...oneshotSummary,
      evidenceReady: false
    },
    oneshotTerminals: oneshotTerminals.map(({ reason, ...item }) => item),
    emptyTitle: '',
    emptyMessage: ''
  }
}

export function createEmptyOneshotData() {
  return {
    ready: false,
    oneshotSummary: {
      reportMonth: '',
      count: 0,
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

export function createStaticMonthlyReportsData() {
  return {
    ready: true,
    displayLookupStatus: { ready: false, label: '演示模式', message: '' },
    batchContext,
    overviewMetrics,
    dailyDetectorStatus,
    dailyReportOptions,
    monthlyReports
  }
}

export function createEmptyMonthlyReportsData(query = {}) {
  const normalized = normalizeWorkbenchQuery(query)
  return {
    ready: false,
    displayLookupStatus: DISPLAY_LOOKUP_EMPTY_STATUS,
    batchContext: {
      ...batchContext,
      reportMonth: normalized.reportMonth,
      primaryHorizon: formatHorizonLabel(normalized.horizon)
    },
    overviewMetrics: [],
    dailyDetectorStatus: { ...FORMAL_EMPTY_STATUS, runDate: normalized.runDate },
    dailyReportOptions: [],
    monthlyReports: [],
    emptyTitle: '接口未就绪',
    emptyMessage: '当前没有可展示的月报记录'
  }
}

export function createStaticProofCasesData() {
  return { ready: true, displayLookupStatus: { ready: false, label: '演示模式', message: '' }, proofCaseHorizonTabs, proofCaseHorizonSets, proofCases }
}

export function createEmptyProofCasesData() {
  return {
    ready: false,
    displayLookupStatus: DISPLAY_LOOKUP_EMPTY_STATUS,
    proofCaseHorizonTabs: [],
    proofCaseHorizonSets: {},
    proofCases: [],
    emptyTitle: '页面暂不展示',
    emptyMessage: '请从 VP 工作台查看当前风险对象和规则线索'
  }
}

export async function loadWorkbenchOptions(query = {}, { allowDemo = false } = {}) {
  const normalizedQuery = normalizeWorkbenchQuery(query)
  if (allowDemo || normalizedQuery.demoMode) return createStaticWorkbenchOptions()
  const [manufacturers, dates] = await Promise.all([
    tryLoad(() => api(normalizedQuery).getMyManufacturers(queryToApiParams(normalizedQuery)), mapManufacturersPayload),
    tryLoad(() => api(normalizedQuery).getDailyDetectorDates(queryToApiParams(normalizedQuery)), mapDailyDetectorDatesPayload)
  ])
  return {
    ...createEmptyWorkbenchOptions(normalizedQuery),
    manufacturerOptions: manufacturers?.manufacturerOptions?.length ? manufacturers.manufacturerOptions : currentManufacturerOption(normalizedQuery),
    defaultManufacturerCode: manufacturers?.defaultManufacturerCode || normalizedQuery.manufacturerCode,
    dailyDetectorDateOptions: dates?.dailyDetectorDateOptions?.length
      ? dates.dailyDetectorDateOptions
      : [{ runDate: normalizedQuery.runDate, label: normalizedQuery.runDate }],
    sourceLabel: manufacturers || dates ? '后端数据' : '接口未就绪'
  }
}

export async function loadWorkbenchData(query = {}, { allowDemo = false } = {}) {
  const normalizedQuery = normalizeWorkbenchQuery(query)
  if (allowDemo || normalizedQuery.demoMode) return createStaticWorkbenchData(normalizedQuery)
  const payload = await tryLoad(
    () => api(normalizedQuery).getWorkbench(queryToApiParams(normalizedQuery)),
    (data) => data
  )
  if (!payload || payload.ready === false) {
    return createEmptyWorkbenchData(normalizedQuery, mapReportContextPayload(payload?.report_context || payload, normalizedQuery))
  }
  return mapWorkbenchPayload(payload, normalizedQuery)
}

export async function loadRuleCluesData(query = {}, { allowDemo = false } = {}) {
  const normalizedQuery = normalizeWorkbenchQuery(query)
  if (allowDemo || normalizedQuery.demoMode) return createStaticRuleCluesData(normalizedQuery)
  const status = await tryLoad(
    () => api(normalizedQuery).getDailyDetectorStatus(queryToApiParams(normalizedQuery)),
    normalizeDailyRuleStatus
  )
  if (!status?.ready) return createEmptyRuleCluesData(normalizedQuery)
  const clues = await tryLoadDailyRuleClues(normalizedQuery)
  return {
    ready: true,
    reportContext: createReadyReportContextFromQuery(normalizedQuery),
    query: normalizedQuery,
    dailyDetectorStatus: {
      ...status,
      clueCount: clues?.dailyDetectorClues?.length ?? status.clueCount,
      attachedHighRiskCount:
        clues?.dailyDetectorClues?.filter((item) => item.isMonthlyHighRiskEntity).length ?? status.attachedHighRiskCount
    },
    dailyDetectorClues: clues?.dailyDetectorClues || [],
    emptyTitle: '',
    emptyMessage: ''
  }
}

export async function loadClueDetailData({ clueId, riskEntityId, query } = {}, { allowDemo = false } = {}) {
  const normalizedQuery = normalizeWorkbenchQuery(query)
  if (allowDemo || normalizedQuery.demoMode) return createStaticClueDetailData({ clueId, riskEntityId, query: normalizedQuery })

  if (riskEntityId) {
    const detail = await loadRiskEntityDetailData(riskEntityId, normalizedQuery)
    if (!detail?.entity) return createEmptyClueDetailData({ clueId, riskEntityId, query: normalizedQuery })
    const clue = detail.detectorEvidence[0] || {}
    return {
      ...detail,
      clue,
      isMonthlyHighRiskEntity: true,
      emptyTitle: '',
      emptyMessage: ''
    }
  }

  const cluesData = await loadRuleCluesData(normalizedQuery)
  const clue = cluesData.dailyDetectorClues?.find((item) => item.id === clueId)
  if (!clue) return createEmptyClueDetailData({ clueId, query: normalizedQuery })
  return {
    ...cluesData,
    clue,
    entity: null,
    isMonthlyHighRiskEntity: false,
    detectorEvidence: [clue],
    probabilityTrend: [],
    horizonProfiles: {},
    emptyTitle: '',
    emptyMessage: ''
  }
}

export async function loadRiskEntityDetailData(entityId, query = {}) {
  const normalizedQuery = normalizeWorkbenchQuery(query)
  const detailPayload = await tryLoad(
    () => api(normalizedQuery).getRiskEntityDetail(entityId, { horizon: normalizedQuery.horizon }),
    (payload) => payload
  )
  if (!detailPayload || detailPayload.ready === false) return createEmptyClueDetailData({ riskEntityId: entityId, query: normalizedQuery })
  const [evidenceData, trendData] = await Promise.all([
    tryLoad(
      () => api(normalizedQuery).getRiskEntityDetectorEvidence(entityId, queryToEvidenceParams(normalizedQuery, query)),
      mapRiskEntityRuleEvidence
    ),
    tryLoad(
      () => api(normalizedQuery).getRiskEntityProbabilityTrend(entityId, { horizon: normalizedQuery.horizon }),
      mapProbabilityTrendPayload
    )
  ])
  return {
    ready: true,
    reportContext: mapReportContextPayload(detailPayload.report_context, normalizedQuery),
    query: normalizedQuery,
    entity: mapRiskEntity(detailPayload.entity || detailPayload, normalizedQuery),
    dailyDetectorStatus: { ...dailyDetectorStatus, sourceLabel: '后端数据', runDate: normalizedQuery.runDate },
    detectorEvidence: evidenceData?.detectorEvidence || [],
    probabilityTrend: trendData?.probabilityTrend || [],
    horizonProfiles: mapHorizonProfiles(detailPayload.horizon_profiles || detailPayload.horizonProfiles || {}),
    emptyTitle: '',
    emptyMessage: ''
  }
}

export async function loadOneshotData(query = {}, { allowDemo = false } = {}) {
  const normalizedQuery = normalizeWorkbenchQuery(query)
  if (allowDemo || normalizedQuery.demoMode) return createStaticOneshotData()
  const data = await tryLoad(() => api(normalizedQuery).frontendOneshotTerminals(), mapOneshotPayload)
  return data || createEmptyOneshotData()
}

export async function loadMonthlyReportsData(query = {}, { allowDemo = false } = {}) {
  const normalizedQuery = normalizeWorkbenchQuery(query)
  if (allowDemo || normalizedQuery.demoMode) return createStaticMonthlyReportsData()
  const data = await tryLoad(() => api(normalizedQuery).getMonthlyReports(), mapMonthlyReportsPayload)
  return data || createEmptyMonthlyReportsData(normalizedQuery)
}

export async function loadProofCasesData(query = {}, { allowDemo = false } = {}) {
  const normalizedQuery = normalizeWorkbenchQuery(query)
  if (allowDemo || normalizedQuery.demoMode) return createStaticProofCasesData()
  return createEmptyProofCasesData()
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
    return window.__BACKEND_BASE_URL__ || params.get('backendBaseUrl') || window.localStorage.getItem('backendBaseUrl') || undefined
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

async function tryLoadDailyRuleClues(query) {
  const params = queryToApiParams(query)
  const dailyClues = await tryLoad(() => api(query).getDailyDetectorClues({ ...params, page_size: 100 }), mapDailyRuleCluesPayload)
  if (dailyClues) return dailyClues
  return tryLoad(() => api(query).getDetectorClues({ ...params, page_size: 100 }), mapDailyRuleCluesPayload)
}

function mapReportContextPayload(payload, fallbackQuery) {
  const query = normalizeWorkbenchQuery(fallbackQuery)
  if (!payload) return createEmptyReportContext(query)
  const ready = payload.ready === true
  const context = {
    ready,
    requestedReportMonth: payload.requested_report_month || query.reportMonth,
    requestedRunDate: payload.requested_run_date || query.runDate,
    requestedHorizon: payload.requested_horizon || query.horizon,
    effectiveReportMonth: payload.effective_report_month || null,
    effectiveRunDate: payload.effective_run_date || null,
    effectiveHorizon: payload.effective_horizon || null,
    fallbackUsed: payload.fallback_used === true,
    title: ready ? '数据已就绪' : '接口未就绪',
    message: ready ? '' : '当前数据接口未返回可用月报结果',
    displayTitle: ready && payload.fallback_used === true ? '当前展示最近可用数据' : ready ? '' : '接口未就绪',
    displayLines: []
  }
  if (ready && context.fallbackUsed) {
    context.displayLines = [
      `观察日期：${context.effectiveRunDate}`,
      `月报月份：${context.effectiveReportMonth}`
    ]
  }
  return context
}

function createDemoReportContext(query = {}) {
  const normalized = normalizeWorkbenchQuery(query)
  return {
    ready: true,
    requestedReportMonth: normalized.reportMonth,
    requestedRunDate: normalized.runDate,
    requestedHorizon: normalized.horizon,
    effectiveReportMonth: normalized.reportMonth,
    effectiveRunDate: normalized.runDate,
    effectiveHorizon: normalized.horizon,
    fallbackUsed: false,
    title: '演示模式',
    message: '',
    displayTitle: '',
    displayLines: []
  }
}

function createReadyReportContextFromQuery(query = {}) {
  const normalized = normalizeWorkbenchQuery(query)
  return {
    ready: true,
    requestedReportMonth: normalized.reportMonth,
    requestedRunDate: normalized.runDate,
    requestedHorizon: normalized.horizon,
    effectiveReportMonth: normalized.reportMonth,
    effectiveRunDate: normalized.runDate,
    effectiveHorizon: normalized.horizon,
    fallbackUsed: false,
    title: '',
    message: '',
    displayTitle: '',
    displayLines: []
  }
}

function mapWorkbenchPayload(payload, fallbackQuery) {
  const reportContext = mapReportContextPayload(payload.report_context, fallbackQuery)
  const query = normalizeWorkbenchQuery({
    ...fallbackQuery,
    manufacturer_code: payload.query?.manufacturer_code || payload.current_manufacturer_code,
    report_month: reportContext.effectiveReportMonth || payload.query?.report_month || payload.effective_report_month,
    run_date: reportContext.effectiveRunDate || payload.query?.run_date || payload.effective_run_date,
    horizon: reportContext.effectiveHorizon || payload.query?.horizon || payload.horizon,
    topN: payload.query?.top_n || payload.top_n,
    sortBy: payload.query?.sort_by || payload.sort_by
  })
  const rows = (payload.rows || payload.monthly_risk_entities || []).map((row) => mapWorkbenchRow(row, query))
  const detectorSummary = normalizeDetectorSummary(payload.detector_summary, payload, rows, query)
  return {
    ready: true,
    reportContext,
    displayLookupStatus: normalizeDisplayLookupStatus(payload.display_lookup_status),
    query,
    scope: mapScope(payload.scope, query),
    batchContext: {
      ...batchContext,
      reportMonth: query.reportMonth,
      primaryHorizon: formatHorizonLabel(query.horizon)
    },
    overviewMetrics: buildTodayMetrics(rows, detectorSummary, query),
    dailyDetectorStatus: {
      ...dailyDetectorStatus,
      ready: true,
      sourceLabel: '后端数据',
      runDate: detectorSummary.runDate || query.runDate,
      clueCount: detectorSummary.clueCount,
      attachedHighRiskCount: detectorSummary.attachedHighRiskCount,
      scannedEntityCount: detectorSummary.scannedEntityCount,
      statusText: '规则巡检结果已更新',
      caveat: ''
    },
    detectorSummary,
    workbenchDisplayRows: rows,
    emptyTitle: '',
    emptyMessage: ''
  }
}

function mapScope(scope = {}, query) {
  return {
    manufacturerCode: scope.manufacturer_code || query.manufacturerCode,
    manufacturerName: scope.manufacturer_display_name || scope.manufacturer_name || manufacturerName(query.manufacturerCode),
    reportMonth: scope.report_month || query.reportMonth
  }
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
  if (payload?.ready !== true) return { ...FORMAL_EMPTY_STATUS, ready: false }
  return {
    ready: true,
    sourceLabel: '后端数据',
    runDate: payload.run_date || payload.effective_run_date || dailyDetectorStatus.runDate,
    reportMonth: payload.report_month || payload.effective_report_month || batchContext.reportMonth,
    clueCount: payload.clue_count ?? payload.total ?? 0,
    attachedHighRiskCount: payload.attached_high_risk_count ?? 0,
    scannedEntityCount: payload.scanned_entity_count ?? 0,
    statusText: '规则巡检结果已更新',
    caveat: ''
  }
}

function normalizeDetectorSummary(summary = {}, payload = {}, rows = [], query) {
  const clueCount = summary.clue_count ?? summary.detector_clue_count ?? payload.today_clue_count ?? 0
  return {
    runDate: summary.run_date || summary.latest_detector_run_date || payload.current_observation_date || query.runDate,
    clueCount,
    attachedHighRiskCount: summary.attached_high_risk_count ?? summary.attached_evidence_count ?? 0,
    scannedEntityCount: summary.scanned_entity_count ?? 0,
    highestRuleScore: payload.highest_detector_score ?? highestRuleScore(payload.today_high_score_rule_clues || []),
    priorityRiskEntityCount: payload.priority_risk_entity_count ?? rows.length
  }
}

function mapWorkbenchRow(row, query) {
  const manufacturer = firstDisplayText(row.manufacturer_display_name, row.manufacturer_name, row.manufacturer_code)
  const hospital = firstDisplayText(row.hospital_display_name, row.hospital_name, row.hospital_code)
  const drug = firstDisplayText(row.drug_display_name, row.drug_name, row.drug_code, row.drug_group)
  const involvedAmount = firstNumber(row.involved_amount, row.average_consumption_in_window, row.window_consumption)
  return {
    id: row.row_id || row.entity_id || `${hospital}-${drug}`,
    entityId: row.entity_id || row.risk_entity_id || '',
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
    riskBand: row.risk_band || row.riskLevel || '',
    reason: replaceHorizonCodes(row.reason || row.primary_reason || ''),
    fillSource: row.source_type || '月报高风险',
    sourceType: row.source_type || '月报高风险',
    action: row.action || '查看详情'
  }
}

function mapRiskEntity(item, query = defaultWorkbenchQuery) {
  const profile = item.selected_horizon_profile || item
  const involvedAmount = firstNumber(profile.involved_amount, item.involved_amount, profile.average_consumption_in_window, item.average_consumption_in_window)
  return {
    id: item.entity_id || item.risk_entity_id || item.id,
    hospital: firstDisplayText(item.hospital_display_name, item.hospital_name, item.hospital_code, item.hospital),
    drug: firstDisplayText(item.drug_display_name, item.drug_name, item.drug_code, item.drug_group, item.drug),
    manufacturer: firstDisplayText(item.manufacturer_display_name, item.manufacturer_name, item.manufacturer_code, item.manufacturer),
    manufacturerCode: item.manufacturer_code || query.manufacturerCode,
    region: firstDisplayText(item.region_display_name, item.region, item.region_code),
    horizon: profile.horizon || item.horizon || query.horizon,
    riskLevel: profile.risk_band || item.risk_band || item.riskLevel || '-',
    riskColor: item.risk_color || item.riskColor || 'red',
    riskProbability: firstNumber(profile.risk_probability, item.risk_probability),
    probabilityDisplay: formatPercent(firstNumber(profile.risk_probability, item.risk_probability)),
    involvedAmount,
    involvedAmountText: formatMoney(involvedAmount),
    status: item.status || item.monthly_status || '',
    reason: replaceHorizonCodes(profile.reason || item.primary_reason || item.reason || ''),
    detectorResults: (profile.detector_results || item.detectorResults || []).map(mapRuleResult)
  }
}

function mapHorizonProfiles(profiles) {
  return Object.fromEntries(Object.entries(profiles || {}).map(([horizon, profile]) => [horizon, mapHorizonProfile(profile)]))
}

function mapHorizonProfile(profile) {
  const involvedAmount = firstNumber(profile.involved_amount, profile.average_consumption_in_window, profile.window_consumption)
  return {
    horizon: profile.horizon,
    horizonLabel: formatHorizonLabel(profile.horizon),
    riskProbability: firstNumber(profile.risk_probability),
    probabilityDisplay: formatPercent(firstNumber(profile.risk_probability)),
    involvedAmount,
    involvedAmountText: formatMoney(involvedAmount),
    reason: replaceHorizonCodes(profile.reason),
    detectorResults: (profile.detector_results || []).map(mapRuleResult)
  }
}

function mapRuleResult(item) {
  return {
    id: item.detector_id || item.id,
    name: item.detector_name || item.name,
    detectorScore: item.detector_score ?? item.score,
    detectorScoreText: formatRuleScore(item.detector_score ?? item.score),
    detectorScoreLabel: '规则巡检分',
    signal: item.signal,
    status: item.status,
    evidence: replaceHorizonCodes(item.evidence),
    action: item.action
  }
}

function mapOneshotPayload(payload) {
  if (payload?.ready === false) return createEmptyOneshotData()
  const hasEvidence = (payload.items || []).some((item) => item.reason || item.evidence_text)
  return {
    ready: true,
    oneshotSummary: {
      reportMonth: payload.report_month,
      count: payload.summary?.oneshot_count ?? payload.items?.length ?? 0,
      highPropensityCount: payload.summary?.high_repurchase_propensity_count ?? 0,
      averageRepurchasePropensity: formatPercent(payload.summary?.average_repurchase_propensity),
      expectedRepurchaseAmount: formatMoney(payload.summary?.expected_repurchase_amount),
      evidenceReady: hasEvidence
    },
    oneshotTerminals: (payload.items || []).map((item) => ({
      id: item.oneshot_id || item.id,
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
      reason: hasEvidence ? replaceHorizonCodes(item.reason || item.evidence_text) : ''
    })),
    emptyTitle: '',
    emptyMessage: ''
  }
}

function mapMonthlyReportsPayload(payload) {
  if (!payload || payload.ready === false) return createEmptyMonthlyReportsData()
  return {
    ready: true,
    displayLookupStatus: normalizeDisplayLookupStatus(payload.display_lookup_status),
    batchContext: {
      ...batchContext,
      reportMonth: payload.batch_context?.report_month || payload.report_month || '',
      primaryHorizon: payload.batch_context?.primary_horizon || ''
    },
    overviewMetrics: payload.overview_metrics || [],
    dailyDetectorStatus: normalizeDailyRuleStatus(payload.daily_detector_status || payload.detector_status || {}),
    dailyReportOptions: (payload.daily_report_options || []).map((item) => ({
      id: item.daily_report_id,
      date: item.date,
      label: item.label,
      title: item.title,
      reportMonth: item.report_month,
      scoreBatchId: item.score_batch_id,
      dataWatermarkAt: item.data_watermark_at,
      highRiskEntities: String(item.high_risk_entities),
      oneshotCount: String(item.oneshot_count),
      detectorAlerts: String(item.detector_alerts),
      summary: replaceHorizonCodes(item.summary)
    })),
    monthlyReports: (payload.monthly_reports || []).map((item) => ({
      id: item.monthly_report_id,
      title: item.title,
      reportMonth: item.report_month,
      scoreBatchId: item.score_batch_id,
      dataWatermarkAt: item.data_watermark_at,
      summary: replaceHorizonCodes(item.summary)
    }))
  }
}

function mapDailyRuleCluesPayload(payload) {
  if (payload?.ready === false) return null
  const items = payload.items || payload.rows || payload.clues || []
  return {
    dailyDetectorClues: items.map(mapDailyRuleClue)
  }
}

function mapDailyRuleClue(item, index = 0) {
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
    manufacturer: firstDisplayText(item.manufacturer_display_name, item.manufacturer_code),
    region: firstDisplayText(item.region_display_name, item.region_code),
    detectorName: item.detector_name || item.detector_id || '规则',
    detectorFamily: item.detector_family || '规则',
    detectorId: item.detector_id || '',
    detectorRunId: item.detector_run_id || '',
    detectorScore: item.detector_score,
    detectorScoreText: formatRuleScore(item.detector_score),
    detectorScoreLabel: '规则巡检分',
    detectorLevel: item.detector_level || item.confidence || '-',
    rootCauseLabel: item.root_cause_label || '规则命中',
    evidenceText: item.evidence_text || item.caveat || '',
    detectorRunDate: item.run_date,
    monthlyRiskProbability: item.monthly_risk_probability ?? item.risk_probability,
    monthlyRiskProbabilityText:
      item.monthly_risk_probability === null || item.monthly_risk_probability === undefined
        ? item.risk_probability === null || item.risk_probability === undefined
          ? '-'
          : formatPercent(item.risk_probability)
        : formatPercent(item.monthly_risk_probability),
    involvedAmount,
    involvedAmountText: involvedAmount === null || involvedAmount === undefined ? '-' : formatMoney(involvedAmount),
    actionText: isMonthly ? '查看风险详情' : '查看线索详情'
  }
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
          detector_name: item.detector_name,
          detector_family: item.detector_family,
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
      detectorName: payload.catalog_by_detector_id?.[item.detector_id]?.detector_name || item.detector_name || item.detector_id
    }))
  }
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
        involvedAmountText: involvedAmount === null || involvedAmount === undefined ? '-' : formatMoney(involvedAmount)
      }
    })
  }
}

function mapStaticRuleEvidence(entity, query) {
  return (entity.detectorResults || []).map((item) => ({
    id: `${entity.id}-${item.id}`,
    riskEntityId: entity.id,
    sourceType: 'monthly_high_risk',
    sourceTypeLabel: '月报高风险',
    isMonthlyHighRiskEntity: true,
    hospital: entity.hospital,
    drug: entity.drug,
    manufacturer: entity.manufacturer,
    region: entity.region,
    detectorName: item.name,
    detectorFamily: item.family || '规则',
    detectorId: item.id,
    detectorRunId: `${query.runDate}-${item.id}`,
    detectorScore: item.detectorScore ?? item.score,
    detectorScoreText: formatRuleScore(item.detectorScore ?? item.score),
    detectorScoreLabel: '规则巡检分',
    detectorLevel: item.signal,
    rootCauseLabel: item.status,
    evidenceText: item.evidence,
    detectorRunDate: query.runDate,
    monthlyRiskProbability: entity.riskProbability,
    monthlyRiskProbabilityText: entity.probabilityDisplay,
    involvedAmount: entity.involvedAmount,
    involvedAmountText: entity.involvedAmountText,
    actionText: item.action
  }))
}

function buildStaticWorkbenchRows(query) {
  const rows = workbenchDisplayRows
    .filter((row) => !query.manufacturerCode || row.manufacturer === query.manufacturerCode || row.manufacturerCode === query.manufacturerCode)
    .map((row) => {
      if (!row.entityId) return applyStaticFallbackHorizon(row, query.horizon)
      const entity = riskEntities.find((item) => item.id === row.entityId)
      const profile = entity ? riskCardHorizonProfiles[entity.id]?.[query.horizon] : null
      return profile && entity ? mapStaticEntityRow(entity, profile) : row
    })

  const sorted = rows.sort((a, b) => {
    if (query.sortBy === 'involved_amount') return b.involvedAmount - a.involvedAmount
    return b.riskProbability - a.riskProbability
  })
  return sorted.slice(0, query.topN)
}

function buildStaticRuleClues(query) {
  return dailyDetectorClues.map((item) => {
    if (!item.riskEntityId) return { ...item, detectorRunDate: query.runDate }
    const entity = riskEntities.find((riskEntity) => riskEntity.id === item.riskEntityId)
    const profile = entity ? riskCardHorizonProfiles[entity.id]?.[query.horizon] : null
    return {
      ...item,
      sourceTypeLabel: item.sourceTypeLabel === '月报高风险对象' ? '月报高风险' : item.sourceTypeLabel,
      detectorRunDate: query.runDate,
      monthlyRiskProbability: profile?.riskProbability ?? item.monthlyRiskProbability,
      monthlyRiskProbabilityText: profile?.probabilityDisplay ?? item.monthlyRiskProbabilityText,
      involvedAmount: profile?.involvedAmount ?? item.involvedAmount,
      involvedAmountText: profile?.involvedAmountText ?? item.involvedAmountText
    }
  })
}

function mapStaticEntityRow(entity, profile) {
  return {
    id: entity.id,
    entityId: entity.id,
    manufacturer: entity.manufacturer,
    manufacturerCode: entity.manufacturer,
    hospital: entity.hospital,
    drug: entity.drug,
    hospitalDrugKey: `${entity.hospital} × ${entity.drug}`,
    region: entity.region,
    horizon: profile.horizon,
    riskProbability: profile.riskProbability,
    probabilityDisplay: profile.probabilityDisplay,
    involvedAmount: profile.involvedAmount,
    involvedAmountText: profile.involvedAmountText,
    fillSource: '月报高风险',
    sourceType: '月报高风险',
    action: '查看详情'
  }
}

function applyStaticFallbackHorizon(row, horizon) {
  const factors = { H3: { p: -0.08, a: 0.5 }, H6: { p: 0, a: 1 }, H12: { p: 0.06, a: 1.65 } }
  const factor = factors[horizon] || factors.H6
  const riskProbability = Math.max(0.05, Math.min(0.95, Number((row.riskProbability + factor.p).toFixed(2))))
  const involvedAmount = Math.round(row.involvedAmount * factor.a)
  return {
    ...row,
    sourceType: row.sourceType || '规则线索',
    fillSource: row.fillSource || '规则线索',
    horizon,
    riskProbability,
    probabilityDisplay: formatPercent(riskProbability),
    involvedAmount,
    involvedAmountText: formatMoney(involvedAmount)
  }
}

function mergeEntityProfile(entity, profile) {
  return {
    ...entity,
    horizon: profile.horizon,
    riskProbability: profile.riskProbability,
    probabilityDisplay: profile.probabilityDisplay,
    involvedAmount: profile.involvedAmount,
    involvedAmountText: profile.involvedAmountText,
    reason: profile.reason,
    detectorResults: profile.detectorResults
  }
}

function queryToApiParams(query) {
  return {
    manufacturer_code: query.manufacturerCode,
    report_month: query.reportMonth,
    run_date: query.runDate,
    horizon: query.horizon,
    top_n: query.topN,
    sort_by: query.sortBy
  }
}

function queryToEvidenceParams(query, source = {}) {
  return {
    run_date: query.runDate,
    detector_family: source.detectorFamily || source.detector_family,
    detector_id: source.detectorId || source.detector_id,
    detector_run_id: source.detectorRunId || source.detector_run_id
  }
}

function mapManufacturersPayload(payload) {
  const items = payload.manufacturers || payload.items || []
  if (!items.length && payload?.ready === false) return null
  const manufacturerOptions = items.map((item) => ({
    code: item.manufacturer_code || item.code || item.id,
    name: item.manufacturer_display_name || item.manufacturer_name || item.name || item.manufacturer_code || item.code
  }))
  return {
    manufacturerCount: payload.manufacturer_count ?? items.length,
    defaultManufacturerCode: payload.default_manufacturer_code || manufacturerOptions[0]?.code,
    manufacturerOptions
  }
}

function mapDailyDetectorDatesPayload(payload) {
  if (payload?.ready === false) return null
  const items = payload.items || payload.dates || []
  return {
    dailyDetectorDateOptions: items.map((item) => ({
      runDate: item.run_date || item.date || item,
      label: item.label || item.run_date || item.date || item
    }))
  }
}

function buildTodayMetrics(rows, detectorSummary, query) {
  return [
    { label: '当前生产企业', value: manufacturerName(query.manufacturerCode), tone: 'info' },
    { label: '当前观察日期', value: query.runDate || '-', tone: 'neutral' },
    { label: '当前预测窗口', value: formatHorizonLabel(query.horizon), tone: 'warning' },
    { label: '今日线索总数', value: String(detectorSummary.clueCount ?? 0), tone: 'success' },
    { label: '最高规则巡检分', value: detectorSummary.highestRuleScore === null || detectorSummary.highestRuleScore === undefined ? '-' : String(detectorSummary.highestRuleScore), tone: 'danger' },
    { label: '重点风险对象数量', value: String(detectorSummary.priorityRiskEntityCount ?? rows.length), tone: 'info' }
  ]
}

function currentManufacturerOption(query) {
  return [{ code: query.manufacturerCode, name: manufacturerName(query.manufacturerCode) }]
}

function manufacturerName(code) {
  return manufacturerOptions.find((item) => item.code === code)?.name || code || '-'
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

function defaultReportMonth() {
  return defaultRunDate().slice(0, 7)
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
