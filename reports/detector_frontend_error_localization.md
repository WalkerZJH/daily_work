# Detector 前端问题端到端定位

本报告基于当前源码、2026-01-01 稳定 API、2025-12 稳定月度 display lookup 和示例实体：

- `manufacturer_code=DFC52F4CCF384D849D053242EA2935F3`
- `hospital_code=YL221606`
- `drug_code/drug_group=ZA12AAN0014010203711`
- `observation_date=2026-01-01`

稳定 lookup 的实际名称为：生产企业“哈药集团制药六厂”、医院“吉林省前卫医院”、药品“脑安片”，质量为 `master`。该实体当天有 3 个 Detector 命中：`purchase_frequency_drop`、`purchase_interval_ipi`、`purchase_quantity_trend`。

## 1. 医院名称缺失

**现象**：clues API 和页面显示 `YL221606`。  
**预期**：显示“吉林省前卫医院”。  
**数据链**：稳定 `entity_display_lookup.parquet` 有名称 → `CompositeDetectorResultRepository` 返回空 lookup → `_merge_entity_display_lookup` 看到空表后原样返回 clue → `_clue_item` 以 code 回退 `hospital_name` → mapper 正确展示收到的 `hospital_name`。  
**第一个错误层**：repository/display lookup。  
**直接原因**：`risk_model_core/repositories.py::CompositeDetectorResultRepository.load_entity_display_lookup` 固定返回空 DataFrame。  
**证据文件/函数**：`risk_model_core/repositories.py`、`project/app/services/detector_result_service.py::_merge_entity_display_lookup/_clue_item`、`front_end/src/modules/monthly-demo/pageDataAdapter.js::mapDailyRuleClue`。  
**最小修复方案**：让 observation context 同时持有对应 previous-complete-month 的月度 repository，并由 composite Detector repository/服务委托其 `load_entity_display_lookup(report_month)`；加入真实 composite repository 回归测试。不要在前端硬编码。  
**优先级**：P0。

## 2. 药品名称缺失

**现象**：显示 `ZA12AAN0014010203711`。  
**预期**：显示“脑安片”。  
**数据链**：lookup 的 `drug_code=drug_group=ZA12...` 且 `drug_display_name=脑安片`；join key 完全一致，但 lookup 在 composite repository 层被置空；API 回退 `drug_group`。  
**第一个错误层**：repository/display lookup。  
**直接原因**：同上，不是 `drug_code`/`drug_group` 错配、类型错误或前导零丢失。  
**证据文件/函数**：同上；稳定 lookup 精确行验证。  
**最小修复方案**：从同一不可变 `daily_detector_results.detector_result_id` 精确取得 `drug_code`，再使用 `tenant_id, report_month, manufacturer_code, hospital_code, drug_code` 连接精确月度 lookup；不得将遗留 `drug_group` 当作 `drug_code`。
**优先级**：P0。

## 3. 生产企业名称缺失

**现象**：clue 行显示企业编码；但 `/api/v1/my/manufacturers` 已能返回企业名称。  
**预期**：clue API 返回“哈药集团制药六厂”。  
**数据链**：企业目录 API 有名称；月度 display lookup 也有名称；Detector composite lookup 为空；`_clue_item` 回退 manufacturer_code；前端 `resolveManufacturerPresentation` 只能展示收到的 code。  
**第一个错误层**：Detector repository/display lookup，而非全局企业目录。  
**直接原因**：Detector clue enrichment 没有复用月度 lookup/企业目录。  
**证据文件/函数**：`CompositeDetectorResultRepository.load_entity_display_lookup`、`DetectorResultService.clues`、`mapDailyRuleClue`、`manufacturerScope.js`。  
**最小修复方案**：统一 Detector clue enrichment 与 display-lookup status 使用同一上下文 repository；不得仅在 Vue 中查表替换。  
**优先级**：P0。

## 4. clues 美化未完成

**现象**：筛选区和视觉层级未达到设计预期。  
**预期**：完整筛选工作流、清晰状态、密度与响应式布局。  
**数据链**：Vue state → adapter query → API → table/cards/SCSS。  
**第一个错误层**：不存在单一功能断点；主要是验收基线缺失与视觉完成度问题。  
**直接原因**：设计文档实际位于 `daily_work/notes/new_ver/前端美化/clues页面美化策略（待实现）.md`；初次检索遗漏了 `daily_work` 这一层。文档随后已完整读取，并作为 Release B 卡片筛选的实现与验收基线。  
**证据文件/函数**：`RiskEntityListView.vue`、`pageDataAdapter.js::loadRuleCluesData`、`front_end/src/styles/library/_modules.scss`。  
**最小修复方案**：按已确认设计文档完成卡片交互与视觉验收；不删除结果列表，也不改造成候选排名页。  
**优先级**：P2。

### 功能/视觉对照矩阵

| 美化策略要求 | 当前是否实现 | 代码位置 | 差距/分类 |
|---|---|---|---|
| draftFilters/appliedFilters | 是 | RiskEntityListView.vue | 无，functional complete |
| 应用后一次查询 | 是 | `applyFilters/loadPage` | 并发加载 context/options/data，非逐控件请求 |
| 重置 | 是 | `resetFilters` | 无 |
| 规则大类/小类 | 是 | category/id selects | 中文小类受 catalog 英文名影响，functional incomplete |
| 命中等级 | 是 | detectorLevel | API 参数名不是 severity，contract partial |
| 排序字段/方向 | 是 | sortBy/sortOrder | 无 |
| 每页条数 | 是 | pageSize 20/50/100 | 无 |
| 已应用条件摘要 | 是 | `appliedSummary` | 总数口径说明不足，functional incomplete |
| 加载/错误/空状态 | 是 | template state branches | 无 |
| 分页 | 是 | `goToPage/pagination` | 无 |
| 中文名称 | 部分 | mapper/catalog | Detector 小类仍英文，functional blocker |
| 响应式布局 | 是 | Vue + `_modules.scss` | 可继续视觉优化 |
| 表格信息密度 | 部分 | table/template | visual incomplete |
| 操作按钮 | 是 | “查看线索详情” | 目标详情语义不完整，functional blocker |
| 视觉层级 | 部分 | batch/filter/table cards | visual incomplete/cosmetic |

## 5. 12350 与 7069 统计差异

**现象**：顶部 12350，已应用结果 7069。  
**预期**：若口径不同，应明确标注；若无筛选且无重复，应相等。  
**数据链**：顶部 `getDailyDetectorStatus → status.clue_count → normalizeDailyRuleStatus → dailyDetectorStatus.clueCount`；列表 `getDailyDetectorClues → clues.total/pagination.total → mapDailyRuleCluesPayload → appliedSummary`。  
**第一个错误层**：不是数据计算错误，而是 summary/list 的契约口径与 UI 标签层。  
**直接原因**：status 对企业/日期的原始 clue 行直接计数，不接受 category/id/level 且不去重；list 应用筛选、hit-only 和 clue-id 去重。  
**证据文件/函数**：`DetectorResultService.status/clues/_deduplicate_clues`、`loadRuleCluesData`、`RiskEntityListView.vue`。  
**最小修复方案**：统一统计契约或明确标注“筛选前全部命中行”与“筛选后去重结果”；保留分页 total。  
**优先级**：P1。  
**结论**：`expected_semantic_difference`。稳定 2026-01-01 的无额外筛选样例中两者均为 4488。

## 6. Detector 英文名称

**现象**：显示 `Purchase frequency drop`。  
**预期**：稳定中文名，例如“采购频次衰减/下降”。  
**数据链**：`detector_catalog.detector_name`（英文）→ service `detector_name_label`（原样）→ adapter 优先 `detector_name_label` → Vue 展示。  
**第一个错误层**：catalog/schema contract。  
**直接原因**：catalog 没有 `detector_name_zh`；`daily_detector_runner.ROOT_CAUSE_LABELS` 虽有中文，但它是命中原因，不是稳定显示名，未用于 catalog。  
**证据文件/函数**：`risk_algorithm_core/detector_catalog.py`、`daily_detector_runner.py::ROOT_CAUSE_LABELS`、`DetectorResultService._clue_item`、`mapDailyRuleClue`。  
**最小修复方案**：在 catalog 增加 10 个版本化 `detector_name_zh`，后端 schema/API 显式返回；前端优先 zh、再英文、最后 id。未知 Detector 使用英文或 id fallback，不做字符串临时替换。  
**优先级**：P1。

## 7. clue-detail 未展示实体全部命中证据

**现象**：从列表点击后只展示被点击的一条 Detector；示例实体实际上有 3 条当日命中。  
**预期**：以 `manufacturer_code × hospital_code × drug_code × observation_date` 为单位展示全部当前命中；有月度候选则关联概率，无则明确“未纳入当前月度概率预测集”。  
**数据链**：`detailHref` 仅写 `clueId` → App 选择 rule-only mode → `loadRuleOnlyClueDetailData` → GET `/detectors/clues/{clueId}` → service `get_daily_detector_clue_by_id` → 单条组件。  
**第一个错误层**：列表 route/query 设计；其后 API 也缺 entity-key all-hits detail。  
**直接原因**：rule-only 合同被设计为单条 clue；Detector-only entity 没有 riskEntityId，无法转入 candidate detail 的 evidence API。`risk_entity_id/entity_id/clue_id/detector_result_id` 在此没有被误混用，而是缺少新的实体详情契约。  
**受影响组件**：`RiskEntityListView.vue::detailHref`、`App.vue` 模式选择、`pageDataAdapter.js::loadRuleOnlyClueDetailData`、`RiskEntityDetailView.vue`、`routes_detector_results.py`。  
**证据文件/函数**：上述文件；GET 实证显示 3 个 detector ids，单 clue GET 只返回 frequency_drop。  
**最小修复方案**：新增明确的 Detector entity detail route/API，参数为 manufacturer/hospital/drug/observation_date，返回同日全部 hit evaluations；列表传完整实体键。若同时传 clueId，可将其作为默认展开项。保持 rule-only 不伪造月度概率；月度结果缺失时显示 `--` 与“未纳入当前月度概率预测集”。  
**优先级**：P1。

补充：当前磁盘源码的 `clue_detail` 已尝试附加 `evaluation`，对应单条结果的 current/baseline/comparison/threshold/config 字段；但 09:58 启动的 live server 未加载当日下午源码，实际 GET 未返回 evaluation，且 live OpenAPI 缺少源码新增 routes。该问题属于运行服务版本陈旧，按安全边界本轮未重启。
