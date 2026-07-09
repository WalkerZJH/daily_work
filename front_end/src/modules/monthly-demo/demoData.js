export const batchContext = {
  reportMonth: '2026-07',
  scoreAsOfDate: '2026-07-31',
  dataWatermarkAt: '2026-07-07 13:32',
  scoreBatchId: '2026-07-monthly-risk-algorithm-fixture',
  resultBatchId: '2026-07-monthly-risk-algorithm-fixture',
  primaryHorizon: '6月主视角',
  scoreFormula: '风险概率 × 预测窗口内平均消费金额'
}

export const overviewMetrics = [
  { label: '主视角清单', value: '20', tone: 'danger', note: '医院 × 药品 · 已补齐' },
  { label: '风险卡', value: '24', tone: 'warning', note: 'RiskCard · detector 证据按卡组织' },
  { label: '新进终端', value: '6', tone: 'info', note: 'oneshot · 复购倾向监测' },
  { label: '高价值待跟进', value: '21', tone: 'success', note: '优先推进清单' }
]

export const dailyDetectorStatus = {
  ready: false,
  sourceLabel: '演示数据',
  runDate: '2026-07-09',
  reportMonth: batchContext.reportMonth,
  clueCount: 9,
  attachedHighRiskCount: 6,
  scannedEntityCount: 128,
  statusText: '今日规则巡检结果已更新',
  caveat: '今日巡检结果每天变化，月报批次结论保持稳定。'
}

export const detectorCatalogSummary = [
  {
    id: 'purchase_gap',
    name: '采购间隔巡检',
    family: '节奏规则',
    status: 'implemented',
    statusLabel: '已启用规则',
    caveat: '识别当前采购间隔偏离历史节奏的对象。'
  },
  {
    id: 'frequency_drop',
    name: '采购频次巡检',
    family: '节奏规则',
    status: 'implemented',
    statusLabel: '已启用规则',
    caveat: '识别近期采购频次低于自身基线的对象。'
  },
  {
    id: 'sku_wallet',
    name: '品规覆盖巡检',
    family: '结构规则',
    status: 'experimental',
    statusLabel: '实验规则',
    caveat: '用于观察品规覆盖变化。'
  },
  {
    id: 'policy_signal',
    name: '政策价格巡检',
    family: '外部规则',
    status: 'interface_only',
    statusLabel: '接口预留',
    caveat: '当前仅展示接口状态。'
  }
]

export const detectorConfigStatus = {
  effectiveConfigVersion: 'detector-rules-2026-07',
  latestRunDate: dailyDetectorStatus.runDate,
  pendingConfigExists: false,
  nextRunRequired: false,
  message: '规则参数调整后，将在下一次 detector 巡检运行后生效。'
}

export const modelMetrics = [
  {
    id: 'backbone_xgboost_h3',
    name: '主干风险模型 3月',
    role: '短窗风险识别',
    horizon: '3月',
    window: '2020-2025 滚动回测 · 524,950 条',
    auc: '0.812',
    prauc: '0.776',
    praucLift: '1.610',
    ece: '0.024',
    brier: '0.177',
    topK: '前10%名单：召回17.96%，命中精度86.94%，提升1.80倍'
  },
  {
    id: 'backbone_xgboost_h6',
    name: '主干风险模型 6月',
    role: '月报主视角',
    horizon: '6月',
    window: '2020-2025 滚动回测 · 524,950 条',
    auc: '0.814',
    prauc: '0.686',
    praucLift: '1.857',
    ece: '0.022',
    brier: '0.169',
    topK: '前10%名单：召回21.12%，命中精度78.35%，提升2.11倍'
  },
  {
    id: 'backbone_xgboost_h12',
    name: '主干风险模型 12月',
    role: '长窗经营影响',
    horizon: '12月',
    window: '2020-2025 滚动回测 · 369,465 条',
    auc: '0.814',
    prauc: '0.598',
    praucLift: '2.090',
    ece: '0.023',
    brier: '0.154',
    topK: '前10%名单：召回23.95%，命中精度68.99%，提升2.39倍'
  },
  {
    id: 'oneshot_repurchase_h6',
    name: '新进终端复购倾向 6月',
    role: '首采人群回测',
    horizon: '6月',
    window: '新进终端回测 · 83,824 条',
    auc: '0.307',
    prauc: '0.264',
    praucLift: '0.725',
    ece: '0.321',
    brier: '0.352',
    topK: '复购倾向分层：6月正例率36.36%，用于识别首采后的复购倾向差异'
  },
  {
    id: 'frequency_detector_evidence',
    name: '采购频次证据模块',
    role: 'detector 证据识别',
    horizon: '6月',
    window: '证据命中回测 · 1,419,365 条',
    auc: '0.672',
    prauc: '0.516',
    praucLift: '1.324',
    ece: '0.312',
    brier: '0.312',
    topK: '命中证据：覆盖38.92%，召回59.93%，命中后风险率59.98%'
  },
  {
    id: 'interval_detector_evidence',
    name: '采购间隔证据模块',
    role: 'detector 证据识别',
    horizon: '6月',
    window: '证据命中回测 · 1,419,365 条',
    auc: '0.583',
    prauc: '0.449',
    praucLift: '1.152',
    ece: '0.355',
    brier: '0.355',
    topK: '命中证据：覆盖20.31%，召回30.46%，命中后风险率58.41%'
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
    detectorNarrative: 'detector 结果自然语言聚合：高消费基线叠加采购间隔和配送履约信号，使该实体在损失价值排序中位列第一。',
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

function horizonDisplayLabel(horizon) {
  return horizon === 'H3' ? '3月' : horizon === 'H12' ? '12月' : '6月'
}

function buildHorizonProfile(entity, horizon, probabilityDelta, consumptionMultiplier, label) {
  const riskProbability = clampProbability(entity.riskProbability + probabilityDelta)
  const averageConsumptionInWindow = Math.round(entity.averageConsumptionInWindow * consumptionMultiplier)
  const businessScore = Math.round(riskProbability * averageConsumptionInWindow)
  const detectorFactor = horizon === 'H3' ? 0.86 : horizon === 'H12' ? 1.08 : 1
  const horizonLabel = horizonDisplayLabel(horizon)

  return {
    horizon,
    horizonLabel,
    label,
    riskProbability,
    probabilityDisplay: formatPercent(riskProbability),
    averageConsumptionInWindow,
    averageConsumptionText: formatMoney(averageConsumptionInWindow),
    businessScore,
    businessScoreText: formatMoney(businessScore),
    lossValue: businessScore,
    lossValueText: formatMoney(businessScore),
    reason: `${horizonLabel} ${label}：${entity.reason}`,
    detectorNarrative: `${horizonLabel} detector 结果自然语言聚合：${entity.detectorNarrative.replace('detector 结果自然语言聚合：', '')}`,
    shapHighlights: entity.shapHighlights.map((item) => ({
      ...item,
      explanation: `${horizonLabel}视角：${item.explanation}`
    })),
    detectorResults: entity.detectorResults.map((detector) => ({
      ...detector,
      score: Number(Math.min(0.99, detector.score * detectorFactor).toFixed(2)),
      evidence: `${horizonLabel} ${label}：${detector.evidence}`
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
    reason: '首采金额高，首采后 19 天内出现补货咨询，所在区域同类终端 6月复购表现强。'
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
    lossValue: businessScore,
    lossValueText: formatMoney(businessScore),
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
    lossValue: entity.lossValue ?? entity.businessScore,
    lossValueText: entity.lossValueText ?? entity.businessScoreText,
    fillSource: '主干风险模型',
    sourceType: 'global 当月命中',
    action: '查看风险卡'
  })),
  ...workbenchFillCandidates
]
  .sort((a, b) => b.businessScore - a.businessScore)
  .slice(0, workbenchFillPolicy.workbenchTargetCount)

export const dailyDetectorClues = [
  {
    id: 'clue_gap_xiehe_a',
    riskEntityId: 're_xiehe_a_h6',
    sourceType: 'monthly_high_risk',
    sourceTypeLabel: '月报高风险对象',
    isMonthlyHighRiskEntity: true,
    hospital: '北京协和医院',
    drug: 'A产品线 · 心血管',
    manufacturer: 'M001',
    region: '华北',
    detectorName: '采购间隔巡检',
    detectorFamily: '节奏规则',
    detectorScore: 91,
    detectorScoreText: '91',
    detectorScoreLabel: '规则巡检分',
    detectorLevel: '强命中',
    hitFlag: true,
    rootCauseLabel: '采购间隔显著拉长',
    evidenceText: '当前距离末次采购 66 天，高于历史中位间隔 28 天，今日规则巡检建议优先复核采购节奏。',
    detectorRunDate: dailyDetectorStatus.runDate,
    monthlyRiskProbability: 0.82,
    monthlyRiskProbabilityText: '82%',
    lossValue: 1049600,
    lossValueText: '¥1,049,600',
    actionText: '查看月报风险详情'
  },
  {
    id: 'clue_frequency_huaxi_c',
    riskEntityId: 're_huaxi_c_h6',
    sourceType: 'monthly_high_risk',
    sourceTypeLabel: '月报高风险对象',
    isMonthlyHighRiskEntity: true,
    hospital: '四川大学华西医院',
    drug: 'C产品线 · 肿瘤',
    manufacturer: 'M001',
    region: '西南',
    detectorName: '采购频次巡检',
    detectorFamily: '节奏规则',
    detectorScore: 84,
    detectorScoreText: '84',
    detectorScoreLabel: '规则巡检分',
    detectorLevel: '命中',
    hitFlag: true,
    rootCauseLabel: '近期频次低于自身基线',
    evidenceText: '近 90 天采购频次较过去 12 个月基线下降，规则证据已附着到月报风险卡。',
    detectorRunDate: dailyDetectorStatus.runDate,
    monthlyRiskProbability: 0.74,
    monthlyRiskProbabilityText: '74%',
    lossValue: 1443000,
    lossValueText: '¥1,443,000',
    actionText: '查看月报风险详情'
  },
  {
    id: 'clue_sku_renji_a',
    riskEntityId: 're_renji_a_h6',
    sourceType: 'monthly_high_risk',
    sourceTypeLabel: '月报高风险对象',
    isMonthlyHighRiskEntity: true,
    hospital: '上海仁济医院',
    drug: 'A产品线 · 心血管',
    manufacturer: 'M002',
    region: '华东',
    detectorName: '品规覆盖巡检',
    detectorFamily: '结构规则',
    detectorScore: 72,
    detectorScoreText: '72',
    detectorScoreLabel: '规则巡检分',
    detectorLevel: '命中',
    hitFlag: true,
    rootCauseLabel: '活跃品规减少',
    evidenceText: '今日巡检发现活跃品规覆盖收缩，作为月报高风险对象的补充证据展示。',
    detectorRunDate: dailyDetectorStatus.runDate,
    monthlyRiskProbability: 0.61,
    monthlyRiskProbabilityText: '61%',
    lossValue: 524600,
    lossValueText: '¥524,600',
    actionText: '查看月报风险详情'
  },
  {
    id: 'clue_rule_only_nanjing_b',
    riskEntityId: '',
    sourceType: 'daily_rule_clue',
    sourceTypeLabel: '仅规则命中',
    isMonthlyHighRiskEntity: false,
    hospital: '南京鼓楼医院',
    drug: 'B产品线 · 抗感染',
    manufacturer: 'M001',
    region: '华东',
    detectorName: '采购间隔巡检',
    detectorFamily: '节奏规则',
    detectorScore: 78,
    detectorScoreText: '78',
    detectorScoreLabel: '规则巡检分',
    detectorLevel: '关注',
    hitFlag: true,
    rootCauseLabel: '补货节奏延后',
    evidenceText: '该对象未进入本期月报高风险清单，但今日规则巡检发现采购间隔偏离历史节奏。',
    detectorRunDate: dailyDetectorStatus.runDate,
    monthlyRiskProbability: null,
    monthlyRiskProbabilityText: '-',
    lossValue: null,
    lossValueText: '-',
    actionText: '查看规则线索详情'
  },
  {
    id: 'clue_rule_only_xiangya_d',
    riskEntityId: '',
    sourceType: 'daily_rule_clue',
    sourceTypeLabel: '仅规则命中',
    isMonthlyHighRiskEntity: false,
    hospital: '中南大学湘雅医院',
    drug: 'D产品线 · 消化',
    manufacturer: 'M001',
    region: '华中',
    detectorName: '采购频次巡检',
    detectorFamily: '节奏规则',
    detectorScore: 69,
    detectorScoreText: '69',
    detectorScoreLabel: '规则巡检分',
    detectorLevel: '关注',
    hitFlag: true,
    rootCauseLabel: '近期采购频次下降',
    evidenceText: '该对象为今日规则线索，建议按巡检证据作为边缘线索观察。',
    detectorRunDate: dailyDetectorStatus.runDate,
    monthlyRiskProbability: null,
    monthlyRiskProbabilityText: '-',
    lossValue: null,
    lossValueText: '-',
    actionText: '查看规则线索详情'
  }
]

export const probabilityTrendByEntityId = {
  re_xiehe_a_h6: [
    { reportMonth: '2026-03', riskProbability: 0.48, riskProbabilityText: '48%', lossValue: 614400, lossValueText: '¥614,400' },
    { reportMonth: '2026-04', riskProbability: 0.57, riskProbabilityText: '57%', lossValue: 729600, lossValueText: '¥729,600' },
    { reportMonth: '2026-05', riskProbability: 0.68, riskProbabilityText: '68%', lossValue: 870400, lossValueText: '¥870,400' },
    { reportMonth: '2026-06', riskProbability: 0.76, riskProbabilityText: '76%', lossValue: 972800, lossValueText: '¥972,800' },
    { reportMonth: '2026-07', riskProbability: 0.82, riskProbabilityText: '82%', lossValue: 1049600, lossValueText: '¥1,049,600' }
  ],
  re_huaxi_c_h6: [
    { reportMonth: '2026-03', riskProbability: 0.44, riskProbabilityText: '44%', lossValue: 858000, lossValueText: '¥858,000' },
    { reportMonth: '2026-04', riskProbability: 0.55, riskProbabilityText: '55%', lossValue: 1072500, lossValueText: '¥1,072,500' },
    { reportMonth: '2026-05', riskProbability: 0.63, riskProbabilityText: '63%', lossValue: 1228500, lossValueText: '¥1,228,500' },
    { reportMonth: '2026-06', riskProbability: 0.69, riskProbabilityText: '69%', lossValue: 1345500, lossValueText: '¥1,345,500' },
    { reportMonth: '2026-07', riskProbability: 0.74, riskProbabilityText: '74%', lossValue: 1443000, lossValueText: '¥1,443,000' }
  ],
  re_renji_a_h6: [
    { reportMonth: '2026-03', riskProbability: 0.39, riskProbabilityText: '39%', lossValue: 335400, lossValueText: '¥335,400' },
    { reportMonth: '2026-04', riskProbability: 0.46, riskProbabilityText: '46%', lossValue: 395600, lossValueText: '¥395,600' },
    { reportMonth: '2026-05', riskProbability: 0.52, riskProbabilityText: '52%', lossValue: 447200, lossValueText: '¥447,200' },
    { reportMonth: '2026-06', riskProbability: 0.58, riskProbabilityText: '58%', lossValue: 498800, lossValueText: '¥498,800' },
    { reportMonth: '2026-07', riskProbability: 0.61, riskProbabilityText: '61%', lossValue: 524600, lossValueText: '¥524,600' }
  ]
}

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
    summary: '当前日报聚焦 6月高风险 entity、oneshot 复购倾向和 detector 证据链。'
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

export const proofCaseHorizonTabs = [
  { id: 'H3', label: '3月风险', note: '短窗验证' },
  { id: 'H6', label: '6月风险', note: '月报主视角' },
  { id: 'H12', label: '12月风险', note: '长窗价值' }
]

export const proofCaseHorizonSets = {
  H3: {
      "horizon": "H3",
      "label": "3月风险",
      "reportMonth": "2024-10",
      "reportDate": "2024-10-31",
      "validationEnd": "2025-01-31",
      "validationDays": "92 天",
      "ece": "0.024",
      "subtitle": "短窗闭合验证",
      "narrative": "以 2024-10-31 月报为起点，主干模型识别出高概率、高价值流失对象；到 2025-01-31 验证窗口闭合时，入选案例在窗口内保持 0 次续购，展示产品提前识别高价值风险的能力。",
      "cases": [
          {
              "id": "hit_202410_h3_01",
              "title": "2024-10 月报命中：平煤神马医疗集团总医院 × 盐酸倍他司汀注射液",
              "visible": "命中确认",
              "reportDate": "2024-10-31",
              "validationEnd": "2025-01-31",
              "horizon": "H3",
              "horizonLabel": "3月风险",
              "manufacturer": "哈药集团三精制药有限公司",
              "manufacturerCode": "9701EFF559DF4862AF18CF0DC1B6962D",
              "hospital": "平煤神马医疗集团总医院",
              "hospitalCode": "YL415576",
              "drug": "盐酸倍他司汀注射液",
              "drugCode": "e55aab9b3ee754a3580eded051caa1c2",
              "riskProbability": "72.0%",
              "riskProbabilityValue": 0.719872,
              "windowConsumption": "¥1,314,461",
              "businessScore": "¥946,244",
              "lastPurchase": "2024-05-31",
              "daysSinceLastAtReport": "152 天",
              "noPurchaseAfterReport": "92 天",
              "noPurchaseFromLast": "244 天",
              "observedAmount": "¥5,257,845",
              "demandShape": "intermittent",
              "outcome": "验证窗口内 0 次续购，3月流失命中。",
              "caseSummary": "月报日后至验证窗口闭合保持 0 次采购记录，高价值风险提前进入复盘清单。",
              "evidence": [
                  "月报日前 12 个月已形成 ¥5,257,845 的采购规模。",
                  "2024-10-31 输出风险概率 72.0%，损失价值 ¥946,244。",
                  "从月报日到 2025-01-31 连续 92 天未续购；从上次采购到闭合累计 244 天。"
              ]
          },
          {
              "id": "hit_202410_h3_02",
              "title": "2024-10 月报命中：苏州大学附属第二医院 × 盘龙七片",
              "visible": "命中确认",
              "reportDate": "2024-10-31",
              "validationEnd": "2025-01-31",
              "horizon": "H3",
              "horizonLabel": "3月风险",
              "manufacturer": "陕西盘龙药业集团股份有限公司",
              "manufacturerCode": "1D93E15EBB9B4F14A1C18E0CD1750A0A",
              "hospital": "苏州大学附属第二医院",
              "hospitalCode": "YL665667",
              "drug": "盘龙七片",
              "drugCode": "ZA16DAP0017010402404",
              "riskProbability": "62.2%",
              "riskProbabilityValue": 0.622103,
              "windowConsumption": "¥1,424,648",
              "businessScore": "¥886,278",
              "lastPurchase": "2024-05-20",
              "daysSinceLastAtReport": "163 天",
              "noPurchaseAfterReport": "92 天",
              "noPurchaseFromLast": "255 天",
              "observedAmount": "¥5,698,592",
              "demandShape": "smooth",
              "outcome": "验证窗口内 0 次续购，3月流失命中。",
              "caseSummary": "月报日后至验证窗口闭合保持 0 次采购记录，高价值风险提前进入复盘清单。",
              "evidence": [
                  "月报日前 12 个月已形成 ¥5,698,592 的采购规模。",
                  "2024-10-31 输出风险概率 62.2%，损失价值 ¥886,278。",
                  "从月报日到 2025-01-31 连续 92 天未续购；从上次采购到闭合累计 255 天。"
              ]
          },
          {
              "id": "hit_202410_h3_03",
              "title": "2024-10 月报命中：上海市长宁区北新泾街道社区卫生服务中心 × 维生素D2软胶囊",
              "visible": "命中确认",
              "reportDate": "2024-10-31",
              "validationEnd": "2025-01-31",
              "horizon": "H3",
              "horizonLabel": "3月风险",
              "manufacturer": "南京海鲸药业股份有限公司",
              "manufacturerCode": "60acf15d-1fe8-42b7-a8e3-b2a4d2780239",
              "hospital": "上海市长宁区北新泾街道社区卫生服务中心",
              "hospitalCode": "YL678118",
              "drug": "维生素D2软胶囊",
              "drugCode": "XA11CCW047E002010301564",
              "riskProbability": "70.5%",
              "riskProbabilityValue": 0.70453,
              "windowConsumption": "¥748,250",
              "businessScore": "¥527,164",
              "lastPurchase": "2024-06-24",
              "daysSinceLastAtReport": "129 天",
              "noPurchaseAfterReport": "92 天",
              "noPurchaseFromLast": "221 天",
              "observedAmount": "¥2,993,000",
              "demandShape": "smooth",
              "outcome": "验证窗口内 0 次续购，3月流失命中。",
              "caseSummary": "月报日后至验证窗口闭合保持 0 次采购记录，高价值风险提前进入复盘清单。",
              "evidence": [
                  "月报日前 12 个月已形成 ¥2,993,000 的采购规模。",
                  "2024-10-31 输出风险概率 70.5%，损失价值 ¥527,164。",
                  "从月报日到 2025-01-31 连续 92 天未续购；从上次采购到闭合累计 221 天。"
              ]
          },
          {
              "id": "hit_202410_h3_04",
              "title": "2024-10 月报命中：沈阳二四二医院 × 盘龙七片",
              "visible": "命中确认",
              "reportDate": "2024-10-31",
              "validationEnd": "2025-01-31",
              "horizon": "H3",
              "horizonLabel": "3月风险",
              "manufacturer": "陕西盘龙药业集团股份有限公司",
              "manufacturerCode": "1D93E15EBB9B4F14A1C18E0CD1750A0A",
              "hospital": "沈阳二四二医院",
              "hospitalCode": "YL210826",
              "drug": "盘龙七片",
              "drugCode": "ZA16DAP0017010402404",
              "riskProbability": "57.7%",
              "riskProbabilityValue": 0.57713,
              "windowConsumption": "¥750,840",
              "businessScore": "¥433,332",
              "lastPurchase": "2024-06-14",
              "daysSinceLastAtReport": "138 天",
              "noPurchaseAfterReport": "92 天",
              "noPurchaseFromLast": "230 天",
              "observedAmount": "¥3,003,360",
              "demandShape": "erratic",
              "outcome": "验证窗口内 0 次续购，3月流失命中。",
              "caseSummary": "月报日后至验证窗口闭合保持 0 次采购记录，高价值风险提前进入复盘清单。",
              "evidence": [
                  "月报日前 12 个月已形成 ¥3,003,360 的采购规模。",
                  "2024-10-31 输出风险概率 57.7%，损失价值 ¥433,332。",
                  "从月报日到 2025-01-31 连续 92 天未续购；从上次采购到闭合累计 230 天。"
              ]
          },
          {
              "id": "hit_202410_h3_05",
              "title": "2024-10 月报命中：杨凌示范区医院 × 盘龙七片",
              "visible": "命中确认",
              "reportDate": "2024-10-31",
              "validationEnd": "2025-01-31",
              "horizon": "H3",
              "horizonLabel": "3月风险",
              "manufacturer": "陕西盘龙药业集团股份有限公司",
              "manufacturerCode": "1D93E15EBB9B4F14A1C18E0CD1750A0A",
              "hospital": "杨凌示范区医院",
              "hospitalCode": "YL612259",
              "drug": "盘龙七片",
              "drugCode": "ZA16DAP0017010402404",
              "riskProbability": "69.8%",
              "riskProbabilityValue": 0.6977,
              "windowConsumption": "¥563,121",
              "businessScore": "¥392,889",
              "lastPurchase": "2024-04-29",
              "daysSinceLastAtReport": "184 天",
              "noPurchaseAfterReport": "92 天",
              "noPurchaseFromLast": "276 天",
              "observedAmount": "¥2,252,484",
              "demandShape": "intermittent",
              "outcome": "验证窗口内 0 次续购，3月流失命中。",
              "caseSummary": "月报日后至验证窗口闭合保持 0 次采购记录，高价值风险提前进入复盘清单。",
              "evidence": [
                  "月报日前 12 个月已形成 ¥2,252,484 的采购规模。",
                  "2024-10-31 输出风险概率 69.8%，损失价值 ¥392,889。",
                  "从月报日到 2025-01-31 连续 92 天未续购；从上次采购到闭合累计 276 天。"
              ]
          },
          {
              "id": "hit_202410_h3_06",
              "title": "2024-10 月报命中：方城县赵河镇卫生院 × 盐酸倍他司汀注射液",
              "visible": "命中确认",
              "reportDate": "2024-10-31",
              "validationEnd": "2025-01-31",
              "horizon": "H3",
              "horizonLabel": "3月风险",
              "manufacturer": "哈药集团三精制药有限公司",
              "manufacturerCode": "9701EFF559DF4862AF18CF0DC1B6962D",
              "hospital": "方城县赵河镇卫生院",
              "hospitalCode": "YL411607",
              "drug": "盐酸倍他司汀注射液",
              "drugCode": "e55aab9b3ee754a3580eded051caa1c2",
              "riskProbability": "60.9%",
              "riskProbabilityValue": 0.608818,
              "windowConsumption": "¥628,050",
              "businessScore": "¥382,368",
              "lastPurchase": "2024-07-29",
              "daysSinceLastAtReport": "93 天",
              "noPurchaseAfterReport": "92 天",
              "noPurchaseFromLast": "185 天",
              "observedAmount": "¥2,512,200",
              "demandShape": "intermittent",
              "outcome": "验证窗口内 0 次续购，3月流失命中。",
              "caseSummary": "月报日后至验证窗口闭合保持 0 次采购记录，高价值风险提前进入复盘清单。",
              "evidence": [
                  "月报日前 12 个月已形成 ¥2,512,200 的采购规模。",
                  "2024-10-31 输出风险概率 60.9%，损失价值 ¥382,368。",
                  "从月报日到 2025-01-31 连续 92 天未续购；从上次采购到闭合累计 185 天。"
              ]
          }
      ]
  },
  H6: {
      "horizon": "H6",
      "label": "6月风险",
      "reportMonth": "2024-10",
      "reportDate": "2024-10-31",
      "validationEnd": "2025-04-30",
      "validationDays": "181 天",
      "ece": "0.022",
      "subtitle": "月报主视角闭合验证",
      "narrative": "以 2024-10-31 月报为起点，主干模型识别出高概率、高价值流失对象；到 2025-04-30 验证窗口闭合时，入选案例在窗口内保持 0 次续购，展示产品提前识别高价值风险的能力。",
      "cases": [
          {
              "id": "hit_202410_h6_01",
              "title": "2024-10 月报命中：平煤神马医疗集团总医院 × 盐酸倍他司汀注射液",
              "visible": "命中确认",
              "reportDate": "2024-10-31",
              "validationEnd": "2025-04-30",
              "horizon": "H6",
              "horizonLabel": "6月风险",
              "manufacturer": "哈药集团三精制药有限公司",
              "manufacturerCode": "9701EFF559DF4862AF18CF0DC1B6962D",
              "hospital": "平煤神马医疗集团总医院",
              "hospitalCode": "YL415576",
              "drug": "盐酸倍他司汀注射液",
              "drugCode": "e55aab9b3ee754a3580eded051caa1c2",
              "riskProbability": "65.8%",
              "riskProbabilityValue": 0.657804,
              "windowConsumption": "¥2,628,922",
              "businessScore": "¥1,729,315",
              "lastPurchase": "2024-05-31",
              "daysSinceLastAtReport": "152 天",
              "noPurchaseAfterReport": "181 天",
              "noPurchaseFromLast": "333 天",
              "observedAmount": "¥5,257,845",
              "demandShape": "intermittent",
              "outcome": "验证窗口内 0 次续购，6月流失命中。",
              "caseSummary": "月报日后至验证窗口闭合保持 0 次采购记录，高价值风险提前进入复盘清单。",
              "evidence": [
                  "月报日前 12 个月已形成 ¥5,257,845 的采购规模。",
                  "2024-10-31 输出风险概率 65.8%，损失价值 ¥1,729,315。",
                  "从月报日到 2025-04-30 连续 181 天未续购；从上次采购到闭合累计 333 天。"
              ]
          },
          {
              "id": "hit_202410_h6_02",
              "title": "2024-10 月报命中：上海市长宁区北新泾街道社区卫生服务中心 × 维生素D2软胶囊",
              "visible": "命中确认",
              "reportDate": "2024-10-31",
              "validationEnd": "2025-04-30",
              "horizon": "H6",
              "horizonLabel": "6月风险",
              "manufacturer": "南京海鲸药业股份有限公司",
              "manufacturerCode": "60acf15d-1fe8-42b7-a8e3-b2a4d2780239",
              "hospital": "上海市长宁区北新泾街道社区卫生服务中心",
              "hospitalCode": "YL678118",
              "drug": "维生素D2软胶囊",
              "drugCode": "XA11CCW047E002010301564",
              "riskProbability": "66.8%",
              "riskProbabilityValue": 0.668055,
              "windowConsumption": "¥1,496,500",
              "businessScore": "¥999,744",
              "lastPurchase": "2024-06-24",
              "daysSinceLastAtReport": "129 天",
              "noPurchaseAfterReport": "181 天",
              "noPurchaseFromLast": "310 天",
              "observedAmount": "¥2,993,000",
              "demandShape": "smooth",
              "outcome": "验证窗口内 0 次续购，6月流失命中。",
              "caseSummary": "月报日后至验证窗口闭合保持 0 次采购记录，高价值风险提前进入复盘清单。",
              "evidence": [
                  "月报日前 12 个月已形成 ¥2,993,000 的采购规模。",
                  "2024-10-31 输出风险概率 66.8%，损失价值 ¥999,744。",
                  "从月报日到 2025-04-30 连续 181 天未续购；从上次采购到闭合累计 310 天。"
              ]
          },
          {
              "id": "hit_202410_h6_03",
              "title": "2024-10 月报命中：沈阳二四二医院 × 盘龙七片",
              "visible": "命中确认",
              "reportDate": "2024-10-31",
              "validationEnd": "2025-04-30",
              "horizon": "H6",
              "horizonLabel": "6月风险",
              "manufacturer": "陕西盘龙药业集团股份有限公司",
              "manufacturerCode": "1D93E15EBB9B4F14A1C18E0CD1750A0A",
              "hospital": "沈阳二四二医院",
              "hospitalCode": "YL210826",
              "drug": "盘龙七片",
              "drugCode": "ZA16DAP0017010402404",
              "riskProbability": "56.6%",
              "riskProbabilityValue": 0.56591,
              "windowConsumption": "¥1,501,680",
              "businessScore": "¥849,815",
              "lastPurchase": "2024-06-14",
              "daysSinceLastAtReport": "138 天",
              "noPurchaseAfterReport": "181 天",
              "noPurchaseFromLast": "319 天",
              "observedAmount": "¥3,003,360",
              "demandShape": "erratic",
              "outcome": "验证窗口内 0 次续购，6月流失命中。",
              "caseSummary": "月报日后至验证窗口闭合保持 0 次采购记录，高价值风险提前进入复盘清单。",
              "evidence": [
                  "月报日前 12 个月已形成 ¥3,003,360 的采购规模。",
                  "2024-10-31 输出风险概率 56.6%，损失价值 ¥849,815。",
                  "从月报日到 2025-04-30 连续 181 天未续购；从上次采购到闭合累计 319 天。"
              ]
          },
          {
              "id": "hit_202410_h6_04",
              "title": "2024-10 月报命中：方城县赵河镇卫生院 × 盐酸倍他司汀注射液",
              "visible": "命中确认",
              "reportDate": "2024-10-31",
              "validationEnd": "2025-04-30",
              "horizon": "H6",
              "horizonLabel": "6月风险",
              "manufacturer": "哈药集团三精制药有限公司",
              "manufacturerCode": "9701EFF559DF4862AF18CF0DC1B6962D",
              "hospital": "方城县赵河镇卫生院",
              "hospitalCode": "YL411607",
              "drug": "盐酸倍他司汀注射液",
              "drugCode": "e55aab9b3ee754a3580eded051caa1c2",
              "riskProbability": "58.6%",
              "riskProbabilityValue": 0.585645,
              "windowConsumption": "¥1,256,100",
              "businessScore": "¥735,628",
              "lastPurchase": "2024-07-29",
              "daysSinceLastAtReport": "93 天",
              "noPurchaseAfterReport": "181 天",
              "noPurchaseFromLast": "274 天",
              "observedAmount": "¥2,512,200",
              "demandShape": "intermittent",
              "outcome": "验证窗口内 0 次续购，6月流失命中。",
              "caseSummary": "月报日后至验证窗口闭合保持 0 次采购记录，高价值风险提前进入复盘清单。",
              "evidence": [
                  "月报日前 12 个月已形成 ¥2,512,200 的采购规模。",
                  "2024-10-31 输出风险概率 58.6%，损失价值 ¥735,628。",
                  "从月报日到 2025-04-30 连续 181 天未续购；从上次采购到闭合累计 274 天。"
              ]
          },
          {
              "id": "hit_202410_h6_05",
              "title": "2024-10 月报命中：杨凌示范区医院 × 盘龙七片",
              "visible": "命中确认",
              "reportDate": "2024-10-31",
              "validationEnd": "2025-04-30",
              "horizon": "H6",
              "horizonLabel": "6月风险",
              "manufacturer": "陕西盘龙药业集团股份有限公司",
              "manufacturerCode": "1D93E15EBB9B4F14A1C18E0CD1750A0A",
              "hospital": "杨凌示范区医院",
              "hospitalCode": "YL612259",
              "drug": "盘龙七片",
              "drugCode": "ZA16DAP0017010402404",
              "riskProbability": "57.2%",
              "riskProbabilityValue": 0.571977,
              "windowConsumption": "¥1,126,242",
              "businessScore": "¥644,184",
              "lastPurchase": "2024-04-29",
              "daysSinceLastAtReport": "184 天",
              "noPurchaseAfterReport": "181 天",
              "noPurchaseFromLast": "365 天",
              "observedAmount": "¥2,252,484",
              "demandShape": "intermittent",
              "outcome": "验证窗口内 0 次续购，6月流失命中。",
              "caseSummary": "月报日后至验证窗口闭合保持 0 次采购记录，高价值风险提前进入复盘清单。",
              "evidence": [
                  "月报日前 12 个月已形成 ¥2,252,484 的采购规模。",
                  "2024-10-31 输出风险概率 57.2%，损失价值 ¥644,184。",
                  "从月报日到 2025-04-30 连续 181 天未续购；从上次采购到闭合累计 365 天。"
              ]
          },
          {
              "id": "hit_202410_h6_06",
              "title": "2024-10 月报命中：丹东市人民医院 × 盘龙七片",
              "visible": "命中确认",
              "reportDate": "2024-10-31",
              "validationEnd": "2025-04-30",
              "horizon": "H6",
              "horizonLabel": "6月风险",
              "manufacturer": "陕西盘龙药业集团股份有限公司",
              "manufacturerCode": "1D93E15EBB9B4F14A1C18E0CD1750A0A",
              "hospital": "丹东市人民医院",
              "hospitalCode": "YL211026",
              "drug": "盘龙七片",
              "drugCode": "ZA16DAP0017010402404",
              "riskProbability": "71.0%",
              "riskProbabilityValue": 0.710065,
              "windowConsumption": "¥779,742",
              "businessScore": "¥553,668",
              "lastPurchase": "2024-02-01",
              "daysSinceLastAtReport": "272 天",
              "noPurchaseAfterReport": "181 天",
              "noPurchaseFromLast": "453 天",
              "observedAmount": "¥1,559,484",
              "demandShape": "intermittent",
              "outcome": "验证窗口内 0 次续购，6月流失命中。",
              "caseSummary": "月报日后至验证窗口闭合保持 0 次采购记录，高价值风险提前进入复盘清单。",
              "evidence": [
                  "月报日前 12 个月已形成 ¥1,559,484 的采购规模。",
                  "2024-10-31 输出风险概率 71.0%，损失价值 ¥553,668。",
                  "从月报日到 2025-04-30 连续 181 天未续购；从上次采购到闭合累计 453 天。"
              ]
          }
      ]
  },
  H12: {
      "horizon": "H12",
      "label": "12月风险",
      "reportMonth": "2025-01",
      "reportDate": "2025-01-31",
      "validationEnd": "2026-01-31",
      "validationDays": "365 天",
      "ece": "0.023",
      "subtitle": "长窗价值闭合验证",
      "narrative": "以 2025-01-31 月报为起点，主干模型识别出高概率、高价值流失对象；到 2026-01-31 验证窗口闭合时，入选案例在窗口内保持 0 次续购，展示产品提前识别高价值风险的能力。",
      "cases": [
          {
              "id": "hit_202501_h12_01",
              "title": "2025-01 月报命中：深圳市南山区人民医院 × 维生素D2软胶囊",
              "visible": "命中确认",
              "reportDate": "2025-01-31",
              "validationEnd": "2026-01-31",
              "horizon": "H12",
              "horizonLabel": "12月风险",
              "manufacturer": "南京海鲸药业股份有限公司",
              "manufacturerCode": "60acf15d-1fe8-42b7-a8e3-b2a4d2780239",
              "hospital": "深圳市南山区人民医院",
              "hospitalCode": "YL440881",
              "drug": "维生素D2软胶囊",
              "drugCode": "XA11CCW047E002010301564",
              "riskProbability": "89.5%",
              "riskProbabilityValue": 0.895022,
              "windowConsumption": "¥7,093,000",
              "businessScore": "¥6,348,389",
              "lastPurchase": "2024-08-13",
              "daysSinceLastAtReport": "170 天",
              "noPurchaseAfterReport": "365 天",
              "noPurchaseFromLast": "535 天",
              "observedAmount": "¥7,093,000",
              "demandShape": "smooth",
              "outcome": "验证窗口内 0 次续购，12月流失命中。",
              "caseSummary": "月报日后至验证窗口闭合保持 0 次采购记录，高价值风险提前进入复盘清单。",
              "evidence": [
                  "月报日前 12 个月已形成 ¥7,093,000 的采购规模。",
                  "2025-01-31 输出风险概率 89.5%，损失价值 ¥6,348,389。",
                  "从月报日到 2026-01-31 连续 365 天未续购；从上次采购到闭合累计 535 天。"
              ]
          },
          {
              "id": "hit_202501_h12_02",
              "title": "2025-01 月报命中：平煤神马医疗集团总医院 × 盐酸倍他司汀注射液",
              "visible": "命中确认",
              "reportDate": "2025-01-31",
              "validationEnd": "2026-01-31",
              "horizon": "H12",
              "horizonLabel": "12月风险",
              "manufacturer": "哈药集团三精制药有限公司",
              "manufacturerCode": "9701EFF559DF4862AF18CF0DC1B6962D",
              "hospital": "平煤神马医疗集团总医院",
              "hospitalCode": "YL415576",
              "drug": "盐酸倍他司汀注射液",
              "drugCode": "e55aab9b3ee754a3580eded051caa1c2",
              "riskProbability": "71.1%",
              "riskProbabilityValue": 0.711176,
              "windowConsumption": "¥3,978,045",
              "businessScore": "¥2,829,090",
              "lastPurchase": "2024-05-31",
              "daysSinceLastAtReport": "244 天",
              "noPurchaseAfterReport": "365 天",
              "noPurchaseFromLast": "609 天",
              "observedAmount": "¥3,978,045",
              "demandShape": "intermittent",
              "outcome": "验证窗口内 0 次续购，12月流失命中。",
              "caseSummary": "月报日后至验证窗口闭合保持 0 次采购记录，高价值风险提前进入复盘清单。",
              "evidence": [
                  "月报日前 12 个月已形成 ¥3,978,045 的采购规模。",
                  "2025-01-31 输出风险概率 71.1%，损失价值 ¥2,829,090。",
                  "从月报日到 2026-01-31 连续 365 天未续购；从上次采购到闭合累计 609 天。"
              ]
          },
          {
              "id": "hit_202501_h12_03",
              "title": "2025-01 月报命中：上海市长宁区北新泾街道社区卫生服务中心 × 维生素D2软胶囊",
              "visible": "命中确认",
              "reportDate": "2025-01-31",
              "validationEnd": "2026-01-31",
              "horizon": "H12",
              "horizonLabel": "12月风险",
              "manufacturer": "南京海鲸药业股份有限公司",
              "manufacturerCode": "60acf15d-1fe8-42b7-a8e3-b2a4d2780239",
              "hospital": "上海市长宁区北新泾街道社区卫生服务中心",
              "hospitalCode": "YL678118",
              "drug": "维生素D2软胶囊",
              "drugCode": "XA11CCW047E002010301564",
              "riskProbability": "80.1%",
              "riskProbabilityValue": 0.801222,
              "windowConsumption": "¥1,927,000",
              "businessScore": "¥1,543,955",
              "lastPurchase": "2024-06-24",
              "daysSinceLastAtReport": "221 天",
              "noPurchaseAfterReport": "365 天",
              "noPurchaseFromLast": "586 天",
              "observedAmount": "¥1,927,000",
              "demandShape": "intermittent",
              "outcome": "验证窗口内 0 次续购，12月流失命中。",
              "caseSummary": "月报日后至验证窗口闭合保持 0 次采购记录，高价值风险提前进入复盘清单。",
              "evidence": [
                  "月报日前 12 个月已形成 ¥1,927,000 的采购规模。",
                  "2025-01-31 输出风险概率 80.1%，损失价值 ¥1,543,955。",
                  "从月报日到 2026-01-31 连续 365 天未续购；从上次采购到闭合累计 586 天。"
              ]
          },
          {
              "id": "hit_202501_h12_04",
              "title": "2025-01 月报命中：方城县赵河镇卫生院 × 盐酸倍他司汀注射液",
              "visible": "命中确认",
              "reportDate": "2025-01-31",
              "validationEnd": "2026-01-31",
              "horizon": "H12",
              "horizonLabel": "12月风险",
              "manufacturer": "哈药集团三精制药有限公司",
              "manufacturerCode": "9701EFF559DF4862AF18CF0DC1B6962D",
              "hospital": "方城县赵河镇卫生院",
              "hospitalCode": "YL411607",
              "drug": "盐酸倍他司汀注射液",
              "drugCode": "e55aab9b3ee754a3580eded051caa1c2",
              "riskProbability": "74.4%",
              "riskProbabilityValue": 0.743722,
              "windowConsumption": "¥1,943,400",
              "businessScore": "¥1,445,349",
              "lastPurchase": "2024-07-29",
              "daysSinceLastAtReport": "185 天",
              "noPurchaseAfterReport": "365 天",
              "noPurchaseFromLast": "550 天",
              "observedAmount": "¥1,943,400",
              "demandShape": "intermittent",
              "outcome": "验证窗口内 0 次续购，12月流失命中。",
              "caseSummary": "月报日后至验证窗口闭合保持 0 次采购记录，高价值风险提前进入复盘清单。",
              "evidence": [
                  "月报日前 12 个月已形成 ¥1,943,400 的采购规模。",
                  "2025-01-31 输出风险概率 74.4%，损失价值 ¥1,445,349。",
                  "从月报日到 2026-01-31 连续 365 天未续购；从上次采购到闭合累计 550 天。"
              ]
          },
          {
              "id": "hit_202501_h12_05",
              "title": "2025-01 月报命中：沈阳二四二医院 × 盘龙七片",
              "visible": "命中确认",
              "reportDate": "2025-01-31",
              "validationEnd": "2026-01-31",
              "horizon": "H12",
              "horizonLabel": "12月风险",
              "manufacturer": "陕西盘龙药业集团股份有限公司",
              "manufacturerCode": "1D93E15EBB9B4F14A1C18E0CD1750A0A",
              "hospital": "沈阳二四二医院",
              "hospitalCode": "YL210826",
              "drug": "盘龙七片",
              "drugCode": "ZA16DAP0017010402404",
              "riskProbability": "72.0%",
              "riskProbabilityValue": 0.719532,
              "windowConsumption": "¥1,790,436",
              "businessScore": "¥1,288,275",
              "lastPurchase": "2024-06-14",
              "daysSinceLastAtReport": "230 天",
              "noPurchaseAfterReport": "365 天",
              "noPurchaseFromLast": "595 天",
              "observedAmount": "¥1,790,436",
              "demandShape": "erratic",
              "outcome": "验证窗口内 0 次续购，12月流失命中。",
              "caseSummary": "月报日后至验证窗口闭合保持 0 次采购记录，高价值风险提前进入复盘清单。",
              "evidence": [
                  "月报日前 12 个月已形成 ¥1,790,436 的采购规模。",
                  "2025-01-31 输出风险概率 72.0%，损失价值 ¥1,288,275。",
                  "从月报日到 2026-01-31 连续 365 天未续购；从上次采购到闭合累计 595 天。"
              ]
          },
          {
              "id": "hit_202501_h12_06",
              "title": "2025-01 月报命中：河南信合医院 × 盐酸倍他司汀注射液",
              "visible": "命中确认",
              "reportDate": "2025-01-31",
              "validationEnd": "2026-01-31",
              "horizon": "H12",
              "horizonLabel": "12月风险",
              "manufacturer": "哈药集团三精制药有限公司",
              "manufacturerCode": "9701EFF559DF4862AF18CF0DC1B6962D",
              "hospital": "河南信合医院",
              "hospitalCode": "YL411465",
              "drug": "盐酸倍他司汀注射液",
              "drugCode": "e55aab9b3ee754a3580eded051caa1c2",
              "riskProbability": "61.7%",
              "riskProbabilityValue": 0.616503,
              "windowConsumption": "¥1,777,500",
              "businessScore": "¥1,095,834",
              "lastPurchase": "2024-09-11",
              "daysSinceLastAtReport": "141 天",
              "noPurchaseAfterReport": "365 天",
              "noPurchaseFromLast": "506 天",
              "observedAmount": "¥1,777,500",
              "demandShape": "cold_start",
              "outcome": "验证窗口内 0 次续购，12月流失命中。",
              "caseSummary": "月报日后至验证窗口闭合保持 0 次采购记录，高价值风险提前进入复盘清单。",
              "evidence": [
                  "月报日前 12 个月已形成 ¥1,777,500 的采购规模。",
                  "2025-01-31 输出风险概率 61.7%，损失价值 ¥1,095,834。",
                  "从月报日到 2026-01-31 连续 365 天未续购；从上次采购到闭合累计 506 天。"
              ]
          }
      ]
  }
}

export const proofCases = proofCaseHorizonSets.H6.cases
