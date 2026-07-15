import {
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

export const demoPageLoaders = {
  workbenchOptions: createStaticWorkbenchOptions,
  reportContext: createDemoReportContext,
  workbenchData: createStaticWorkbenchData,
  ruleCluesData: createStaticRuleCluesData,
  clueDetailData: createStaticClueDetailData,
  oneshotData: createStaticOneshotData,
  monthlyReportsData: createStaticMonthlyReportsData,
  proofCasesData: createStaticProofCasesData
}

export function createStaticWorkbenchOptions() {
  return {
    manufacturerOptions,
    defaultManufacturerCode: manufacturerOptions[0]?.code || defaultWorkbenchQuery.manufacturerCode,
    dailyDetectorDateOptions,
    reportMonthOptions: [defaultWorkbenchQuery.reportMonth],
    horizonOptions,
    topNOptions,
    sortOptions,
    sourceLabel: '演示模式'
  }
}

export function createDemoReportContext(query = {}) {
  const normalized = normalizeDemoQuery(query)
  return {
    ready: true,
    observationDate: normalized.observationDate,
    probabilityReportMonth: normalized.probabilityReportMonth,
    detectorRunDate: normalized.detectorRunDate,
    probabilityBatchAvailable: true,
    detectorRunAvailable: true,
    contextStatus: 'ready',
    manualSelectionRequired: false,
    availableReportMonths: [normalized.probabilityReportMonth],
    availableDetectorRunDates: dailyDetectorDateOptions.map((item) => item.runDate),
    effectiveHorizon: normalized.horizon,
    requestedReportMonth: normalized.reportMonth,
    requestedRunDate: normalized.runDate,
    requestedHorizon: normalized.horizon,
    effectiveReportMonth: normalized.probabilityReportMonth,
    effectiveRunDate: normalized.observationDate,
    fallbackUsed: false,
    title: '演示模式',
    message: '',
    displayTitle: '演示模式',
    displayLines: [
      `观察日期：${normalized.observationDate}`,
      `概率基准月：${normalized.probabilityReportMonth}`,
      `规则巡检日期：${normalized.detectorRunDate}`
    ]
  }
}

export function createStaticWorkbenchData(query = {}) {
  const normalized = normalizeDemoQuery(query)
  const rows = buildStaticWorkbenchRows(normalized)
  const topRuleClues = buildStaticRuleClues(normalized).slice(0, Math.min(normalized.topN, 20))
  const detectorSummary = {
    ready: true,
    runDate: normalized.detectorRunDate,
    clueCount: dailyDetectorStatus.clueCount,
    attachedHighRiskCount: dailyDetectorStatus.attachedHighRiskCount,
    scannedEntityCount: dailyDetectorStatus.scannedEntityCount,
    highestRuleScore: highestRuleScore(topRuleClues),
    priorityRiskEntityCount: rows.length
  }
  return {
    ready: true,
    reportContext: createDemoReportContext(normalized),
    displayLookupStatus: { ready: false, label: '演示模式', message: '' },
    query: normalized,
    scope: {
      manufacturerCode: normalized.manufacturerCode,
      manufacturerName: manufacturerName(normalized.manufacturerCode),
      reportMonth: normalized.probabilityReportMonth
    },
    overviewMetrics: buildTodayMetrics(rows, detectorSummary, normalized),
    dailyDetectorStatus: {
      ...dailyDetectorStatus,
      ready: true,
      sourceLabel: '演示模式',
      runDate: normalized.detectorRunDate
    },
    detectorSummary,
    workbenchDisplayRows: rows,
    topRuleClues,
    emptyTitle: '',
    emptyMessage: ''
  }
}

export function createStaticRuleCluesData(query = {}) {
  const normalized = normalizeDemoQuery(query)
  const clues = buildStaticRuleClues(normalized)
  return {
    ready: true,
    reportContext: createDemoReportContext(normalized),
    query: normalized,
    dailyDetectorStatus: { ...dailyDetectorStatus, ready: true, sourceLabel: '演示模式', runDate: normalized.detectorRunDate },
    dailyDetectorClues: clues,
    total: clues.length,
    emptyTitle: '',
    emptyMessage: ''
  }
}

export function createStaticClueDetailData({ clueId, riskEntityId, query } = {}) {
  const normalized = normalizeDemoQuery(query)
  const clues = buildStaticRuleClues(normalized)
  const clue = clues.find((item) => item.id === clueId) || clues.find((item) => item.riskEntityId === riskEntityId) || clues[0]
  const entity = clue?.riskEntityId ? riskEntities.find((item) => item.id === clue.riskEntityId) : null
  const selectedProfile = entity ? riskCardHorizonProfiles[entity.id]?.[normalized.horizon] : null
  return {
    ready: true,
    reportContext: createDemoReportContext(normalized),
    query: normalized,
    clue: clue || {},
    entity: entity && selectedProfile ? mergeEntityProfile(entity, selectedProfile) : entity || null,
    isMonthlyHighRiskEntity: Boolean(entity),
    detectorEvidence: entity ? mapStaticRuleEvidence(entity, normalized) : clue ? [clue] : [],
    probabilityTrend: entity ? probabilityTrendByEntityId[entity.id] || [] : [],
    horizonProfiles: entity ? riskCardHorizonProfiles[entity.id] || {} : {},
    emptyTitle: '',
    emptyMessage: ''
  }
}

export function createStaticOneshotData() {
  return {
    ready: true,
    status: oneshotTerminals.length ? 'ready' : 'empty',
    displayLookupStatus: { ready: false, label: '演示模式', message: '' },
    oneshotSummary: { ...oneshotSummary },
    pagination: { page: 1, pageSize: 20, total: oneshotTerminals.length, totalPages: oneshotTerminals.length ? 1 : 0 },
    sortBy: 'first_purchase_date',
    sortOrder: 'desc',
    oneshotTerminals: [...oneshotTerminals],
    errorMessage: '',
    emptyTitle: '',
    emptyMessage: ''
  }
}

export function createStaticMonthlyReportsData(query = {}) {
  return {
    ready: true,
    displayLookupStatus: { ready: false, label: '演示模式', message: '' },
    reportContext: createDemoReportContext(query),
    runtimeProfile: null,
    overviewMetrics,
    dailyDetectorStatus,
    dailyReportOptions,
    monthlyReports,
    emptyTitle: '',
    emptyMessage: ''
  }
}

export function createStaticProofCasesData() {
  return {
    ready: true,
    displayLookupStatus: { ready: false, label: '演示模式', message: '' },
    proofCaseHorizonTabs,
    proofCaseHorizonSets,
    proofCases,
    emptyTitle: '',
    emptyMessage: ''
  }
}

function normalizeDemoQuery(query = {}) {
  const observationDate = query.observationDate || query.observation_date || query.runDate || query.run_date || defaultWorkbenchQuery.runDate
  const probabilityReportMonth = query.probabilityReportMonth || query.probability_report_month || query.reportMonth || query.report_month || defaultWorkbenchQuery.reportMonth
  const detectorRunDate = query.detectorRunDate || query.detector_run_date || observationDate
  return {
    ...defaultWorkbenchQuery,
    ...query,
    manufacturerCode: query.manufacturerCode || query.manufacturer_code || defaultWorkbenchQuery.manufacturerCode,
    observationDate,
    reportMonth: probabilityReportMonth,
    runDate: observationDate,
    probabilityReportMonth,
    detectorRunDate,
    horizon: horizonOptions.some((item) => item.id === query.horizon) ? query.horizon : defaultWorkbenchQuery.horizon,
    topN: topNOptions.includes(Number(query.topN ?? query.top_n)) ? Number(query.topN ?? query.top_n) : defaultWorkbenchQuery.topN,
    sortBy: sortOptions.some((item) => item.id === (query.sortBy || query.sort_by)) ? query.sortBy || query.sort_by : defaultWorkbenchQuery.sortBy,
    demoMode: true
  }
}

function buildStaticWorkbenchRows(query) {
  const rows = workbenchDisplayRows.map((row) => {
    if (!row.entityId) return applyStaticFallbackHorizon(row, query.horizon)
    const entity = riskEntities.find((item) => item.id === row.entityId)
    const profile = entity ? riskCardHorizonProfiles[entity.id]?.[query.horizon] : null
    return profile && entity ? mapStaticEntityRow(entity, profile) : row
  })

  const sorted = rows.sort((a, b) => {
    if (query.sortBy === 'involved_amount' || query.sortBy === 'loss_value') return b.involvedAmount - a.involvedAmount
    return b.riskProbability - a.riskProbability
  })
  return sorted.slice(0, query.topN)
}

function buildStaticRuleClues(query) {
  return dailyDetectorClues.map((item) => {
    if (!item.riskEntityId) return { ...item, detectorRunDate: query.detectorRunDate }
    const entity = riskEntities.find((riskEntity) => riskEntity.id === item.riskEntityId)
    const profile = entity ? riskCardHorizonProfiles[entity.id]?.[query.horizon] : null
    return {
      ...item,
      sourceTypeLabel: item.isMonthlyHighRiskEntity ? '月报高风险' : '仅规则命中',
      detectorRunDate: query.detectorRunDate,
      monthlyRiskProbability: profile?.riskProbability ?? item.monthlyRiskProbability,
      monthlyRiskProbabilityText: profile?.probabilityDisplay ?? item.monthlyRiskProbabilityText,
      involvedAmount: profile?.involvedAmount ?? item.involvedAmount,
      involvedAmountText: profile?.involvedAmountText ?? item.involvedAmountText,
      lossValueText: profile?.involvedAmountText ?? item.involvedAmountText
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
    lossValueText: profile.involvedAmountText,
    riskBand: profile.riskBand || '',
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
    involvedAmountText: formatMoney(involvedAmount),
    lossValueText: formatMoney(involvedAmount)
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
    lossValueText: profile.involvedAmountText,
    reason: profile.reason,
    detectorResults: profile.detectorResults
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
    detectorRunId: `${query.detectorRunDate}-${item.id}`,
    detectorScore: item.detectorScore ?? item.score,
    detectorScoreText: formatRuleScore(item.detectorScore ?? item.score),
    detectorScoreLabel: '规则巡检分',
    detectorLevel: item.signal,
    rootCauseLabel: item.status,
    evidenceText: item.evidence,
    detectorRunDate: query.detectorRunDate,
    monthlyRiskProbability: entity.riskProbability,
    monthlyRiskProbabilityText: entity.probabilityDisplay,
    involvedAmount: entity.involvedAmount,
    involvedAmountText: entity.involvedAmountText,
    lossValueText: entity.involvedAmountText,
    actionText: item.action
  }))
}

function buildTodayMetrics(rows, detectorSummary, query) {
  return [
    { label: '当前生产企业', value: manufacturerName(query.manufacturerCode), tone: 'info' },
    { label: '观察日期', value: query.observationDate || '-', tone: 'neutral' },
    { label: '概率基准月', value: query.probabilityReportMonth || '-', tone: 'warning' },
    { label: '规则巡检日期', value: query.detectorRunDate || '-', tone: 'success' },
    { label: '当前预测窗口', value: formatHorizonLabel(query.horizon), tone: 'warning' },
    { label: '今日线索总数', value: String(detectorSummary.clueCount ?? 0), tone: 'success' },
    { label: '最高规则巡检分', value: detectorSummary.highestRuleScore === null || detectorSummary.highestRuleScore === undefined ? '-' : String(detectorSummary.highestRuleScore), tone: 'danger' },
    { label: '重点风险对象数量', value: String(detectorSummary.priorityRiskEntityCount ?? rows.length), tone: 'info' }
  ]
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

function formatRuleScore(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-'
  const score = Number(value)
  return score <= 1 ? String(Math.round(score * 100)) : String(Math.round(score))
}

function formatHorizonLabel(value) {
  const labels = { H3: '3月', H6: '6月', H12: '12月' }
  return labels[value] || value || '-'
}

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-'
  return `${Math.round(Number(value) * 100)}%`
}

function formatMoney(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-'
  return `¥${Math.round(Number(value)).toLocaleString('zh-CN')}`
}
