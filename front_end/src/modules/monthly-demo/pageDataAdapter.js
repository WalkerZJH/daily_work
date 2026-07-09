import { BackendApi } from '../../services/backendApi'
import {
  batchContext,
  dailyReportOptions,
  dailyDetectorClues,
  dailyDetectorStatus,
  detectorCatalogSummary,
  detectorConfigStatus,
  globalCurrentMonthHospitalDrugCount,
  modelMetrics,
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
  workbenchDisplayRows,
  workbenchFillPolicy
} from './demoData'

const DISPLAY_LOOKUP_DEMO_STATUS = {
  ready: false,
  label: '演示数据',
  message: '展示名映射未接通'
}

export function createStaticWorkbenchData() {
  return {
    displayLookupStatus: DISPLAY_LOOKUP_DEMO_STATUS,
    batchContext,
    overviewMetrics,
    dailyDetectorStatus,
    detectorCatalogSummary,
    detectorConfigStatus,
    globalCurrentMonthHospitalDrugCount,
    workbenchFillPolicy,
    workbenchDisplayRows
  }
}

export function createStaticRiskEntitiesData() {
  return {
    displayLookupStatus: DISPLAY_LOOKUP_DEMO_STATUS,
    dailyDetectorStatus,
    detectorCatalogSummary,
    detectorConfigStatus,
    dailyDetectorClues
  }
}

export function createStaticRiskEntityDetailData(entityId) {
  const entity = riskEntities.find((item) => item.id === entityId) || riskEntities[0]
  const clue = dailyDetectorClues.find((item) => item.riskEntityId === entity.id) || dailyDetectorClues[0]
  return {
    displayLookupStatus: DISPLAY_LOOKUP_DEMO_STATUS,
    dailyDetectorStatus,
    entity,
    clue,
    isMonthlyHighRiskEntity: true,
    detectorEvidence: mapStaticDetectorEvidence(entity),
    probabilityTrend: probabilityTrendByEntityId[entity.id] || [],
    horizonProfiles: riskCardHorizonProfiles[entity.id] || {}
  }
}

export function createStaticRuleCluesData() {
  return {
    dailyDetectorStatus,
    detectorCatalogSummary,
    detectorConfigStatus,
    dailyDetectorClues
  }
}

export function createStaticClueDetailData({ clueId, riskEntityId } = {}) {
  const clue =
    dailyDetectorClues.find((item) => item.id === clueId) ||
    dailyDetectorClues.find((item) => item.riskEntityId === riskEntityId) ||
    dailyDetectorClues[0]
  const entity = clue.riskEntityId ? riskEntities.find((item) => item.id === clue.riskEntityId) : null
  return {
    dailyDetectorStatus,
    clue,
    entity: entity || null,
    isMonthlyHighRiskEntity: Boolean(entity),
    detectorEvidence: entity ? mapStaticDetectorEvidence(entity) : [clue],
    probabilityTrend: entity ? probabilityTrendByEntityId[entity.id] || [] : [],
    horizonProfiles: entity ? riskCardHorizonProfiles[entity.id] || {} : {}
  }
}

export function createStaticOneshotData() {
  return { displayLookupStatus: DISPLAY_LOOKUP_DEMO_STATUS, oneshotSummary, oneshotTerminals }
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

export async function loadWorkbenchData() {
  const data = await tryLoadWhenDisplayLookupReady(() => api().getWorkbench(), mapWorkbenchPayload)
  if (!data) return null
  return { ...data, ...(await tryLoadDailyDetectorContext()) }
}

export async function loadRiskEntitiesData() {
  return tryLoadWhenDisplayLookupReady(() => api().getRiskEntities(), (payload) => ({
    riskEntities: payload.entities.map(mapRiskEntity)
  }))
}

export async function loadRiskEntityDetailData(entityId) {
  const data = await tryLoadWhenDisplayLookupReady(() => api().getRiskEntityDetail(entityId), (payload) => ({
    entity: mapRiskEntity(payload.entity),
    horizonProfiles: Object.fromEntries(
      Object.entries(payload.horizon_profiles || {}).map(([horizon, profile]) => [horizon, mapHorizonProfile(profile)])
    )
  }))
  if (!data) return null
  const [evidenceData, trendData] = await Promise.all([
    tryLoad(() => api().getRiskEntityDetectorEvidence(entityId), mapRiskEntityDetectorEvidence),
    tryLoad(() => api().getRiskEntityProbabilityTrend(entityId), mapProbabilityTrendPayload)
  ])
  return {
    ...data,
    dailyDetectorStatus,
    isMonthlyHighRiskEntity: true,
    detectorEvidence: evidenceData?.detectorEvidence || [],
    probabilityTrend: trendData?.probabilityTrend || []
  }
}

export async function loadOneshotData() {
  return tryLoadWhenDisplayLookupReady(() => api().frontendOneshotTerminals(), mapOneshotPayload)
}

export async function loadMonthlyReportsData() {
  const data = await tryLoadWhenDisplayLookupReady(() => api().getMonthlyReports(), mapMonthlyReportsPayload)
  if (!data) return null
  return { ...data, ...(await tryLoadDailyDetectorContext()) }
}

export async function loadProofCasesData() {
  await resolveDisplayLookupStatus()
  return null
}

export async function loadRuleCluesData() {
  const context = await tryLoadDailyDetectorContext()
  if (!context?.dailyDetectorStatus?.ready) return null
  return context
}

export async function loadClueDetailData({ clueId, riskEntityId } = {}) {
  const context = await tryLoadDailyDetectorContext()
  if (!context?.dailyDetectorStatus?.ready) return null
  const clue =
    context.dailyDetectorClues.find((item) => item.id === clueId) ||
    context.dailyDetectorClues.find((item) => item.riskEntityId === riskEntityId)
  if (!clue) return null
  if (!clue.riskEntityId) {
    return {
      ...context,
      clue,
      entity: null,
      isMonthlyHighRiskEntity: false,
      detectorEvidence: [clue],
      probabilityTrend: []
    }
  }
  const detail = await loadRiskEntityDetailData(clue.riskEntityId)
  if (!detail) return null
  return {
    ...context,
    ...detail,
    clue,
    isMonthlyHighRiskEntity: true
  }
}

function api() {
  const baseUrl = resolveBackendBaseUrl()
  return new BackendApi(baseUrl)
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

async function tryLoad(loader, mapper) {
  try {
    return mapper(await loader())
  } catch (error) {
    return null
  }
}

async function tryLoadWhenDisplayLookupReady(loader, mapper) {
  const displayLookupStatus = await resolveDisplayLookupStatus()
  if (!displayLookupStatus.ready) return null
  const data = await tryLoad(loader, mapper)
  return data ? { ...data, displayLookupStatus } : null
}

async function tryLoadDailyDetectorContext() {
  const status = await tryLoad(() => api().getDailyDetectorStatus(), normalizeDailyDetectorStatus)
  if (!status?.ready) return createStaticRuleCluesData()
  const [clues, catalog, config] = await Promise.all([
    tryLoadDailyDetectorClues(),
    tryLoad(() => api().getDetectorCatalog(), mapDetectorCatalogPayload),
    tryLoad(() => api().getDetectorConfigStatus(), mapDetectorConfigStatus)
  ])
  return {
    dailyDetectorStatus: {
      ...dailyDetectorStatus,
      ...status,
      clueCount: clues?.dailyDetectorClues?.length ?? status.clueCount ?? dailyDetectorStatus.clueCount,
      attachedHighRiskCount:
        clues?.dailyDetectorClues?.filter((item) => item.isMonthlyHighRiskEntity).length ??
        status.attachedHighRiskCount ??
        dailyDetectorStatus.attachedHighRiskCount
    },
    dailyDetectorClues: clues?.dailyDetectorClues || dailyDetectorClues,
    detectorCatalogSummary: catalog?.detectorCatalogSummary || detectorCatalogSummary,
    detectorConfigStatus: config || detectorConfigStatus
  }
}

async function tryLoadDailyDetectorClues() {
  const dailyClues = await tryLoad(() => api().getDailyDetectorClues({ page_size: 100 }), mapDailyDetectorCluesPayload)
  if (dailyClues) return dailyClues
  return tryLoad(() => api().getDetectorClues({ page_size: 100 }), mapDailyDetectorCluesPayload)
}

async function resolveDisplayLookupStatus() {
  try {
    return normalizeDisplayLookupStatus(await api().displayLookupStatus())
  } catch (error) {
    return DISPLAY_LOOKUP_DEMO_STATUS
  }
}

function normalizeDisplayLookupStatus(payload) {
  if (payload?.ready !== true) return DISPLAY_LOOKUP_DEMO_STATUS
  return {
    ready: true,
    label: '展示名映射已就绪',
    message: payload.message || '后端展示名映射可用'
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
    caveat: '今日巡检结果每天变化，月报批次结论保持稳定。'
  }
}

function mapWorkbenchPayload(payload) {
  return {
    batchContext: mapBatchContext(payload.batch_context),
    overviewMetrics: payload.overview_metrics || overviewMetrics,
    modelMetrics: mapModelMetrics(payload.model_metrics || modelMetrics),
    globalCurrentMonthHospitalDrugCount: payload.fill_policy.global_current_month_hospital_drug_count,
    workbenchFillPolicy: mapFillPolicy(payload.fill_policy),
    workbenchDisplayRows: payload.rows.map(mapWorkbenchRow)
  }
}

function mapBatchContext(context) {
  return {
    reportMonth: context.report_month,
    scoreAsOfDate: context.score_as_of_date,
    dataWatermarkAt: context.data_watermark_at,
    scoreBatchId: context.score_batch_id,
    resultBatchId: context.result_batch_id,
    primaryHorizon: `${formatHorizonLabel(context.primary_horizon)} ${context.primary_horizon_label}`,
    scoreFormula: '风险概率 × 预测窗口内平均消费金额'
  }
}

function mapFillPolicy(policy) {
  return {
    manufacturer: policy.manufacturer_code,
    workbenchTargetCount: policy.workbench_target_count,
    globalCurrentMonthHospitalDrugCount: policy.global_current_month_hospital_drug_count,
    fillReason: policy.fill_reason
  }
}

function mapWorkbenchRow(row) {
  const manufacturer = firstDisplayText(row.manufacturer_display_name, row.manufacturer_code)
  const hospital = firstDisplayText(row.hospital_display_name, row.hospital_name, row.hospital_code)
  const drug = firstDisplayText(row.drug_display_name, row.drug_name, row.drug_code, row.drug_group)
  const lossValue = firstNumber(row.loss_value, row.monthly_loss_value, row.business_score, row.risk_probability * row.average_consumption_in_window)
  return {
    id: row.row_id,
    entityId: row.entity_id || '',
    manufacturer,
    hospital,
    drug,
    hospitalDrugKey: `${hospital} × ${drug}`,
    region: firstDisplayText(row.region_display_name, row.region, row.region_code),
    riskProbability: row.risk_probability,
    probabilityDisplay: formatPercent(row.risk_probability),
    averageConsumptionInWindow: row.average_consumption_in_window,
    averageConsumptionText: formatMoney(row.average_consumption_in_window),
    lossValue,
    lossValueText: formatMoney(lossValue),
    fillSource: row.fill_source,
    sourceType: row.source_type,
    action: row.action
  }
}

function mapRiskEntity(item) {
  const lossValue = firstNumber(item.loss_value, item.monthly_loss_value, item.business_score, item.risk_probability * item.average_consumption_in_window)
  return {
    id: item.entity_id,
    hospital: firstDisplayText(item.hospital_display_name, item.hospital_name, item.hospital_code),
    drug: firstDisplayText(item.drug_display_name, item.drug_name, item.drug_code, item.drug_group),
    manufacturer: firstDisplayText(item.manufacturer_display_name, item.manufacturer_code),
    region: firstDisplayText(item.region_display_name, item.region, item.region_code),
    horizon: item.horizon,
    riskLevel: item.risk_band,
    riskColor: item.risk_color,
    riskProbability: item.risk_probability,
    probabilityDisplay: formatPercent(item.risk_probability),
    averageConsumptionInWindow: item.average_consumption_in_window,
    averageConsumptionText: formatMoney(item.average_consumption_in_window),
    lossValue,
    lossValueText: formatMoney(lossValue),
    status: item.status,
    monthlyStatus: item.monthly_status,
    lastPurchase: item.last_purchase_date,
    daysSinceLast: item.days_since_last_purchase,
    cards: item.risk_card_count,
    valueLevel: item.value_level,
    reason: replaceHorizonCodes(item.primary_reason),
    evidence: [],
    detectorNarrative: '',
    shapHighlights: [],
    detectorResults: []
  }
}

function mapHorizonProfile(profile) {
  const lossValue = firstNumber(profile.loss_value, profile.monthly_loss_value, profile.business_score, profile.risk_probability * profile.average_consumption_in_window)
  return {
    horizon: profile.horizon,
    horizonLabel: formatHorizonLabel(profile.horizon),
    label: profile.label,
    riskProbability: profile.risk_probability,
    probabilityDisplay: formatPercent(profile.risk_probability),
    averageConsumptionInWindow: profile.average_consumption_in_window,
    averageConsumptionText: formatMoney(profile.average_consumption_in_window),
    lossValue,
    lossValueText: formatMoney(lossValue),
    reason: replaceHorizonCodes(profile.reason),
    detectorNarrative: replaceHorizonCodes(profile.detector_narrative),
    shapHighlights: profile.xgboost_shap.map((item) => ({
      feature: item.feature,
      contribution: formatContribution(item.contribution),
      explanation: replaceHorizonCodes(item.explanation)
    })),
    detectorResults: profile.detector_results.map((item) => ({
      id: item.detector_id,
      name: item.detector_name,
      detectorScore: item.detector_score ?? item.score,
      detectorScoreText: formatRuleScore(item.detector_score ?? item.score),
      detectorScoreLabel: '规则巡检分',
      signal: item.signal,
      status: item.status,
      evidence: replaceHorizonCodes(item.evidence),
      action: item.action
    }))
  }
}

function mapOneshotPayload(payload) {
  return {
    oneshotSummary: {
      reportMonth: payload.report_month,
      count: payload.summary.oneshot_count,
      highPropensityCount: payload.summary.high_repurchase_propensity_count,
      averageRepurchasePropensity: formatPercent(payload.summary.average_repurchase_propensity),
      expectedRepurchaseAmount: formatMoney(payload.summary.expected_repurchase_amount)
    },
    oneshotTerminals: payload.items.map((item) => ({
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
      reason: replaceHorizonCodes(item.reason)
    }))
  }
}

function mapMonthlyReportsPayload(payload) {
  return {
    batchContext: mapBatchContext(payload.batch_context),
    overviewMetrics: payload.overview_metrics || overviewMetrics,
    dailyDetectorStatus,
    dailyReportOptions: payload.daily_report_options.map((item) => ({
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
    monthlyReports: payload.monthly_reports.map((item) => ({
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
  if (payload?.ready !== true) return null
  return {
    dailyDetectorClues: (payload.items || []).map(mapDailyDetectorClue)
  }
}

function mapDailyDetectorClue(item, index = 0) {
  const isMonthly = item.is_monthly_high_risk_entity === true
  const lossValue = firstNumber(item.loss_value, item.monthly_loss_value)
  const title = item.display_name || item.title || `规则线索 #${item.display_rank || index + 1}`
  return {
    id: item.detector_clue_id,
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
    detectorScore: item.detector_score,
    detectorScoreText: formatRuleScore(item.detector_score),
    detectorScoreLabel: '规则巡检分',
    detectorLevel: item.detector_level || '-',
    hitFlag: item.hit_flag,
    rootCauseLabel: item.root_cause_label || '规则线索命中',
    evidenceText: item.evidence_text || item.caveat || '',
    detectorRunDate: item.run_date,
    monthlyRiskProbability: item.monthly_risk_probability,
    monthlyRiskProbabilityText: item.monthly_risk_probability === null || item.monthly_risk_probability === undefined ? '-' : formatPercent(item.monthly_risk_probability),
    lossValue,
    lossValueText: lossValue === null || lossValue === undefined ? '-' : formatMoney(lossValue),
    actionText: isMonthly ? '查看月报风险详情' : '查看规则线索详情'
  }
}

function mapDetectorCatalogPayload(payload) {
  if (payload?.ready !== true) return null
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

function mapDetectorConfigStatus(payload) {
  return {
    effectiveConfigVersion: payload?.effective_config_version || detectorConfigStatus.effectiveConfigVersion,
    latestRunDate: payload?.latest_run_date || detectorConfigStatus.latestRunDate,
    pendingConfigExists: Boolean(payload?.pending_config_exists),
    nextRunRequired: Boolean(payload?.next_run_required),
    message: '规则参数调整后，将在下一次 detector 巡检运行后生效。'
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
          detector_family: item.detector_family,
          detector_score: item.detector_score,
          detector_level: item.confidence,
          hit_flag: true,
          root_cause_label: item.root_cause_label,
          evidence_text: item.evidence_text,
          is_monthly_high_risk_entity: true,
          risk_entity_id: item.risk_entity_id,
          monthly_risk_probability: payload.monthly_risk_probability,
          monthly_loss_value: payload.monthly_loss_value,
          caveat: item.caveat
        },
        index
      ),
      detectorName: payload.catalog_by_detector_id?.[item.detector_id]?.detector_name || item.detector_id
    }))
  }
}

function mapProbabilityTrendPayload(payload) {
  return {
    probabilityTrend: (payload.items || payload.trend || []).map((item) => {
      const lossValue = firstNumber(item.loss_value, item.monthly_loss_value)
      return {
        reportMonth: item.report_month,
        riskProbability: item.risk_probability,
        riskProbabilityText: formatPercent(item.risk_probability),
        lossValue,
        lossValueText: lossValue === null || lossValue === undefined ? '-' : formatMoney(lossValue)
      }
    })
  }
}

function mapStaticDetectorEvidence(entity) {
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
    detectorFamily: '规则巡检',
    detectorScore: item.detectorScore ?? item.score,
    detectorScoreText: formatRuleScore(item.detectorScore ?? item.score),
    detectorScoreLabel: '规则巡检分',
    detectorLevel: item.signal,
    hitFlag: true,
    rootCauseLabel: item.status,
    evidenceText: item.evidence,
    detectorRunDate: dailyDetectorStatus.runDate,
    monthlyRiskProbability: entity.riskProbability,
    monthlyRiskProbabilityText: entity.probabilityDisplay,
    lossValue: entity.lossValue ?? entity.businessScore,
    lossValueText: entity.lossValueText ?? entity.businessScoreText,
    actionText: item.action
  }))
}

function mapModelMetrics(items) {
  return (items || []).map((item) => {
    if (item.auc !== undefined && item.topK !== undefined) return item
    const firstTopK = (item.topk_recall || [])[0] || {}
    const listShare = firstTopK.actual_k_percent !== undefined ? formatMetricPercent(firstTopK.actual_k_percent) : '-'
    const recall = firstTopK.recall !== undefined ? formatMetricPercent(firstTopK.recall) : '-'
    const precision =
      firstTopK.true_positive_count !== undefined && firstTopK.selected_count
        ? formatMetricPercent(firstTopK.true_positive_count / firstTopK.selected_count)
        : '-'
    const positiveRate =
      item.positive_count !== undefined && item.sample_count ? item.positive_count / item.sample_count : undefined
    const lift =
      positiveRate && firstTopK.true_positive_count !== undefined && firstTopK.selected_count
        ? `${(firstTopK.true_positive_count / firstTopK.selected_count / positiveRate).toFixed(2)}倍`
        : '-'
    return {
      id: item.model_id,
      name: replaceHorizonCodes(item.model_name),
      role: modelRoleLabel(item.model_role),
      horizon: formatHorizonLabel(item.horizon),
      window: replaceHorizonCodes(item.evaluation_window),
      auc: formatMetric(item.auc),
      prauc: formatMetric(item.prauc),
      praucLift: item.pr_auc_lift !== undefined ? formatMetric(item.pr_auc_lift) : formatMetric(item.prauc_lift),
      ece: formatMetric(item.ece),
      brier: formatMetric(item.brier),
      topK: firstTopK.selected_count
        ? `前${listShare}名单：召回${recall}，命中精度${precision}，提升${lift}`
        : '复购倾向分层指标'
    }
  })
}

function modelRoleLabel(role) {
  const labels = {
    backbone_risk_probability: '风险概率识别',
    oneshot_repurchase_propensity: '新进终端复购倾向',
    detector_evidence_ranker: '证据排序',
    detector_evidence: '证据识别'
  }
  return labels[role] || role || '模型指标'
}

function formatHorizonLabel(value) {
  const labels = { H3: '3月', H6: '6月', H12: '12月' }
  return labels[value] || replaceHorizonCodes(value || '-')
}

function replaceHorizonCodes(value) {
  if (value === null || value === undefined) return value
  return String(value)
    .replaceAll('H12', '12月')
    .replaceAll('H6', '6月')
    .replaceAll('H3', '3月')
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

function formatPercent(value) {
  return `${Math.round(value * 100)}%`
}

function formatMetric(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-'
  return Number(value).toFixed(3)
}

function formatMetricPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-'
  return `${(Number(value) * 100).toFixed(2)}%`
}

function formatMoney(value) {
  return `¥${Math.round(value).toLocaleString('zh-CN')}`
}

function formatContribution(value) {
  return `${value >= 0 ? '+' : ''}${Number(value).toFixed(2)}`
}
