export const architectureStages = [
  {
    id: 'S1',
    title: '数据接入与规范化',
    summary: '隔离真实数据源差异，算法只依赖 canonical schema。',
    nodes: [
      { id: 'A', title: '数据源', status: 'reserved', text: '业务库、CSV、Excel、未来 API' },
      { id: 'B', title: 'Adapter', status: 'live', text: '当前 CSVAdapter / Mock 已接通' },
      { id: 'C', title: 'Canonical Schema', status: 'live', text: 'Drug / Org / Order / ProductLineMapping' },
      { id: 'D', title: '标准视图 / 聚合视图', status: 'partial', text: 'ViewBuilder 已预留 MySQL 视图模板' }
    ]
  },
  {
    id: 'S2',
    title: '特征工程',
    summary: '按 as_of_date 切窗，生成可回测、可复现的特征快照。',
    nodes: [
      { id: 'E', title: 'Preprocessor Registry', status: 'reserved', text: '为不同算法预留不同预处理链' },
      { id: 'F', title: 'Feature Store', status: 'reserved', text: '后续沉淀训练/服务一致特征' },
      { id: 'G', title: 'Feature Snapshot', status: 'live', text: 'recent / baseline / demand shape' }
    ]
  },
  {
    id: 'S3',
    title: '算法检测',
    summary: 'Detector 并行运行，新增算法只需注册并输出统一 DetectorResult。',
    nodes: [
      { id: 'H', title: 'Detector Registry', status: 'partial', text: 'v0 以服务层显式编排，后续注册化' },
      { id: 'I', title: 'Detector Result', status: 'live', text: 'hit / severity / confidence / reason_code' }
    ]
  },
  {
    id: 'S4',
    title: '线索生成',
    summary: '将多路 detector 输出融合为结构化风险线索和证据链。',
    nodes: [
      { id: 'J', title: 'Fusion', status: 'live', text: '规则融合，暂不接机器学习' },
      { id: 'K', title: 'Evidence Builder', status: 'live', text: '保留 metrics 与 order_refs' },
      { id: 'L', title: 'RiskClue', status: 'live', text: 'red / orange / yellow / none' }
    ]
  },
  {
    id: 'S5',
    title: '服务接口',
    summary: '对外暴露调试、dry-run、配置查看和回测入口。',
    nodes: [
      { id: 'M', title: 'Inspection Service', status: 'live', text: '巡检编排服务' },
      { id: 'N', title: 'Debug API', status: 'live', text: '数据质量、单单元调试' },
      { id: 'O', title: 'Dry-run API', status: 'live', text: '全量巡检预演' },
      { id: 'P', title: 'Backtest API', status: 'live', text: 'walk-forward skeleton' }
    ]
  }
]

export const architectureEdges = [
  '数据源 → Adapter → Canonical Schema → 标准视图',
  '标准视图 → 预处理 → 特征快照',
  '特征快照 → 并行 Detector → DetectorResult',
  'DetectorResult → Fusion → Evidence → RiskClue',
  'RiskClue → Inspection Service → Debug / Dry-run / Backtest API'
]

export const statusLabels = {
  live: '已接入',
  partial: '部分预留',
  reserved: '待接入'
}
