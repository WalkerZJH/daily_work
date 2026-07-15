export const batchContext = {
  reportMonth: '2026-07',
  scoreBatchId: '',
  resultBatchId: '',
  dataWatermarkAt: '',
  primaryHorizon: '6个月'
}

export const overviewMetrics = []

export const dailyDetectorStatus = {
  ready: false,
  sourceLabel: '接口未接通',
  runDate: '2026-07-09',
  reportMonth: '2026-07',
  clueCount: 0,
  attachedHighRiskCount: 0,
  scannedEntityCount: 0,
  statusText: '暂无正式巡检数据',
  caveat: '请接通后端接口后查看正式结果'
}

export const horizonOptions = [
  { id: 'H3', label: '3个月' },
  { id: 'H6', label: '6个月' },
  { id: 'H12', label: '12个月' }
]

export const sortOptions = [
  { id: 'risk_probability', label: '丢失概率' },
  { id: 'involved_amount', label: '涉及金额' }
]

export const topNOptions = [10, 20, 30, 50]

export const manufacturerOptions = [
  { code: '', name: '生产企业未接通' }
]

export const dailyDetectorDateOptions = [
  { runDate: dailyDetectorStatus.runDate, label: dailyDetectorStatus.runDate }
]

export const defaultWorkbenchQuery = {
  manufacturerCode: '',
  reportMonth: batchContext.reportMonth,
  runDate: dailyDetectorStatus.runDate,
  horizon: 'H6',
  topN: 20,
  sortBy: 'risk_probability'
}

export const detectorCatalogSummary = []

export const detectorConfigStatus = {
  ready: false,
  latestRunDate: dailyDetectorStatus.runDate,
  message: '规则配置状态未接通'
}

export const riskEntities = []

export const riskCardHorizonProfiles = {}

export const oneshotSummary = {
  reportMonth: '',
  cutoffDate: '',
  resultBatchId: '',
  count: 0,
  dailyNewTerminalCount: 0,
  monthlyNewTerminalCount: 0
}

export const oneshotTerminals = []

export const globalCurrentMonthHospitalDrugCount = 0

export const workbenchFillCandidates = []

export const workbenchDisplayRows = []

export const dailyDetectorClues = []

export const probabilityTrendByEntityId = {}

export const dailyReportOptions = [
  { runDate: dailyDetectorStatus.runDate, label: dailyDetectorStatus.runDate }
]

export const monthlyReports = []

export const proofCaseHorizonTabs = [
  { id: 'H3', label: '3个月' },
  { id: 'H6', label: '6个月' },
  { id: 'H12', label: '12个月' }
]

export const proofCaseHorizonSets = {
  H3: { summary: {}, cases: [] },
  H6: { summary: {}, cases: [] },
  H12: { summary: {}, cases: [] }
}

export const proofCases = []
