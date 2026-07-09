import { BackendApi } from '../../services/backendApi'
import {
  batchContext,
  dailyDetectorClues,
  dailyDetectorDateOptions,
  dailyDetectorStatus,
  dailyReportOptions,
  defaultWorkbenchQuery,
  detectorCatalogSummary,
  detectorConfigStatus,
  globalCurrentMonthHospitalDrugCount,
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
  workbenchDisplayRows,
  workbenchFillPolicy
} from './demoData'

const DISPLAY_LOOKUP_DEMO_STATUS = {
  ready: false,
  label: '演示数据',
  message: '展示名映射未接通'
}

export function normalizeWorkbenchQuery(query = {}) {
  const horizon = horizonOptions.some((item) => item.id === query.horizon) ? query.horizon : defaultWorkbenchQuery.horizon
  const topN = topNOptions.includes(Number(query.topN)) ? Number(query.topN) : defaultWorkbenchQuery.topN
  const sortBy = sortOptions.some((item) => item.id === query.sortBy) ? query.sortBy : defaultWorkbenchQuery.sortBy
  return {
    manufacturerCode: query.manufacturerCode || query.manufacturer_code || defaultWorkbenchQuery.manufacturerCode,
    reportMonth: query.reportMonth || query.report_month || defaultWorkbenchQuery.reportMonth,
    runDate: query.runDate || query.run_date || defaultWorkbenchQuery.runDate,
    horizon,
    topN,
    sortBy
  }
}

export function createStaticWorkbenchOptions() {
  return {
    manufacturerOptions,
    dailyDetectorDateOptions,
    horizonOptions,
    topNOptions,
    sortOptions,
    sourceLabel: '演示数据'
  }
}

export function createStaticWorkbenchData(query = {}) {
  const normalizedQuery = normalizeWorkbenchQuery(query)
  return {
    displayLookupStatus: DISPLAY_LOOKUP_DEMO_STATUS,
    query: normalizedQuery,
    scope: {
      manufacturerCode: normalizedQuery.manufacturerCode,
      manufacturerName: manufacturerName(normalizedQuery.manufacturerCode),
      reportMonth: normalizedQuery.reportMonth
    },
    batchContext: {
      ...batchContext,
      primaryHorizon: formatHorizonLabel(normalizedQuery.horizon)
    },
    overviewMetrics,
    dailyDetectorStatus: {
      ...dailyDetectorStatus,
      runDate: normalizedQuery.runDate
    },
    detectorSummary: {
      runDate: normalizedQuery.runDate,
      clueCount: dailyDetectorStatus.clueCount,
      attachedHighRiskCount: dailyDetectorStatus.attachedHighRiskCount
    },
    detectorCatalogSummary,
    detectorConfigStatus,
    globalCurrentMonthHospitalDrugCount,
    workbenchFillPolicy: {
      ...workbenchFillPolicy,
      manufacturer: normalizedQuery.manufacturerCode,
      workbenchTargetCount: normalizedQuery.topN
    },
    workbenchDisplayRows: buildStaticWorkbenchRows(normalizedQuery)
  }
}

export function createStaticRiskEntitiesData(query = {}) {
  const normalizedQuery = normalizeWorkbenchQuery(query)
  return {
    displayLookupStatus: DISPLAY_LOOKUP_DEMO_STATUS,
    query: normalizedQuery,
    dailyDetectorStatus: { ...dailyDetectorStatus, runDate: normalizedQuery.runDate },
    detectorCatalogSummary,
    detectorConfigStatus,
    dailyDetectorClues: buildStaticRuleClues(normalizedQuery)
  }
}

export function createStaticRiskEntityDetailData(entityId, query = {}) {
  const normalizedQuery = normalizeWorkbenchQuery(query)
  const entity = riskEntities.find((item) => item.id === entityId) || riskEntities[0]
  const selectedProfile = riskCardHorizonProfiles[entity.id]?.[normalizedQuery.horizon]
  const clue = dailyDetectorClues.find((item) => item.riskEntityId === entity.id) || dailyDetectorClues[0]
  return {
    displayLookupStatus: DISPLAY_LOOKUP_DEMO_STATUS,
    query: normalizedQuery,
    dailyDetectorStatus: { ...dailyDetectorStatus, runDate: normalizedQuery.runDate },
    entity: selectedProfile ? mergeEntityProfile(entity, selectedProfile) : entity,
    clue: {
      ...clue,
      detectorRunDate: normalizedQuery.runDate
    },
    isMonthlyHighRiskEntity: true,
    detectorEvidence: mapStaticDetectorEvidence(entity, normalizedQuery),
    probabilityTrend: probabilityTrendByEntityId[entity.id] || [],
    horizonProfiles: riskCardHorizonProfiles[entity.id] || {}
  }
}

export function createStaticRuleCluesData(query = {}) {
  const normalizedQuery = normalizeWorkbenchQuery(query)
  return {
    query: normalizedQuery,
    dailyDetectorStatus: { ...dailyDetectorStatus, runDate: normalizedQuery.runDate },
    detectorCatalogSummary,
    detectorConfigStatus,
    dailyDetectorClues: buildStaticRuleClues(normalizedQuery)
  }
}

export function createStaticClueDetailData({ clueId, riskEntityId, query } = {}) {
  const normalizedQuery = normalizeWorkbenchQuery(query)
  const clues = buildStaticRuleClues(normalizedQuery)
  const clue = clues.find((item) => item.id === clueId) || clues.find((item) => item.riskEntityId === riskEntityId) || clues[0]
  const entity = clue.riskEntityId ? riskEntities.find((item) => item.id === clue.riskEntityId) : null
  const selectedProfile = entity ? riskCardHorizonProfiles[entity.id]?.[normalizedQuery.horizon] : null
  return {
    query: normalizedQuery,
    dailyDetectorStatus: { ...dailyDetectorStatus, runDate: normalizedQuery.runDate },
    clue,
    entity: entity && selectedProfile ? mergeEntityProfile(entity, selectedProfile) : entity || null,
    isMonthlyHighRiskEntity: Boolean(entity),
    detectorEvidence: entity ? mapStaticDetectorEvidence(entity, normalizedQuery) : [clue],
    probabilityTrend: entity ? probabilityTrendByEntityId[entity.id] || [] : [],
    horizonProfiles: entity ? riskCardHorizonProfiles[entity.id] || {} : {}
  }
}

export function createStaticOneshotData() {
  return {
    displayLookupStatus: DISPLAY_LOOKUP_DEMO_STATUS,
    oneshotSummary: {
      ...oneshotSummary,
      evidenceReady: false
    },
    oneshotTerminals: oneshotTerminals.map(({ reason, ...item }) => item)
  }
}

export function createStaticMonthlyReportsData() {
  return {
    displayLookupStatus: DISPLAY_LOOKUP_DEMO_STATUS,
    batchContext,
    overviewMetrics,
    dailyDetectorStatus,
    dailyReportOptions,
    monthlyReports
  }
}

export function createStaticProofCasesData() {
  return { displayLookupStatus: DISPLAY_LOOKUP_DEMO_STATUS, proofCaseHorizonTabs, proofCaseHorizonSets, proofCases }
}

export async function loadWorkbenchOptions(query = {}) {
  const normalizedQuery = normalizeWorkbenchQuery(query)
  const [manufacturers, dates] = await Promise.all([
    tryLoad(() => api().getMyManufacturers(), mapManufacturersPayload),
    tryLoad(() => api().getDailyDetectorDates(queryToApiParams(normalizedQuery)), mapDailyDetectorDatesPayload)
  ])
  if (!manufacturers && !dates) return null
  return {
    ...createStaticWorkbenchOptions(),
    manufacturerOptions: manufacturers?.manufacturerOptions || manufacturerOptions,
    dailyDetectorDateOptions: dates?.dailyDetectorDateOptions || dailyDetectorDateOptions,
    sourceLabel: manufacturers || dates ? '后端数据' : '演示数据'
  }
}

export async function loadWorkbenchData(query = {}) {
  const normalizedQuery = normalizeWorkbenchQuery(query)
  return tryLoad(() => api().getWorkbench(queryToApiParams(normalizedQuery)), (payload) => mapWorkbenchPayload(payload, normalizedQuery))
}

export async function loadRiskEntitiesData(query = {}) {
  const normalizedQuery = normalizeWorkbenchQuery(query)
  return tryLoad(() => api().getRiskEntities(queryToApiParams(normalizedQuery)), (payload) => ({
    query: normalizedQuery,
    riskEntities: (payload.entities || payload.rows || []).map((item) => mapRiskEntity(item, normalizedQuery))
  }))
}

export async function loadRiskEntityDetailData(entityId, query = {}) {
  const normalizedQuery = normalizeWorkbenchQuery(query)
  const data = await tryLoad(() => api().getRiskEntityDetail(entityId, { horizon: normalizedQuery.horizon }), (payload) => ({
    query: normalizedQuery,
    entity: mapRiskEntity(payload.entity || payload, normalizedQuery),
    horizonProfiles: mapHorizonProfiles(payload.horizon_profiles || payload.horizonProfiles || {})
  }))
  if (!data) return null
  const evidenceParams = queryToEvidenceParams(normalizedQuery, query)
  const [evidenceData, trendData] = await Promise.all([
    tryLoad(() => api().getRiskEntityDetectorEvidence(entityId, evidenceParams), mapRiskEntityDetectorEvidence),
    tryLoad(() => api().getRiskEntityProbabilityTrend(entityId, { horizon: normalizedQuery.horizon }), mapProbabilityTrendPayload)
  ])
  return {
    ...data,
    dailyDetectorStatus: { ...dailyDetectorStatus, runDate: normalizedQuery.runDate },
    isMonthlyHighRiskEntity: true,
    detectorEvidence: evidenceData?.detectorEvidence || [],
    probabilityTrend: trendData?.probabilityTrend || []
  }
}

export async function loadOneshotData() {
  return tryLoad(() => api().frontendOneshotTerminals(), mapOneshotPayload)
}

export async function loadMonthlyReportsData() {
  const data = await tryLoad(() => api().getMonthlyReports(), mapMonthlyReportsPayload)
  if (!data) return null
  return { ...data, ...(await tryLoadDailyDetectorContext()) }
}

export async function loadProofCasesData() {
  return null
}

export async function loadRuleCluesData(query = {}) {
  const context = await tryLoadDailyDetectorContext(query)
  if (!context?.dailyDetectorStatus?.ready) return null
  return context
}

export async function loadClueDetailData({ clueId, riskEntityId, query } = {}) {
  const normalizedQuery = normalizeWorkbenchQuery(query)
  if (riskEntityId) {
    const detail = await loadRiskEntityDetailData(riskEntityId, normalizedQuery)
    if (!detail) return null
    const clue = detail.detectorEvidence[0] || buildStaticRuleClues(normalizedQuery).find((item) => item.riskEntityId === riskEntityId)
    return {
      ...detail,
      clue: clue || {},
      isMonthlyHighRiskEntity: true
    }
  }

  const context = await tryLoadDailyDetectorContext(normalizedQuery)
  if (!context?.dailyDetectorStatus?.ready) return null
  const clue = context.dailyDetectorClues.find((item) => item.id === clueId)
  if (!clue) return null
  return {
    ...context,
    clue,
    entity: null,
    isMonthlyHighRiskEntity: false,
    detectorEvidence: [clue],
    probabilityTrend: []
  }
}

function api() {
  return new BackendApi(resolveBackendBaseUrl(), resolveUserId())
}

function resolveBackendBaseUrl() {
  if (typeof window === 'undefined') return undefined
  const params = new URLSearchParams(window.location.search)
  try {
    return window.__BACKEND_BASE_URL__ || params.get('backendBaseUrl') || window.localStorage.getItem('backendBaseUrl') || undefined
  } catch (error) {
    return window.__BACKEND_BASE_URL__ || params.get('backendBaseUrl') || undefined
  }
}

function resolveUserId() {
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

async function tryLoadDailyDetectorContext(query = {}) {
  const normalizedQuery = normalizeWorkbenchQuery(query)
  const params = queryToApiParams(normalizedQuery)
  const status = await tryLoad(() => api().getDailyDetectorStatus(params), normalizeDailyDetectorStatus)
  if (!status?.ready) return createStaticRuleCluesData(normalizedQuery)
  const [clues, catalog] = await Promise.all([
    tryLoadDailyDetectorClues(normalizedQuery),
    tryLoad(() => api().getDetectorCatalog(), mapDetectorCatalogPayload)
  ])
  return {
    query: normalizedQuery,
    dailyDetectorStatus: {
      ...dailyDetectorStatus,
      ...status,
      clueCount: clues?.dailyDetectorClues?.length ?? status.clueCount ?? dailyDetectorStatus.clueCount,
      attachedHighRiskCount:
        clues?.dailyDetectorClues?.filter((item) => item.isMonthlyHighRiskEntity).length ??
        status.attachedHighRiskCount ??
        dailyDetectorStatus.attachedHighRiskCount
    },
    dailyDetectorClues: clues?.dailyDetectorClues || buildStaticRuleClues(normalizedQuery),
    detectorCatalogSummary: catalog?.detectorCatalogSummary || detectorCatalogSummary,
    detectorConfigStatus
  }
}

async function tryLoadDailyDetectorClues(query) {
  const params = queryToApiParams(query)
  const dailyClues = await tryLoad(() => api().getDailyDetectorClues({ ...params, page_size: 100 }), mapDailyDetectorCluesPayload)
  if (dailyClues) return dailyClues
  return tryLoad(() => api().getDetectorClues({ ...params, page_size: 100 }), mapDailyDetectorCluesPayload)
}

function mapWorkbenchPayload(payload, fallbackQuery) {
  const payloadQuery = payload.query || {}
  const query = normalizeWorkbenchQuery({
    ...fallbackQuery,
    manufacturer_code: payloadQuery.manufacturer_code,
    report_month: payloadQuery.report_month,
    run_date: payloadQuery.run_date,
    horizon: payloadQuery.horizon,
    topN: payloadQuery.top_n,
    sortBy: payloadQuery.sort_by
  })
  const rows = (payload.rows || []).map((row) => mapWorkbenchRow(row, query))
  const detectorSummary = normalizeDetectorSummary(payload.detector_summary, query)
  return {
    displayLookupStatus: normalizeDisplayLookupStatus(payload.display_lookup_status),
    query,
    scope: mapScope(payload.scope, query),
    batchContext: {
      ...batchContext,
      reportMonth: query.reportMonth,
      primaryHorizon: formatHorizonLabel(query.horizon)
    },
    overviewMetrics: buildOverviewMetrics(rows, detectorSummary),
    dailyDetectorStatus: {
      ...dailyDetectorStatus,
      ready: true,
      sourceLabel: '后端数据',
      runDate: detectorSummary.runDate || query.runDate,
      clueCount: detectorSummary.clueCount,
      attachedHighRiskCount: detectorSummary.attachedHighRiskCount,
      scannedEntityCount: detectorSummary.scannedEntityCount
    },
    detectorSummary,
    detectorCatalogSummary,
    detectorConfigStatus,
    globalCurrentMonthHospitalDrugCount: payload.scope?.entity_count ?? rows.length,
    workbenchFillPolicy: {
      manufacturer: query.manufacturerCode,
      workbenchTargetCount: query.topN,
      globalCurrentMonthHospitalDrugCount: payload.scope?.entity_count ?? rows.length,
      fillReason: ''
    },
    workbenchDisplayRows: rows
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
  if (!payload) return DISPLAY_LOOKUP_DEMO_STATUS
  return {
    ready: payload.ready === true,
    label: payload.ready === true ? '展示名映射已接通' : '展示名映射未接通',
    message: payload.message || ''
  }
}

function normalizeDailyDetectorStatus(payload) {
  if (payload?.ready !== true) return { ...dailyDetectorStatus, ready: false }
  return {
    ready: true,
    sourceLabel: '后端数据',
    runDate: payload.run_date || dailyDetectorStatus.runDate,
    reportMonth: payload.report_month || batchContext.reportMonth,
    clueCount: payload.clue_count,
    attachedHighRiskCount: payload.attached_high_risk_count,
    scannedEntityCount: payload.scanned_entity_count,
    statusText: '今日规则巡检结果已更新',
    caveat: '日报日期对应当天巡检批次。'
  }
}

function normalizeDetectorSummary(summary = {}, query) {
  return {
    runDate: summary.run_date || query.runDate,
    clueCount: summary.clue_count ?? summary.rule_clue_count ?? dailyDetectorStatus.clueCount,
    attachedHighRiskCount: summary.attached_high_risk_count ?? summary.attached_evidence_count ?? dailyDetectorStatus.attachedHighRiskCount,
    scannedEntityCount: summary.scanned_entity_count ?? dailyDetectorStatus.scannedEntityCount
  }
}

function mapWorkbenchRow(row, query) {
  const manufacturer = firstDisplayText(row.manufacturer_display_name, row.manufacturer_name, row.manufacturer_code)
  const hospital = firstDisplayText(row.hospital_display_name, row.hospital_name, row.hospital_code)
  const drug = firstDisplayText(row.drug_display_name, row.drug_name, row.drug_code, row.drug_group)
  const involvedAmount = firstNumber(row.involved_amount, row.average_consumption_in_window, row.window_consumption)
  return {
    id: row.row_id || row.entity_id || `${hospital}-${drug}`,
    entityId: row.entity_id || '',
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
    fillSource: row.fill_source || row.source_type || '月报对象',
    sourceType: row.source_type || '月报对象',
    action: row.action || '查看详情'
  }
}

function mapRiskEntity(item, query = defaultWorkbenchQuery) {
  const profile = item.selected_horizon_profile || item
  const involvedAmount = firstNumber(profile.involved_amount, item.involved_amount, profile.average_consumption_in_window, item.average_consumption_in_window)
  return {
    id: item.entity_id || item.id,
    hospital: firstDisplayText(item.hospital_display_name, item.hospital_name, item.hospital_code, item.hospital),
    drug: firstDisplayText(item.drug_display_name, item.drug_name, item.drug_code, item.drug_group, item.drug),
    manufacturer: firstDisplayText(item.manufacturer_display_name, item.manufacturer_name, item.manufacturer_code, item.manufacturer),
    manufacturerCode: item.manufacturer_code || query.manufacturerCode,
    region: firstDisplayText(item.region_display_name, item.region, item.region_code),
    horizon: profile.horizon || item.horizon || query.horizon,
    riskLevel: profile.risk_band || item.risk_band || item.riskLevel,
    riskColor: item.risk_color || item.riskColor || 'red',
    riskProbability: firstNumber(profile.risk_probability, item.risk_probability),
    probabilityDisplay: formatPercent(firstNumber(profile.risk_probability, item.risk_probability)),
    involvedAmount,
    involvedAmountText: formatMoney(involvedAmount),
    status: item.status || item.monthly_status || '',
    monthlyStatus: item.monthly_status,
    lastPurchase: item.last_purchase_date || item.lastPurchase,
    daysSinceLast: item.days_since_last_purchase || item.daysSinceLast,
    cards: item.risk_card_count || item.cards,
    valueLevel: item.value_level || item.valueLevel,
    reason: replaceHorizonCodes(profile.reason || item.primary_reason || item.reason || ''),
    evidence: item.evidence || [],
    detectorNarrative: replaceHorizonCodes(profile.detector_narrative || item.detectorNarrative || ''),
    shapHighlights: mapShapHighlights(profile.xgboost_shap || item.shapHighlights || []),
    detectorResults: (profile.detector_results || item.detectorResults || []).map(mapDetectorResult)
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
    label: profile.label,
    riskProbability: firstNumber(profile.risk_probability),
    probabilityDisplay: formatPercent(firstNumber(profile.risk_probability)),
    involvedAmount,
    involvedAmountText: formatMoney(involvedAmount),
    reason: replaceHorizonCodes(profile.reason),
    detectorNarrative: replaceHorizonCodes(profile.detector_narrative),
    shapHighlights: mapShapHighlights(profile.xgboost_shap || []),
    detectorResults: (profile.detector_results || []).map(mapDetectorResult)
  }
}

function mapDetectorResult(item) {
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

function mapShapHighlights(items) {
  return (items || []).map((item) => ({
    feature: item.feature,
    contribution: item.contribution === undefined ? '' : formatContribution(item.contribution),
    explanation: replaceHorizonCodes(item.explanation)
  }))
}

function mapOneshotPayload(payload) {
  const hasEvidence = (payload.items || []).some((item) => item.reason || item.evidence_text)
  return {
    oneshotSummary: {
      reportMonth: payload.report_month,
      count: payload.summary?.oneshot_count ?? 0,
      highPropensityCount: payload.summary?.high_repurchase_propensity_count ?? 0,
      averageRepurchasePropensity: formatPercent(payload.summary?.average_repurchase_propensity ?? 0),
      expectedRepurchaseAmount: formatMoney(payload.summary?.expected_repurchase_amount ?? 0),
      evidenceReady: hasEvidence
    },
    oneshotTerminals: (payload.items || []).map((item) => ({
      id: item.oneshot_id,
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
    }))
  }
}

function mapMonthlyReportsPayload(payload) {
  return {
    batchContext: {
      ...batchContext,
      reportMonth: payload.batch_context?.report_month || batchContext.reportMonth
    },
    overviewMetrics: payload.overview_metrics || overviewMetrics,
    dailyDetectorStatus,
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

function mapDailyDetectorCluesPayload(payload) {
  if (payload?.ready === false) return null
  return {
    dailyDetectorClues: (payload.items || payload.rows || []).map(mapDailyDetectorClue)
  }
}

function mapDailyDetectorClue(item, index = 0) {
  const isMonthly = item.is_monthly_high_risk_entity === true || Boolean(item.risk_entity_id)
  const involvedAmount = firstNullableNumber(item.involved_amount, item.monthly_involved_amount)
  const title = item.display_name || item.title || `规则线索 #${item.display_rank || index + 1}`
  return {
    id: item.detector_clue_id || item.id || title,
    riskEntityId: item.risk_entity_id || '',
    sourceType: isMonthly ? 'monthly_high_risk' : 'daily_rule_clue',
    sourceTypeLabel: isMonthly ? '月报高风险对象' : '仅规则命中',
    isMonthlyHighRiskEntity: isMonthly,
    hospital: firstDisplayText(item.hospital_display_name, item.hospital_name, title),
    drug: firstDisplayText(item.drug_display_name, item.drug_name, item.drug_group, '规则线索'),
    manufacturer: firstDisplayText(item.manufacturer_display_name, item.manufacturer_code),
    region: firstDisplayText(item.region_display_name, item.region_code),
    detectorName: item.detector_name || item.detector_id,
    detectorFamily: item.detector_family || '规则巡检',
    detectorId: item.detector_id || '',
    detectorRunId: item.detector_run_id || '',
    detectorScore: item.detector_score,
    detectorScoreText: formatRuleScore(item.detector_score),
    detectorScoreLabel: '规则巡检分',
    detectorLevel: item.detector_level || item.confidence || '-',
    hitFlag: item.hit_flag,
    rootCauseLabel: item.root_cause_label || '规则线索命中',
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
    actionText: isMonthly ? '查看月报风险详情' : '查看规则线索详情'
  }
}

function mapDetectorCatalogPayload(payload) {
  if (payload?.ready === false) return null
  return {
    detectorCatalogSummary: (payload.items || []).map((item) => ({
      id: item.detector_id,
      name: item.detector_name,
      family: item.detector_family,
      status: item.status,
      statusLabel: detectorStatusLabel(item.status),
      caveat: item.caveat || ''
    }))
  }
}

function mapRiskEntityDetectorEvidence(payload) {
  return {
    detectorEvidence: (payload.items || []).map((item, index) => ({
      ...mapDailyDetectorClue(
        {
          detector_clue_id: `${item.risk_entity_id}-${item.detector_id}-${index}`,
          detector_run_id: item.detector_run_id,
          run_date: item.run_date,
          detector_id: item.detector_id,
          detector_name: item.detector_name,
          detector_family: item.detector_family,
          detector_score: item.detector_score,
          detector_level: item.confidence,
          hit_flag: true,
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

function mapStaticDetectorEvidence(entity, query) {
  return (entity.detectorResults || []).map((item) => ({
    id: `${entity.id}-${item.id}`,
    riskEntityId: entity.id,
    sourceType: 'monthly_high_risk',
    sourceTypeLabel: '月报高风险对象',
    isMonthlyHighRiskEntity: true,
    hospital: entity.hospital,
    drug: entity.drug,
    manufacturer: entity.manufacturer,
    region: entity.region,
    detectorName: item.name,
    detectorFamily: item.family || '规则巡检',
    detectorId: item.id,
    detectorRunId: `${query.runDate}-${item.id}`,
    detectorScore: item.detectorScore ?? item.score,
    detectorScoreText: formatRuleScore(item.detectorScore ?? item.score),
    detectorScoreLabel: '规则巡检分',
    detectorLevel: item.signal,
    hitFlag: true,
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
    fillSource: '月报对象',
    sourceType: '月报对象',
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
    detectorNarrative: profile.detectorNarrative,
    shapHighlights: profile.shapHighlights,
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
  return {
    manufacturerCount: payload.manufacturer_count ?? items.length,
    manufacturerOptions: items.map((item) => ({
      code: item.manufacturer_code || item.code || item.id,
      name: item.manufacturer_display_name || item.manufacturer_name || item.name || item.manufacturer_code || item.code
    }))
  }
}

function mapDailyDetectorDatesPayload(payload) {
  const items = payload.items || payload.dates || []
  return {
    dailyDetectorDateOptions: items.map((item) => ({
      runDate: item.run_date || item.date || item,
      label: item.label || item.run_date || item.date || item
    }))
  }
}

function buildOverviewMetrics(rows, detectorSummary) {
  return [
    { label: '今日重点风险对象', value: String(rows.length), tone: 'danger' },
    { label: '今日巡检线索', value: String(detectorSummary.clueCount ?? '-'), tone: 'warning' },
    { label: '已附着证据', value: String(detectorSummary.attachedHighRiskCount ?? '-'), tone: 'success' },
    { label: '巡检对象', value: String(detectorSummary.scannedEntityCount ?? '-'), tone: 'info' }
  ]
}

function manufacturerName(code) {
  return manufacturerOptions.find((item) => item.code === code)?.name || code
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

function formatRuleScore(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-'
  const score = Number(value)
  return score <= 1 ? String(Math.round(score * 100)) : String(Math.round(score))
}

function detectorStatusLabel(status) {
  const labels = {
    implemented: '已启用规则',
    interface_only: '接口预留',
    experimental: '实验规则',
    reserved: '保留能力'
  }
  return labels[status] || status || '规则巡检'
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

function formatContribution(value) {
  return `${value >= 0 ? '+' : ''}${Number(value).toFixed(2)}`
}
