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
  proofCases,
  riskCardHorizonProfiles,
  riskEntities,
  workbenchDisplayRows,
  workbenchFillPolicy
} from './demoData'

export function createStaticWorkbenchData() {
  return {
    batchContext,
    overviewMetrics,
    modelMetrics,
    globalCurrentMonthHospitalDrugCount,
    workbenchFillPolicy,
    workbenchDisplayRows
  }
}

export function createStaticRiskEntitiesData() {
  return { riskEntities }
}

export function createStaticRiskEntityDetailData(entityId) {
  const entity = riskEntities.find((item) => item.id === entityId) || riskEntities[0]
  return {
    entity,
    horizonProfiles: riskCardHorizonProfiles[entity.id] || {}
  }
}

export function createStaticOneshotData() {
  return { oneshotSummary, oneshotTerminals }
}

export function createStaticMonthlyReportsData() {
  return {
    batchContext,
    overviewMetrics,
    modelMetrics,
    dailyReportOptions,
    monthlyReports
  }
}

export function createStaticProofCasesData() {
  return { proofCases }
}

export async function loadWorkbenchData() {
  return tryLoad(() => api().frontendWorkbench(), mapWorkbenchPayload)
}

export async function loadRiskEntitiesData() {
  return tryLoad(() => api().frontendRiskEntities(), (payload) => ({
    riskEntities: payload.entities.map(mapRiskEntity)
  }))
}

export async function loadRiskEntityDetailData(entityId) {
  return tryLoad(() => api().frontendRiskEntityDetail(entityId), (payload) => ({
    entity: mapRiskEntity(payload.entity),
    horizonProfiles: Object.fromEntries(
      Object.entries(payload.horizon_profiles || {}).map(([horizon, profile]) => [horizon, mapHorizonProfile(profile)])
    )
  }))
}

export async function loadOneshotData() {
  return tryLoad(() => api().frontendOneshotTerminals(), mapOneshotPayload)
}

export async function loadMonthlyReportsData() {
  return tryLoad(() => api().frontendMonthlyReports(), mapMonthlyReportsPayload)
}

export async function loadProofCasesData() {
  return tryLoad(() => api().frontendProofCases(), (payload) => ({
    proofCases: (payload.items || []).map((item) => ({
      id: item.proof_case_id,
      title: item.title,
      visible: item.visible,
      outcome: item.outcome,
      caveat: item.case_summary
    }))
  }))
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
    primaryHorizon: `${context.primary_horizon} ${context.primary_horizon_label}`,
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
  return {
    id: row.row_id,
    entityId: row.entity_id || '',
    manufacturer: row.manufacturer_code,
    hospital: row.hospital_name,
    drug: row.drug_name,
    hospitalDrugKey: `${row.hospital_name} × ${row.drug_name}`,
    region: row.region,
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
    hospital: item.hospital_name,
    drug: item.drug_name,
    manufacturer: item.manufacturer_code,
    region: item.region,
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
    reason: item.primary_reason,
    evidence: [],
    detectorNarrative: '',
    shapHighlights: [],
    detectorResults: []
  }
}

function mapHorizonProfile(profile) {
  return {
    horizon: profile.horizon,
    label: profile.label,
    riskProbability: profile.risk_probability,
    probabilityDisplay: formatPercent(profile.risk_probability),
    averageConsumptionInWindow: profile.average_consumption_in_window,
    averageConsumptionText: formatMoney(profile.average_consumption_in_window),
    businessScore: profile.business_score,
    businessScoreText: formatMoney(profile.business_score),
    reason: profile.reason,
    detectorNarrative: profile.detector_narrative,
    shapHighlights: profile.xgboost_shap.map((item) => ({
      feature: item.feature,
      contribution: formatContribution(item.contribution),
      explanation: item.explanation
    })),
    detectorResults: profile.detector_results.map((item) => ({
      id: item.detector_id,
      name: item.detector_name,
      score: item.score,
      signal: item.signal,
      status: item.status,
      evidence: item.evidence,
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
      hospital: item.hospital_name,
      drug: item.drug_name,
      region: item.region,
      firstPurchaseDate: item.first_purchase_date,
      firstPurchaseAmount: item.first_purchase_amount,
      firstPurchaseAmountText: formatMoney(item.first_purchase_amount),
      daysSinceFirstPurchase: item.days_since_first_purchase,
      repurchasePropensity: item.repurchase_propensity,
      repurchasePropensityText: formatPercent(item.repurchase_propensity),
      expectedRepurchaseAmountText: formatMoney(item.expected_repurchase_amount),
      priority: item.priority,
      reason: item.reason
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
      summary: item.summary
    })),
    monthlyReports: payload.monthly_reports.map((item) => ({
      id: item.monthly_report_id,
      title: item.title,
      reportMonth: item.report_month,
      scoreBatchId: item.score_batch_id,
      dataWatermarkAt: item.data_watermark_at,
      summary: item.summary
    }))
  }
}

function mapModelMetrics(items) {
  return (items || []).map((item) => {
    if (item.auc !== undefined && item.topK !== undefined) return item
    const firstTopK = (item.topk_recall || [])[0] || {}
    const actualPercent =
      firstTopK.actual_k_percent !== undefined ? formatMetricPercent(firstTopK.actual_k_percent) : '-'
    const requestedPercent =
      firstTopK.requested_k_percent !== undefined ? formatMetricPercent(firstTopK.requested_k_percent) : '-'
    const recall = firstTopK.recall !== undefined ? formatMetricPercent(firstTopK.recall) : '-'
    const prefix = firstTopK.k_policy === 'union_backfilled_actual_share' ? 'Union TopK' : firstTopK.label || 'TopK'
    return {
      id: item.model_id,
      name: item.model_name,
      role: item.model_role,
      horizon: item.horizon || '-',
      window: item.evaluation_window,
      auc: formatMetric(item.auc),
      prauc: formatMetric(item.prauc),
      ece: formatMetric(item.ece),
      brier: formatMetric(item.brier),
      topK: `${prefix} requested ${requestedPercent} / actual ${actualPercent} / recall ${recall}`,
      topKPolicy: firstTopK.k_policy || 'direct_actual_share'
    }
  })
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
