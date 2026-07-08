export const batchContext = {
  reportMonth: '2026-07',
  scoreAsOfDate: '2026-07-31',
  dataWatermarkAt: '2026-07-07 13:32',
  scoreBatchId: '2026-07-monthly-risk-algorithm-fixture',
  resultBatchId: '2026-07-monthly-risk-algorithm-fixture',
  primaryHorizon: 'H6 主视角',
  scoreFormula: '风险概率 × 预测窗口内平均消费金额'
}

export const overviewMetrics = [
  { label: '主视角清单', value: '20', tone: 'danger', note: '医院 × 药品 · 已补齐' },
  { label: '风险卡', value: '24', tone: 'warning', note: 'RiskCard · detector 证据按卡组织' },
  { label: '新进终端', value: '6', tone: 'info', note: 'oneshot · 复购倾向监测' },
  { label: '高价值待跟进', value: '21', tone: 'success', note: '优先推进清单' }
]

export const modelMetrics = [
  {
    id: 'backbone_xgboost_h6',
    name: '主干风险概率模型',
    role: 'backbone_risk_probability',
    horizon: 'H6',
    window: '2026-01 to 2026-06 walk-forward',
    auc: '0.842',
    prauc: '0.318',
    ece: '0.037',
    brier: '0.109',
    topK: 'Top 5% / actual 5.03% / recall 41.2%',
    topKPolicy: 'direct_actual_share'
  },
  {
    id: 'oneshot_repurchase_propensity',
    name: 'oneshot 复购倾向模型',
    role: 'oneshot_repurchase_propensity',
    horizon: 'H6',
    window: '2026-01 to 2026-06 first-purchase cohorts',
    auc: '0.806',
    prauc: '0.441',
    ece: '0.043',
    brier: '0.137',
    topK: 'Top 10% / actual 9.96% / recall 53.3%',
    topKPolicy: 'direct_actual_share'
  },
  {
    id: 'detector_evidence_ranker',
    name: 'detector 证据排序模型',
    role: 'detector_evidence_ranker',
    horizon: 'H6',
    window: '2026-01 to 2026-06 detector evidence backtest',
    auc: '0.781',
    prauc: '0.294',
    ece: '0.052',
    brier: '0.128',
    topK: 'Union TopK requested 10% / actual 12.80% / recall 69.6%',
    topKPolicy: 'union_backfilled_actual_share'
  }
]

export const riskEntities = [
  {
    id: 're_xiehe_a_h6',
    hospital: '北京协和医院',
    drug: 'A产品线 · 心血管',
    manufacturer: 'M001',
    region: '华北',
    horizon: 'H6',
    riskLevel: 'high',
    riskColor: 'red',
    riskProbability: 0.82,
    probabilityDisplay: '82%',
    averageConsumptionInWindow: 1280000,
    averageConsumptionText: '¥1,280,000',
    businessScore: 1049600,
    businessScoreText: '¥1,049,600',
    status: '优先跟进',
    monthlyStatus: 'new',
    lastPurchase: '2026-05-02',
    daysSinceLast: 66,
    cards: 4,
    valueLevel: '高',
    reason: '采购间隔超出历史节奏，近 3 月频次下降，品规从 4 个缩至 1 个。',
    evidence: [
      '距离上次采购 66 天，历史中位采购间隔 28 天',
      '近 3 月采购频次低于过去 12 月基线',
      '品规覆盖收缩，主力规格消失'
    ],
    detectorNarrative: 'detector 结果自然语言聚合：间隔超期、频次下降和品规收缩同时指向采购节奏走弱，建议优先确认采购计划和竞品替代情况。',
    shapHighlights: [
      { feature: 'days_since_last_purchase', contribution: '+0.21', explanation: '距离末次采购天数显著抬升风险概率' },
      { feature: 'frequency_drop_90d', contribution: '+0.17', explanation: '近 90 天采购频次低于自身基线' },
      { feature: 'sku_coverage_delta', contribution: '+0.09', explanation: '品规覆盖明显收窄' }
    ],
    detectorResults: [
      {
        id: 'gap',
        name: '采购间隔 detector',
        score: 0.91,
        signal: '强命中',
        status: '采购间隔超期',
        evidence: '当前间隔 66 天，历史中位间隔 28 天，超期倍数 2.36。',
        action: '确认是否存在采购计划延后、替代品切换或配送节奏变化。'
      },
      {
        id: 'frequency',
        name: '频次下降 detector',
        score: 0.78,
        signal: '命中',
        status: '采购频次下降',
        evidence: '近 90 天订单频次较 12 个月基线下降 44%。',
        action: '核对科室需求和院内采购节奏。'
      },
      {
        id: 'sku',
        name: '品规收缩 detector',
        score: 0.72,
        signal: '命中',
        status: '品规覆盖收缩',
        evidence: '活跃品规从 4 个缩至 1 个，主力规格消失。',
        action: '查看是否有竞品替代或规格替换。'
      },
      {
        id: 'fulfillment',
        name: '配送履约 detector',
        score: 0.46,
        signal: '关注',
        status: '配送稳定性波动',
        evidence: '配送完成率较前期下降 8 个百分点。',
        action: '同步配送侧确认近期履约情况。'
      }
    ]
  },
  {
    id: 're_huaxi_c_h6',
    hospital: '四川大学华西医院',
    drug: 'C产品线 · 肿瘤',
    manufacturer: 'M001',
    region: '西南',
    horizon: 'H6',
    riskLevel: 'high',
    riskColor: 'red',
    riskProbability: 0.74,
    probabilityDisplay: '74%',
    averageConsumptionInWindow: 1950000,
    averageConsumptionText: '¥1,950,000',
    businessScore: 1443000,
    businessScoreText: '¥1,443,000',
    status: '优先跟进',
    monthlyStatus: 'persistent',
    lastPurchase: '2026-04-18',
    daysSinceLast: 80,
    cards: 5,
    valueLevel: '高',
    reason: '连续停购苗头叠加配送履约恶化，需要判断需求流失还是断供问题。',
    evidence: [
      '末次采购距今 80 天，明显超过自身采购节奏',
      '配送率连续下行，提示需求节奏和供应稳定性同步走弱',
      '高价值医院，建议优先复核'
    ],
    detectorNarrative: 'detector 结果自然语言聚合：高消费基线叠加采购间隔和配送履约信号，使该实体在业务评分排序中位列第一。',
    shapHighlights: [
      { feature: 'avg_consumption_h6', contribution: '+0.24', explanation: '预测窗口内平均消费金额高，放大业务优先级' },
      { feature: 'days_since_last_purchase', contribution: '+0.18', explanation: '距离末次采购天数推高风险概率' },
      { feature: 'fulfillment_drop', contribution: '+0.11', explanation: '配送履约下降提示供应侧扰动' }
    ],
    detectorResults: [
      {
        id: 'gap',
        name: '采购间隔 detector',
        score: 0.88,
        signal: '强命中',
        status: '采购间隔超期',
        evidence: '当前间隔 80 天，历史中位间隔 31 天。',
        action: '优先确认院内采购计划是否暂停。'
      },
      {
        id: 'frequency',
        name: '频次下降 detector',
        score: 0.81,
        signal: '命中',
        status: '采购频次下降',
        evidence: '连续两个自然月采购次数低于历史常规水平。',
        action: '复核用量是否被其他产品替代。'
      },
      {
        id: 'sku',
        name: '品规收缩 detector',
        score: 0.39,
        signal: '弱信号',
        status: '品规覆盖稳定',
        evidence: '核心品规仍保留，收缩主要来自低频规格。',
        action: '结合采购间隔和配送履约统一判断。'
      },
      {
        id: 'fulfillment',
        name: '配送履约 detector',
        score: 0.83,
        signal: '命中',
        status: '配送履约恶化',
        evidence: '配送完成率连续下降，近期缺货备注增加。',
        action: '同步配送商和供应计划，避免断供扩大。'
      }
    ]
  },
  {
    id: 're_renji_a_h6',
    hospital: '上海仁济医院',
    drug: 'A产品线 · 心血管',
    manufacturer: 'M002',
    region: '华东',
    horizon: 'H6',
    riskLevel: 'medium',
    riskColor: 'orange',
    riskProbability: 0.61,
    probabilityDisplay: '61%',
    averageConsumptionInWindow: 860000,
    averageConsumptionText: '¥860,000',
    businessScore: 524600,
    businessScoreText: '¥524,600',
    status: '跟进中',
    monthlyStatus: 'worsening',
    lastPurchase: '2026-05-29',
    daysSinceLast: 39,
    cards: 3,
    valueLevel: '中',
    reason: '采购量和采购频次同步下降，需要确认是否为正常窗口波动。',
    evidence: [
      '近 90 天订单频次低于基线',
      '采购数量下降但仍有持续采购',
      '建议本月保持人工复核'
    ],
    detectorNarrative: 'detector 结果自然语言聚合：频次下降较明显，间隔和品规信号中等，适合进入跟进中队列。',
    shapHighlights: [
      { feature: 'frequency_drop_90d', contribution: '+0.15', explanation: '采购频次下降是主要风险来源' },
      { feature: 'quantity_drop_90d', contribution: '+0.08', explanation: '采购量下降抬升风险概率' },
      { feature: 'recent_purchase_exists', contribution: '-0.06', explanation: '近期仍有采购，降低部分风险' }
    ],
    detectorResults: [
      {
        id: 'gap',
        name: '采购间隔 detector',
        score: 0.54,
        signal: '关注',
        status: '间隔轻度拉长',
        evidence: '当前间隔 39 天，略高于历史中位间隔 27 天。',
        action: '观察下个采购窗口是否恢复。'
      },
      {
        id: 'frequency',
        name: '频次下降 detector',
        score: 0.76,
        signal: '命中',
        status: '采购频次下降',
        evidence: '近 90 天频次低于 12 个月基线 36%。',
        action: '确认科室用量和竞品活动。'
      },
      {
        id: 'sku',
        name: '品规收缩 detector',
        score: 0.58,
        signal: '关注',
        status: '品规轻度收缩',
        evidence: '低频规格减少，主力规格仍在。',
        action: '关注主力规格采购是否延续。'
      },
      {
        id: 'fulfillment',
        name: '配送履约 detector',
        score: 0.22,
        signal: '平稳',
        status: '配送履约稳定',
        evidence: '配送完成率保持在正常区间。',
        action: '以需求侧复核为主。'
      }
    ]
  }
]

function formatPercent(value) {
  return `${Math.round(value * 100)}%`
}

function formatMoney(value) {
  return `¥${Math.round(value).toLocaleString('zh-CN')}`
}

function clampProbability(value) {
  return Math.min(0.96, Math.max(0.05, Number(value.toFixed(2))))
}

function buildHorizonProfile(entity, horizon, probabilityDelta, consumptionMultiplier, label) {
  const riskProbability = clampProbability(entity.riskProbability + probabilityDelta)
  const averageConsumptionInWindow = Math.round(entity.averageConsumptionInWindow * consumptionMultiplier)
  const businessScore = Math.round(riskProbability * averageConsumptionInWindow)
  const detectorFactor = horizon === 'H3' ? 0.86 : horizon === 'H12' ? 1.08 : 1

  return {
    horizon,
    label,
    riskProbability,
    probabilityDisplay: formatPercent(riskProbability),
    averageConsumptionInWindow,
    averageConsumptionText: formatMoney(averageConsumptionInWindow),
    businessScore,
    businessScoreText: formatMoney(businessScore),
    reason: `${horizon} ${label}：${entity.reason}`,
    detectorNarrative: `${horizon} detector 结果自然语言聚合：${entity.detectorNarrative.replace('detector 结果自然语言聚合：', '')}`,
    shapHighlights: entity.shapHighlights.map((item) => ({
      ...item,
      explanation: `${horizon} 视角：${item.explanation}`
    })),
    detectorResults: entity.detectorResults.map((detector) => ({
      ...detector,
      score: Number(Math.min(0.99, detector.score * detectorFactor).toFixed(2)),
      evidence: `${horizon} ${label}：${detector.evidence}`
    }))
  }
}

export const riskCardHorizonProfiles = Object.fromEntries(
  riskEntities.map((entity) => [
    entity.id,
    {
      H3: buildHorizonProfile(entity, 'H3', -0.14, 0.48, '短窗预警'),
      H6: buildHorizonProfile(entity, 'H6', 0, 1, '主视角'),
      H12: buildHorizonProfile(entity, 'H12', 0.08, 1.72, '长窗经营影响')
    }
  ])
)

export const oneshotSummary = {
  reportMonth: batchContext.reportMonth,
  count: 6,
  highPropensityCount: 3,
  averageRepurchasePropensity: '67%',
  expectedRepurchaseAmount: '¥1,520,000'
}

export const oneshotTerminals = [
  {
    id: 'os_001',
    hospital: '浙江大学医学院附属第一医院',
    drug: 'D产品线 · 消化',
    region: '华东',
    firstPurchaseDate: '2026-06-18',
    firstPurchaseAmount: 320000,
    firstPurchaseAmountText: '¥320,000',
    daysSinceFirstPurchase: 19,
    repurchasePropensity: 0.79,
    repurchasePropensityText: '79%',
    expectedRepurchaseAmountText: '¥410,000',
    priority: '高复购倾向',
    reason: '首采金额高，首采后 19 天内出现补货咨询，所在区域同类终端 H6 复购表现强。'
  },
  {
    id: 'os_002',
    hospital: '郑州大学第一附属医院',
    drug: 'A产品线 · 心血管',
    region: '华中',
    firstPurchaseDate: '2026-06-24',
    firstPurchaseAmount: 180000,
    firstPurchaseAmountText: '¥180,000',
    daysSinceFirstPurchase: 13,
    repurchasePropensity: 0.64,
    repurchasePropensityText: '64%',
    expectedRepurchaseAmountText: '¥260,000',
    priority: '中高复购倾向',
    reason: '首采金额中高，采购后仍处于常规复购观察窗口，建议跟进用量反馈。'
  },
  {
    id: 'os_003',
    hospital: '苏州大学附属第一医院',
    drug: 'C产品线 · 肿瘤',
    region: '华东',
    firstPurchaseDate: '2026-06-05',
    firstPurchaseAmount: 510000,
    firstPurchaseAmountText: '¥510,000',
    daysSinceFirstPurchase: 32,
    repurchasePropensity: 0.71,
    repurchasePropensityText: '71%',
    expectedRepurchaseAmountText: '¥850,000',
    priority: '高复购倾向',
    reason: '首采金额高，区域同类终端复购周期集中在 35-60 天，当前进入促进复购窗口。'
  }
]

export const globalCurrentMonthHospitalDrugCount = riskEntities.length

export const workbenchFillPolicy = {
  manufacturer: 'M001',
  workbenchTargetCount: 20,
  globalCurrentMonthHospitalDrugCount,
  fillReason: 'global 当月医院 × 药品数量低于主工作台容量时，直接使用补充算法填充到 20 个。'
}

const fillHospitals = [
  '南京鼓楼医院',
  '中南大学湘雅医院',
  '山东大学齐鲁医院',
  '武汉同济医院',
  '广州中山肿瘤医院',
  '重庆医科大学附属第一医院',
  '安徽医科大学第一附属医院',
  '北京朝阳医院',
  '复旦大学附属华山医院',
  '天津医科大学总医院',
  '西安交通大学第一附属医院',
  '大连医科大学附属第一医院',
  '厦门大学附属第一医院',
  '徐州医科大学附属医院',
  '新疆医科大学第一附属医院',
  '海南省人民医院',
  '贵州医科大学附属医院'
]

const fillSources = ['oneshot 复购倾向', 'detector 补充排序', '历史节奏回补', '高价值终端覆盖']
const fillDrugs = ['A产品线 · 心血管', 'B产品线 · 抗感染', 'C产品线 · 肿瘤', 'D产品线 · 消化']

export const workbenchFillCandidates = fillHospitals.map((hospital, index) => {
  const riskProbability = Number((0.58 - index * 0.012).toFixed(2))
  const averageConsumptionInWindow = 760000 - index * 18000
  const businessScore = Math.round(riskProbability * averageConsumptionInWindow)
  const drug = fillDrugs[index % fillDrugs.length]

  return {
    id: `fill_${String(index + 1).padStart(2, '0')}`,
    entityId: '',
    manufacturer: workbenchFillPolicy.manufacturer,
    hospital,
    drug,
    hospitalDrugKey: `${hospital} × ${drug}`,
    region: ['华东', '华中', '华北', '华南', '西南'][index % 5],
    riskProbability,
    probabilityDisplay: formatPercent(riskProbability),
    averageConsumptionInWindow,
    averageConsumptionText: formatMoney(averageConsumptionInWindow),
    businessScore,
    businessScoreText: formatMoney(businessScore),
    fillSource: fillSources[index % fillSources.length],
    sourceType: '补充算法',
    action: '进入主工作台跟进清单'
  }
})

export const workbenchDisplayRows = [
  ...riskEntities.map((entity) => ({
    id: entity.id,
    entityId: entity.id,
    manufacturer: entity.manufacturer,
    hospital: entity.hospital,
    drug: entity.drug,
    hospitalDrugKey: `${entity.hospital} × ${entity.drug}`,
    region: entity.region,
    riskProbability: entity.riskProbability,
    probabilityDisplay: entity.probabilityDisplay,
    averageConsumptionInWindow: entity.averageConsumptionInWindow,
    averageConsumptionText: entity.averageConsumptionText,
    businessScore: entity.businessScore,
    businessScoreText: entity.businessScoreText,
    fillSource: '主干风险模型',
    sourceType: 'global 当月命中',
    action: '查看风险卡'
  })),
  ...workbenchFillCandidates
]
  .sort((a, b) => b.businessScore - a.businessScore)
  .slice(0, workbenchFillPolicy.workbenchTargetCount)

export const dailyReportOptions = [
  {
    id: 'daily_2026_07_07',
    date: '2026-07-07',
    label: '当前日报',
    title: '2026-07-07 风险日报',
    reportMonth: '2026-07',
    scoreBatchId: batchContext.scoreBatchId,
    dataWatermarkAt: batchContext.dataWatermarkAt,
    highRiskEntities: '9',
    oneshotCount: '6',
    detectorAlerts: '24',
    summary: '当前日报聚焦 H6 高风险 entity、oneshot 复购倾向和 detector 证据链。'
  },
  {
    id: 'daily_2026_07_06',
    date: '2026-07-06',
    label: '上一期',
    title: '2026-07-06 风险日报',
    reportMonth: '2026-07',
    scoreBatchId: '2026-07-daily-risk-20260706',
    dataWatermarkAt: '2026-07-06 18:00',
    highRiskEntities: '8',
    oneshotCount: '5',
    detectorAlerts: '19',
    summary: '上一期日报用于对比新增、持续和缓解的风险实体变化。'
  },
  {
    id: 'daily_2026_07_05',
    date: '2026-07-05',
    label: '历史日报',
    title: '2026-07-05 风险日报',
    reportMonth: '2026-07',
    scoreBatchId: '2026-07-daily-risk-20260705',
    dataWatermarkAt: '2026-07-05 18:00',
    highRiskEntities: '7',
    oneshotCount: '4',
    detectorAlerts: '17',
    summary: '历史日报展示风险排序、detector 证据和新进终端复购倾向的连续变化。'
  }
]

export const monthlyReports = [
  {
    id: 'monthly_2026_07',
    title: '2026-07 MonthlyReport',
    reportMonth: '2026-07',
    scoreBatchId: batchContext.scoreBatchId,
    dataWatermarkAt: batchContext.dataWatermarkAt,
    summary: 'RiskResultBatch 已生成，支撑月报工作清单、风险实体跟进、新进终端复购监测和成功案例沉淀。'
  },
  {
    id: 'monthly_2026_06',
    title: '2026-06 MonthlyReport',
    reportMonth: '2026-06',
    scoreBatchId: '2026-06-monthly-risk-algorithm-review',
    dataWatermarkAt: '2026-06-30 23:59',
    summary: '历史月报入口，用于比较新增、持续、缓解、oneshot 复购倾向与主工作台补齐变化。'
  }
]

export const proofCases = [
  {
    id: 'proof_xiehe_2025',
    title: 'Proof-case · 北京协和历史命中案例',
    visible: '业务可见',
    outcome: '历史高风险线索后续发生停购，证据包括采购间隔超期和品规收缩。',
    caveat: '成功案例展示采购间隔超期、品规收缩和后续停购结果，突出产品提前识别价值。'
  },
  {
    id: 'proof_huaxi_2025',
    title: 'Proof-case · 华西配送侧案例',
    visible: '业务可见',
    outcome: '系统提前识别配送履约恶化，业务复核后归因为断供侧问题。',
    caveat: '成功案例展示配送履约恶化信号，帮助团队提前定位断供侧风险。'
  }
]
