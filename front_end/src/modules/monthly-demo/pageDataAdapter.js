import { BackendApi } from '../../services/backendApi'
import {
  batchContext,
  dailyReportOptions,
  globalCurrentMonthHospitalDrugCount,
  modelMetrics,
  monthlyReports,
  oneshotSummary,
  oneshotTerminals,
  overviewMetrics,
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
    modelMetrics,
    globalCurrentMonthHospitalDrugCount,
    workbenchFillPolicy,
    workbenchDisplayRows
  }
}

export function createStaticRiskEntitiesData() {
  return { displayLookupStatus: DISPLAY_LOOKUP_DEMO_STATUS, riskEntities }
}

export function createStaticRiskEntityDetailData(entityId) {
  const entity = riskEntities.find((item) => item.id === entityId) || riskEntities[0]
  return {
    displayLookupStatus: DISPLAY_LOOKUP_DEMO_STATUS,
    entity,
    horizonProfiles: riskCardHorizonProfiles[entity.id] || {}
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
    modelMetrics,
    dailyReportOptions,
    monthlyReports
  }
}

export function createStaticProofCasesData() {
  return { displayLookupStatus: DISPLAY_LOOKUP_DEMO_STATUS, proofCaseHorizonTabs, proofCaseHorizonSets, proofCases }
}

export async function loadWorkbenchData() {
  return tryLoadWhenDisplayLookupReady(() => api().frontendWorkbench(), mapWorkbenchPayload)
}

export async function loadRiskEntitiesData() {
  return tryLoadWhenDisplayLookupReady(() => api().frontendRiskEntities(), (payload) => ({
    riskEntities: payload.entities.map(mapRiskEntity)
  }))
}

export async function loadRiskEntityDetailData(entityId) {
  return tryLoadWhenDisplayLookupReady(() => api().frontendRiskEntityDetail(entityId), (payload) => ({
    entity: mapRiskEntity(payload.entity),
    horizonProfiles: Object.fromEntries(
      Object.entries(payload.horizon_profiles || {}).map(([horizon, profile]) => [horizon, mapHorizonProfile(profile)])
    )
  }))
}

export async function loadOneshotData() {
  return tryLoadWhenDisplayLookupReady(() => api().frontendOneshotTerminals(), mapOneshotPayload)
}

export async function loadMonthlyReportsData() {
  return tryLoadWhenDisplayLookupReady(() => api().frontendMonthlyReports(), mapMonthlyReportsPayload)
}

export async function loadProofCasesData() {
  await resolveDisplayLookupStatus()
  return null
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
    businessScore: row.business_score,
    businessScoreText: formatMoney(row.business_score),
    fillSource: row.fill_source,
    sourceType: row.source_type,
    action: row.action
  }
}

function mapRiskEntity(item) {
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
    businessScore: item.business_score,
    businessScoreText: formatMoney(item.business_score),
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
  return {
    horizon: profile.horizon,
    horizonLabel: formatHorizonLabel(profile.horizon),
    label: profile.label,
    riskProbability: profile.risk_probability,
    probabilityDisplay: formatPercent(profile.risk_probability),
    averageConsumptionInWindow: profile.average_consumption_in_window,
    averageConsumptionText: formatMoney(profile.average_consumption_in_window),
    businessScore: profile.business_score,
    businessScoreText: formatMoney(profile.business_score),
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
      score: item.score,
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
    modelMetrics: mapModelMetrics(payload.model_metrics || modelMetrics),
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
