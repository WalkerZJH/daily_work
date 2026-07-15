# 「终端不丢」P 级模块分阶段实施路线图

> 文档类型：长期实施计划 / Codex 执行约束 / 模块验收基线  
> 初始审计基线：`main@5a8668549328a8bd79bd22fa6c8acb15baf6a135`  
> 初始编制日期：2026-07-14  
> 适用仓库：`WalkerZJH/daily_work`  
> 建议保存路径：`docs/roadmaps/terminal-retention-p-module-roadmap.md` 或仓库现有规划文档目录

---

## 0. 文档目的

本文档用于约束「终端不丢」项目后续所有 P 级模块的实施顺序、业务边界、数据门禁、验收标准和 Codex 工作方式。

本文档不是一次性的大型实现 Prompt。后续每次收到“继续按 P 模块路线图实施”“实现下一个模块”或等价指令时，Codex 必须：

1. 读取本文档；
2. 检查当前 Git 基线、工作区和仓库级/目录级 `AGENTS.md`；
3. 读取“模块状态表”；
4. 按优先级、依赖关系和门禁选择**下一个可实施模块**；
5. 一次只实现一个模块；
6. 完成代码、测试、构建、文档同步和验证报告；
7. 更新本文档中的模块状态和变更记录；
8. 完成本模块后停止，不得自动开始下一个模块；
9. 默认不得提交、推送、创建分支或 PR，除非用户另行明确授权。

当某个模块未通过数据、接口、口径或性能门禁时，Codex 不得用静态数据、假接口、Prototype 数据或前端占位值伪装完成。应将其标记为 `BLOCKED`，记录证据和最小解除条件，再按本文档的“阻塞绕行规则”处理。

---

# 1. 全局业务边界

## 1.1 正式业务分类

项目正式业务分类只有：

- `Recurring`：已有采购历史、需要持续监测的终端对象；
- `One-shot`：首次采购或首采后尚未形成稳定复购历史的终端对象。

以下内容不是第三类业务对象：

- Daily Detector；
- 规则巡检；
- 证据线索；
- 需求形态分析；
- 风险证据；
- 内部运行状态。

Daily Detector 是事实证据层和内部巡检机制，不得被包装成新的业务分类。

## 1.2 风险模型与 Detector 的语义隔离

必须长期保持：

- 月度 Recurring 候选概率来自月度风险模型；
- Detector score 是规则巡检分数，不是风险概率；
- rule-only clue 不创建 risk entity；
- rule-only clue 不进入 Recurring 候选池；
- rule-only clue 不产生月度风险概率；
- Daily Detector 不得改变月度候选概率、涉及金额、损失金额或排序；
- 不得使用 detector score 填充、替代或近似 probability。

## 1.3 事实与因果边界

除非已有可审计数据、正式字段和冻结口径，否则不得展示或推断：

- 配送商责任；
- 配送异常导致流失；
- 竞品替代；
- 价格导致流失；
- SKU 收缩导致流失；
- 已挽回；
- 挽回金额；
- ROI；
- 兑现率；
- 自动处置结论。

允许展示已有事实、趋势、规则命中和数据 caveat，但不得将相关性写成因果性。

## 1.4 Prototype 使用边界

`daily_work/prototype` 只可参考：

- 信息架构；
- 页面层次；
- 操作意图；
- 视觉布局；
- 交互方向。

Prototype 中的静态医院、金额、ROI、责任归因、竞品替代、P(alive)、推荐动作等均不得直接进入正式系统。

## 1.5 数据和批次边界

必须遵守：

- 正式结果以 Parquet 和正式 manifest 为准；
- 历史正式批次不可覆盖；
- 新运行必须写入新的、可版本化、可追溯的结果路径；
- 未验证的生成目录不得被当作正式批次；
- `2025-12-monthly-risk-algorithm-formal-v2-raw` 中的 `risk_entities` 为 1,229 行 bounded monthly worklist，不能称为全量 Recurring 候选池；
- 在 `full-recurring-v1` 或等价全量批次被正式验证前，不得上线“全量 Recurring”口径；
- 不得通过前端静态补齐、随机生成、复制 Prototype 或改写历史结果来绕过数据门禁。

## 1.6 客户页面与内部页面

客户可见页面只展示已有正式事实和已验证模型结果。

以下功能在正式数据、权限和工作流完善前，只能是内部页面或保持阻塞：

- 规则配置；
- 运行状态；
- 阈值管理；
- 挽回核验；
- 配送预警；
- 订单详情；
- 工作单；
- 自动派单；
- 企业微信转发；
- 模型运行管理。

---

# 2. Codex 长期执行协议

## 2.1 每次开始前

必须先执行并记录：

```bash
git branch --show-current
git rev-parse HEAD
git status --short
```

随后：

1. 读取仓库根目录及相关子目录的 `AGENTS.md`；
2. 读取本文档最新状态；
3. 检查上一个模块是否已完成并通过验收；
4. 检查当前工作区是否存在未知修改；
5. 检查当前 HEAD 是否与本文档最近记录一致；
6. 若存在冲突，先报告，不得覆盖未知修改。

## 2.2 一次只实施一个模块

每次任务只允许：

- 一个 `module_id`；
- 一个明确范围；
- 一组对应测试；
- 一次对应文档同步。

禁止：

- 顺手实现下一个模块；
- 把多个页面一起重构；
- 在修复前端时顺手重训模型；
- 在做内部页时顺手加入写入功能；
- 在做事实展示时顺手生成建议或因果结论。

## 2.3 模块状态

统一使用：

| 状态 | 含义 |
|---|---|
| `PLANNED` | 已规划，尚未满足前置条件 |
| `READY` | 前置条件已满足，可以开始 |
| `IN_PROGRESS` | 当前正在实施 |
| `BLOCKED` | 已确认存在不能由当前模块安全解决的阻塞 |
| `DONE` | 代码、测试、构建、文档和验收均完成 |
| `DEFERRED` | 用户明确推迟 |
| `CANCELLED` | 用户明确取消 |

不得仅因页面可打开就标记 `DONE`。

## 2.4 模块完成定义

模块只有同时满足以下条件才能标记 `DONE`：

1. 范围内代码完成；
2. 新增测试通过；
3. 相关回归测试通过；
4. 前端涉及变更时 `npm run build` 成功；
5. 后端涉及变更时相关 API/仓储测试通过；
6. 完整测试已运行，或明确记录与本模块无关的既有失败；
7. 状态文档已同步；
8. 无未经说明的静态数据或假接口；
9. 业务语义边界验证通过；
10. `git status --short` 和 `git diff --stat` 已报告。

## 2.5 阻塞绕行规则

优先级不等于“必须在阻塞点永久停住”。

当一个模块为 `BLOCKED` 时：

1. 只允许完成该模块的门禁核验和阻塞记录；
2. 不得实现半成品客户功能；
3. 若本文档将该模块标记为 `allow_bypass_when_blocked: yes`，则后续收到“继续实施”时可选择下一个 `READY` 模块；
4. 若标记为 `allow_bypass_when_blocked: no`，必须等待用户解除阻塞或调整计划；
5. 绕过不等于完成，被绕过模块保持 `BLOCKED`。

---

# 3. 当前模块状态表

> Codex 每完成一个模块后必须更新本表，并在“变更记录”中补充日期、基线和结果。

| 顺序 | module_id | 优先级 | 模块 | 初始状态 | 主要依赖 | 阻塞时可绕行 |
|---:|---|---|---|---|---|---|
| 1 | `P0-01` | P0 | 基线、契约与过期工件收敛 | `DONE` | 当前审计结论 | 否 |
| 2 | `P1-01` | P1 | Rule-only Detector 线索独立详情 | `DONE` | `P0-01` | 否 |
| 3 | `P1-02` | P1 | Recurring 全量候选分页列表 | `BLOCKED` | 全量批次门禁 | 是 |
| 4 | `P1.5-01` | P1.5 | Recurring 候选概率趋势与详情导航闭环 | `PLANNED` | 趋势数据审计、候选详情稳定 | 是 |
| 5 | `P2-01` | P2 | One-shot 首采事实工作台完善 | `DONE` | One-shot 字段与口径审计 | 是 |
| 6 | `P2-02` | P2 | Detector 规则目录与运行状态只读中心 | `PLANNED` | 现有 catalog/run/status API | 是 |
| 7 | `P2.5-01` | P2.5 | Detector 输入快照契约与独立运行链路 | `BLOCKED` | 冻结 snapshot schema、正式样本 | 是 |
| 8 | `P3-01` | P3 | 事实型管理驾驶舱 v0 | `PLANNED` | 指标字典、汇总口径、前序模块 | 是 |

---

# 4. 推荐实施队列

Codex 收到“继续按路线图实施”时，按以下逻辑选择模块：

1. 先完成 `P0-01`；
2. 再完成 `P1-01`；
3. 检查 `P1-02` 全量批次门禁：
   - 已满足：实施 `P1-02`；
   - 未满足：记录为 `BLOCKED`，不得用 1,229 行 bounded worklist 冒充全量列表；
4. 检查 `P1.5-01` 趋势数据门禁：
   - 已满足：实施；
   - 未满足：记录为 `BLOCKED` 并继续；
5. 实施 `P2-01`；
6. 实施 `P2-02`；
7. 检查并实施 `P2.5-01`；
8. 最后实施 `P3-01`。

当某模块被阻塞而允许绕行时，Codex 必须在最终报告中明确：

```text
blocked_module:
blocking_evidence:
minimum_unblock_condition:
next_eligible_module:
```

---

# 5. P0-01：基线、契约与过期工件收敛

## 5.1 目标

建立后续模块可依赖的单一事实基线，消除已确认的代码、测试和状态文档冲突。

本模块不增加业务功能。

## 5.2 已知问题

已确认：

1. `clues.html` 当前是“规则巡检结果”，不是 Recurring 候选排序列表；
2. `reports/current_implementation_status.md` 对 `clues.html` 的描述过期；
3. `reports/frontend_query_refactor_baseline.md` 与当前规则线索语义一致；
4. `tests/test_frontend_cleanup_contract.py` 仍要求：
   - `type="date"`
   - `v-model="query.observationDate"`
5. 当前正式实现已经使用：
   - `SquareDatePicker`
   - `draftQuery`
   - `appliedQuery`
6. 前端构建当前已验证成功。

## 5.3 实施范围

### 文档

统一以下事实：

- `index.html`：Recurring Top N 月度候选工作台；
- `clues.html`：Daily Detector 规则巡检结果；
- `clue-detail.html`：当前为候选详情入口，后续由 `P1-01` 扩展为双模式；
- `oneshot.html`：One-shot 首采事实页；
- Detector 是证据层，不是第三类业务对象。

至少检查并最小修改：

```text
reports/current_implementation_status.md
reports/frontend_query_refactor_baseline.md
front_end/AGENTS.md
```

### 测试

更新 `tests/test_frontend_cleanup_contract.py` 中的过期断言，使其验证当前正式查询契约：

- 使用 `SquareDatePicker`；
- 使用 `draftQuery`；
- 使用 `appliedQuery`；
- 查询只在显式提交后应用；
- 不得为了旧测试恢复原生 date input。

### 契约测试

补充或强化静态边界：

- `clues.html` 不加载候选排名 adapter；
- 规则线索页不成为候选分页页；
- 候选排名仍属于 Recurring 工作台或未来独立候选列表；
- Prototype 不参与生产构建和正式数据读取。

## 5.4 禁止事项

- 不实现 clue 详情；
- 不新建候选列表；
- 不修改模型；
- 不改历史数据；
- 不进行无关前端重构。

## 5.5 验收标准

- 过期日期组件测试已修正；
- 相关测试通过；
- 前端构建通过；
- 文档不再把 `clues.html` 写成候选排序列表；
- 规则线索与候选对象边界有自动化测试保护；
- 无业务功能变化。

---

# 6. P1-01：Rule-only Detector 线索独立详情

## 6.1 目标

修复真实用户路径断点：

```text
clues.html
→ clue-detail.html?clueId=<detector_clue_id>
→ 当前显示“缺少候选对象标识”
```

使 `clue-detail.html` 支持：

- Recurring candidate mode；
- Rule-only detector clue mode。

两种模式复用页面外壳，但不混用数据链路。

## 6.2 当前基础

已有：

- detector clue 列表；
- `detector_clue_id`；
- detector 规则信息；
- `evidence_text`；
- `evidence_payload`；
- 详情页壳；
- 候选详情 API；
- 候选证据 API；
- 概率趋势 API。

缺少：

- 单条 detector clue 只读 API；
- 高效按 ID 查询；
- rule-only 详情 adapter；
- 页面模式分支。

## 6.3 数据规模与性能门禁

正式 2025-12：

```text
daily_detector_clues.parquet: 2,924,013 rows
rule-only: 2,872,398 rows
file size: approximately 58.9 MB
```

禁止：

```python
pd.read_parquet(full_file)
df[df["detector_clue_id"] == clue_id]
```

也禁止先调用全量列表方法再过滤。

必须先检查：

- Parquet engine；
- row groups；
- row-group statistics；
- 列投影；
- predicate pushdown；
- 项目现有 PyArrow / DuckDB / Polars 能力；
- 是否已有轻量索引约定。

## 6.4 后端计划

新增：

```http
GET /api/v1/detectors/clues/{detector_clue_id}
```

要求：

- 稳定详情 DTO；
- 200 / 404 / 重复主键异常；
- 显式 caveat；
- `evidence_payload` 安全 JSON 序列化；
- 不透传任意内部对象；
- 单条仓储方法不走全量 pandas 读取。

建议仓储语义：

```python
get_daily_detector_clue_by_id(...)
```

具体命名遵循项目规范。

## 6.5 前端计划

`clue-detail.html` 支持：

### Candidate mode

URL：

```text
riskEntityId=<id>
```

数据：

- risk entity detail；
- detector evidence；
- probability trend。

### Rule-only mode

URL：

```text
clueId=<detector_clue_id>
```

数据：

- 新单条 clue API。

禁止 rule-only 模式调用：

```text
/risk-entities/{id}
/probability-trend
/risk-entities/{id}/detector-evidence
```

## 6.6 Rule-only 展示

允许：

- 医院；
- 药品；
- 生产企业；
- 观测日期；
- detector 名称；
- detector family；
- 规则巡检分数；
- 命中等级；
- confidence；
- root cause；
- evidence text；
- evidence payload；
- “未关联月度风险候选”；
- caveat。

必须明确：

```text
规则巡检分数不是月度风险概率。
仅规则命中不会创建 Recurring 风险候选对象。
```

禁止：

- 月度概率；
- H3/H6/H12；
- 概率趋势；
- 金额；
- 候选排名；
- 高风险标签；
- 自动建议；
- 工单；
- 责任归因；
- 竞品替代。

## 6.7 导航

- rule-only 返回 `clues.html`，尽可能保留查询上下文；
- candidate 不得默认返回规则巡检页；
- 不在本模块新建 Recurring 全量列表。

## 6.8 测试

至少覆盖：

- 单条 API 200；
- 404；
- 重复 ID；
- rule-only 不创建 risk entity；
- detector score 不映射为 probability；
- evidence payload 序列化；
- 仓储不调用全量列表；
- 仓储不完整加载 292 万行 pandas DataFrame；
- rule-only URL 正确进入 clue mode；
- 不调用 risk entity API；
- 不调用 probability trend；
- candidate 原路径不回归；
- 参数缺失显示明确错误；
- 前端构建通过。

## 6.9 验收标准

- rule-only 点击详情不再空白；
- 单条读取路径性能可解释；
- rule-only 和 candidate 数据链路互斥；
- 业务语义无污染；
- 相关测试和构建通过。

---

# 7. P1-02：Recurring 全量候选分页列表

## 7.1 目标

为 Recurring 建立独立的全量候选分页列表，不复用 `clues.html`。

## 7.2 当前基础

已有：

- `GET /api/v1/risk-entities`；
- manufacturer / observation date / horizon；
- sort；
- page；
- page_size；
- `loadCandidateRankingData`；
- 候选详情页；
- Top N 工作台。

缺少：

- 正式独立 View；
- 正式页面入口；
- Vite input；
- 导航；
- 分页交互；
- 已验证全量批次。

## 7.3 强制数据门禁

实施前必须找到并验证：

```text
full-recurring-v1
```

或等价正式全量批次。

必须验证：

- batch 路径真实存在；
- manifest 存在；
- 文件完整；
- `full_recurring_count`；
- `persisted_recurring_count`；
- 两者口径一致或差异有正式说明；
- 结果不是 bounded worklist；
- API 实际指向该批次；
- 候选分页能覆盖全量记录。

当前 1,229 行 `formal-v2-raw` 不满足门禁。

若门禁失败：

- 将本模块标记 `BLOCKED`；
- 只输出阻塞证据；
- 不创建标有“全量候选”的客户页面；
- 不用 1,229 行结果伪装全量。

`allow_bypass_when_blocked: yes`

## 7.4 页面计划

新建独立页面，名称遵循当前工程约定，例如：

```text
candidate-list.html
```

最终命名应在实现前检查现有路由和命名规则后确定。

禁止复用：

```text
clues.html
```

页面采用：

- `draftQuery`；
- `appliedQuery`；
- 显式查询；
- 服务端分页；
- 服务端排序；
- URL 查询上下文；
- 稳定返回导航。

## 7.5 查询与排序

使用现有 API 支持的正式字段：

- manufacturer；
- observation_date；
- horizon；
- page；
- page_size；
- `risk_probability`；
- `involved_amount`；
- `loss_value`。

禁止：

- 按 detector score 排序；
- 前端加载全部数据后自行分页；
- 前端重新计算候选概率；
- 将规则线索混入候选列表。

## 7.6 列表展示

至少包含：

- 候选排名或页内序号；
- 医院；
- 药品；
- 生产企业；
- 观测日期；
- horizon；
- 月度风险概率；
- 涉及金额；
- 损失价值（仅正式字段存在时）；
- 详情入口。

所有金额、概率和排序必须来自正式 API。

## 7.7 导航与边界

- Top N 工作台可进入全量候选页；
- 全量候选页可进入候选详情；
- 候选详情返回候选列表或工作台来源；
- “查看规则巡检结果”仍进入 `clues.html`；
- 候选和规则页面不得互相冒充。

## 7.8 测试

覆盖：

- 分页参数；
- page_size；
- 合法排序；
- 非法排序 422；
- draft/applied；
- 查询上下文；
- 空结果；
- 越界页；
- 候选详情跳转；
- 返回导航；
- 不加载 detector clue 列表；
- 前端构建。

## 7.9 验收标准

- 页面使用已验证全量批次；
- 总数、页数、分页结果与 manifest/API 一致；
- 不修改候选池；
- 不影响 Top N 工作台；
- 不污染规则线索页面；
- 测试与构建通过。

## 7.10 门禁核验记录（2026-07-15）

- `full-recurring-v1` 目录真实存在，已有 `risk_entities.parquet`、`risk_cards.parquet` 和 `risk_entity_horizon_profiles.parquet`；其中 `risk_entities.parquet` 为 88,515 行，`candidate_type` 均为 `recurring`。
- 这只能证明主干预测产物已部分写出，不能替代正式批次契约：该目录没有 `manifest.json`，因此无法读取或核验 `full_recurring_count`、`persisted_recurring_count`、结果表计数和批次版本信息；`validate_result_batch` 因缺少 manifest 失败。
- Detector 是与主干预测语义分离的独立证据表，不是 `P1-02` 的阻塞条件，也不得与 Recurring 候选混入同一业务表。当前缺少 Detector 表不作为本模块的阻塞证据。
- 当前 API 仅发现带 `manifest.json` 的批次；`data/project_result_batches` 下 2025-12 当前可发现的是 `formal-v2-raw`，其 `risk_entities.parquet` 为 1,229 行，因此 API 尚未实际指向 88,515 行产物。

阻塞结论：`P1-02` 保持 `BLOCKED`。最小解除条件是为不修改既有业务结果的正式 `full-recurring-v1` 批次补齐并校验 manifest，确认两项 Recurring 计数口径，然后验证 API 已发现该批次并可覆盖全量分页。不得用 1,229 行 bounded worklist 冒充全量，也不得因本模块重训、重跑或覆盖历史预测批次。

---

# 8. P1.5-01：Recurring 候选概率趋势与详情导航闭环

## 8.1 目标

使用现有 `probabilityTrend` 数据链路，在候选详情页展示真实历史概率变化，并修复候选详情的返回导航。

## 8.2 当前基础

已有：

- `/api/v1/risk-entities/{id}/probability-trend`；
- adapter 已请求并保存 `probabilityTrend`；
- 候选详情页；
- 月度结果；
- H3/H6/H12；
- detector evidence。

缺少：

- 趋势数据正式审计；
- 最少历史点口径；
- 页面渲染；
- 明确空状态；
- 正确返回来源。

## 8.3 实施前门禁

必须审计正式结果：

- 每个 entity 的趋势点数量分布；
- 起止月份；
- 是否存在重复月份；
- 是否存在缺月；
- probability 范围；
- 不同 horizon 是否混合；
- entity ID 跨批次是否稳定；
- 数据保留周期。

必须形成简短报告，并冻结：

```text
trend_minimum_points
trend_sort_order
duplicate_month_policy
missing_month_policy
horizon_policy
```

若没有足够历史点：

- 页面只显示“历史趋势暂不可用”；
- 不插值；
- 不补零；
- 不复制当前概率形成假趋势；
- 不生成趋势结论。

`allow_bypass_when_blocked: yes`

## 8.4 前端计划

候选详情增加只读趋势区域：

- 横轴：正式 observation/report month；
- 纵轴：正式 risk probability；
- 当前点明确标识；
- 空状态；
- 数据不足状态；
- caveat。

禁止：

- 预测未来点；
- 线性外推；
- 自动生成“持续恶化”“即将流失”等未经规则支持的结论；
- 混入 detector score；
- 混合不同 horizon 而不标识。

## 8.5 导航计划

修复当前候选详情返回 `clues.html` 的语义错误。

返回优先级：

1. 有正式 source/from 上下文时返回来源页；
2. 来自全量候选列表时返回该列表并保留查询；
3. 来自 Top N 工作台时返回工作台；
4. 无来源时返回 Recurring 工作台；
5. 不默认返回规则巡检页。

## 8.6 测试

覆盖：

- 足够历史点；
- 单点；
- 空数据；
- 重复月；
- 顺序；
- horizon；
- 概率格式；
- 无伪造点；
- source navigation；
- candidate API 回归；
- rule-only clue 页面不渲染趋势；
- 前端构建。

## 8.7 验收标准

- 趋势只基于真实历史点；
- 数据不足时明确空状态；
- 不生成因果或未来预测；
- 候选返回路径语义正确；
- rule-only 不受影响；
- 测试和构建通过。

---

# 9. P2-01：One-shot 首采事实工作台完善

## 9.1 目标

将现有 One-shot 页面完善为稳定的“首采事实工作台”，优先展示可验证事实，不把当前未充分验证的复购倾向模型作为客户决策依据。

## 9.2 当前基础

已有：

- `oneshot.html`；
- One-shot API；
- `loadOneshotData`；
- 首采事实展示；
- `evidenceReady` 条件显示；
- 标准结果表或候选回退逻辑。

当前缺少：

- 统一 `draftQuery/appliedQuery`；
- 分页边界；
- 详情边界；
- 正式预测字段审计；
- 模型指标方向和有效性确认。

## 9.3 模型门禁

已知历史报告中的 One-shot 模型指标存在明显风险：

```text
AUC: 0.307
PR-AUC: 0.264
Lift: 0.725
ECE: 0.321
Brier: 0.352
```

实施前必须审计：

- 标签方向；
- 正负类定义；
- 分数方向；
- AUC 是否因方向反转；
- 评估样本；
- 时间切分；
- 数据泄漏；
- `evidenceReady` 的真实含义；
- 当前页面使用的 propensity 字段来源。

在审计通过前：

- 默认只展示首采事实；
- 不展示“高复购倾向”“低复购倾向”等决策标签；
- 不按未经验证的 propensity 做客户可见排序；
- 不生成自动促销建议。

## 9.4 页面计划

统一使用：

- manufacturer；
- observation/report date；
- 必要事实过滤；
- `draftQuery`；
- `appliedQuery`；
- URL 查询上下文；
- 服务端分页（若数据规模需要）。

至少展示：

- 医院；
- 药品；
- 生产企业；
- 首采日期；
- 首采数量；
- 首采金额（仅正式字段存在时）；
- 最近事实状态；
- 数据来源日期。

不得将 One-shot 混入 Recurring 候选池。

## 9.5 详情计划

只在正式字段足够时增加 One-shot 事实详情。

详情允许：

- 首采订单事实；
- 后续采购事实；
- 已观察窗口；
- 数据完整性；
- evidence-ready 状态解释。

禁止：

- 伪造复购概率；
- 伪造营销优先级；
- 自动生成促销动作；
- 将“未复购”直接解释为“流失”。

## 9.6 后端计划

优先复用现有 endpoint。

仅当现有接口无法支持正式分页或详情时，新增最小只读 API。

禁止：

- 前端加载全量再分页；
- 在页面层计算 propensity；
- 重训模型作为本模块的隐含子任务。

## 9.7 测试

覆盖：

- draft/applied；
- 查询上下文；
- 分页；
- 空结果；
- 首采事实；
- evidenceReady；
- 未通过模型门禁时预测字段隐藏；
- One-shot 与 Recurring 数据隔离；
- 前端构建。

## 9.8 验收标准

- One-shot 页面成为稳定事实工作台；
- 未验证模型信息默认不进入客户决策界面；
- 不创建第三类业务；
- 不污染 Recurring；
- 测试和构建通过。

## 9.9 实施结果（2026-07-15）

P2-01 已按事实优先边界完成：`oneshot.html` 只读取正式
`oneshot_terminals.parquet`，提供生产企业范围查询、事实字段排序和服务端分页；
缺表时显式返回不可用状态，不再回退到 Recurring 候选数据。页面已移除复购倾向、
预计复购金额、模型优先级等未经模型门禁验证的语义，并区分加载、错误、缺表和空结果状态。

本阶段没有新增 One-shot 物化、详情页或预测模型，也没有运行训练、预测和 Detector
物化。One-shot 预测能力继续受独立模型有效性门禁约束，P2-02 仍为独立后续模块。

---

# 10. P2-02：Detector 规则目录与运行状态只读中心

## 10.1 目标

将当前内部占位的规则配置/运行状态入口建设为只读内部中心，用于查看：

- detector catalog；
- 规则启用状态；
- 阻塞原因；
- 运行记录；
- 观测日期；
- 状态；
- 数据量；
- caveat。

本模块不实现规则编辑。

## 10.2 当前基础

已有 API：

```text
/api/v1/detectors/catalog
/api/v1/detectors/runs
/api/v1/daily-detector/dates
/api/v1/daily-detector/status
/api/v1/detectors/config-status
```

已有内部导航占位。

## 10.3 页面计划

内部页面至少包含：

### 规则目录

- detector ID；
- detector name；
- family；
- enabled；
- implementation status；
- block reason；
- evidence availability；
- caveat。

### 运行记录

- run ID；
- observation date；
- status；
- started/finished time（若正式字段存在）；
- clue count；
- high-risk linked count；
- rule-only count；
- error summary（若正式字段存在）。

### 状态说明

必须显示：

- detector score 不是 probability；
- daily clues 不创建 risk entity；
- 被禁用规则的原因；
- 数据缺失与未实现是不同状态。

## 10.4 状态口径

至少区分：

```text
enabled
disabled
blocked_by_data
blocked_by_missing_domain_concept
not_implemented
reserved
run_success
run_failed
run_partial
no_run
```

最终字段以现有正式 catalog/schema 为准。

不得把所有 disabled 都显示成“异常”。

## 10.5 禁止事项

- 不编辑阈值；
- 不写 YAML；
- 不启动 detector；
- 不重新运行；
- 不修改启用状态；
- 不创建审批流；
- 不把内部页暴露成客户承诺。

## 10.6 性能

运行记录和 catalog 应通过服务端过滤/分页获取。

禁止前端读取 292 万 clue 用于计算运行汇总。

汇总应来自正式 run/status 表或后端聚合。

## 10.7 测试

覆盖：

- catalog；
- run list；
- status；
- disabled reasons；
- no-run；
- failed run；
- 空状态；
- 内部导航；
- 只读边界；
- 不存在写请求；
- 前端构建。

## 10.8 验收标准

- 内部人员可审计规则和运行状态；
- 不提供写入入口；
- 状态口径与正式数据一致；
- 不通过 clue 全表前端聚合；
- 测试和构建通过。

---

# 11. P2.5-01：Detector 输入快照契约与独立运行链路

## 11.1 目标

完成 Daily Detector 的版本化输入快照和独立运行链路，使 detector 可以在不重跑月度模型、不覆盖历史结果的前提下生成新的只读证据批次。

## 11.2 当前状态

当前：

- `production_pipeline/run_daily_detector.py` 存在；
- 要求 `detector_input_snapshot.parquet`；
- 快照缺失时返回 blocked；
- 快照存在时仍进入 `NotImplementedError`；
- snapshot schema 尚未正式冻结。

初始状态：

```text
BLOCKED
```

## 11.3 强制解除条件

实施前必须具备：

1. 冻结的 snapshot schema；
2. 字段定义；
3. 数据粒度；
4. 主键；
5. 时间字段；
6. 空值规则；
7. 枚举规则；
8. 数据来源；
9. 脱敏边界；
10. 一个可验证的正式样本或经过审批的固定 fixture；
11. 版本策略；
12. manifest 规范。

若缺少任一关键项，不得实现“正式可运行”状态。

`allow_bypass_when_blocked: yes`

## 11.4 输入快照契约

至少冻结：

```text
snapshot_schema_version
snapshot_id
source_batch_id
observation_date
created_at
row_count
primary_key
required_columns
optional_columns
data_types
nullability
enum_constraints
source_checksums
```

字段必须与现有三个已实现 detector 的实际输入一致：

- purchase interval / IPI；
- purchase quantity trend；
- purchase frequency drop。

不得为 blocked detector 伪造输入：

- SKU shrink；
- fulfillment gap；
- price competition；
- peer contrast。

## 11.5 运行计划

实现独立 CLI 或完善现有脚本：

```bash
python -m production_pipeline.run_daily_detector ...
```

实际命令遵循仓库结构。

必须支持：

- 显式 snapshot；
- 显式 observation date；
- 显式 output batch/run ID；
- schema validation；
- dry-run 或 validate-only；
- 不覆盖；
- 幂等检查；
- 原子写入；
- 失败清理；
- manifest；
- run registry；
- 状态记录；
- 输出行数核对。

## 11.6 输出

版本化写入新的结果路径。

至少包括：

- detector catalog snapshot/reference；
- detector run；
- daily detector clues；
- high-risk detector evidence；
- manifest；
- validation report。

不得修改：

- 月度 risk entities；
- 月度概率；
- 月度金额；
- 历史 detector 结果。

## 11.7 失败与回滚

必须：

- 临时目录写入；
- 全部验证通过后原子发布；
- 失败不留下“成功批次”；
- registry 不得先标成功；
- 同一 run ID 不得静默覆盖；
- manifest 校验失败不得对外提供。

## 11.8 测试

先使用小型固定 fixture：

- schema valid；
- missing required field；
- wrong type；
- duplicate key；
- bad date；
- no overwrite；
- dry-run；
- success；
- failure cleanup；
- manifest；
- row counts；
- registry；
- 三个已实现 detector；
- blocked detector 不运行；
- 月度候选不变化。

在 fixture 通过前，不对正式大批次执行。

## 11.9 验收标准

- snapshot schema 已冻结；
- runner 不再依赖隐式当前模型；
- 新运行版本化；
- 不覆盖历史；
- 不改变 Recurring 候选；
- 输出可审计；
- 失败可恢复；
- 测试通过。

---

# 12. P3-01：事实型管理驾驶舱 v0

## 12.1 目标

建设内部事实型管理驾驶舱，用于汇总当前已验证的 Recurring、One-shot 和 Detector 事实。

本模块不是 Prototype 的静态复刻。

## 12.2 强制口径门禁

实施前必须冻结指标字典。

每个指标必须定义：

```text
metric_id
display_name
business_definition
numerator
denominator
time_grain
entity_grain
filters
source_table
source_field
update_frequency
data_freshness
null_policy
owner
caveat
```

没有指标字典，不得开始客户可见或管理层正式驾驶舱。

## 12.3 v0 允许指标

仅在正式数据存在时可展示：

### Recurring

- 当前月候选对象数；
- 按风险层级的对象数；
- 候选涉及金额；
- 不同 horizon 的对象分布；
- 数据观测日期；
- 批次 ID。

### Detector

- 最近运行状态；
- 最近成功运行日期；
- 规则命中数；
- rule-only 数；
- 与月度候选关联数；
- 各 detector family 命中数；
- enabled / blocked / not implemented 规则数。

### One-shot

- 首采终端数；
- 首采事实时间分布；
- 有后续采购事实的终端数；
- 仍在观察窗口的终端数。

One-shot 指标必须避免把“尚未复购”直接定义为流失。

## 12.4 v0 禁止指标

在闭环数据缺失前不得展示：

- 已挽回金额；
- 回款金额；
- ROI；
- 兑现率；
- 工单完成率；
- 自动派单成功率；
- 配送责任占比；
- 竞品替代率；
- 价格导致流失金额；
- 预计可挽回金额；
- Prototype 中的任何静态数字。

## 12.5 后端计划

优先使用正式汇总表。

若需新增聚合 API：

- 后端聚合；
- 明确 report month / observation date；
- 明确 batch；
- 明确数据新鲜度；
- 明确分页/筛选；
- 不让前端读取 292 万 clue 后计算指标；
- 为每个指标保留来源和 caveat。

## 12.6 前端计划

页面至少包含：

- 全局时间/批次上下文；
- 数据新鲜度；
- 指标卡；
- 维度分布；
- 运行状态；
- 口径说明入口；
- 空状态；
- 数据不可用状态。

不得：

- 混用不同月份；
- 混用不同批次而不标识；
- 隐藏分母；
- 用动画或颜色夸大风险；
- 将内部事实写成因果结论。

## 12.7 数据质量

上线前必须完成：

- API 与源表对账；
- 指标总数与分组和一致性；
- 空值；
- 重复；
- 时间边界；
- 批次一致性；
- 过滤一致性；
- 抽样核对。

## 12.8 测试

覆盖：

- 指标定义；
- 过滤；
- 时间；
- batch；
- 总分一致；
- 空数据；
- stale data；
- API/source reconciliation；
- 不出现禁止指标；
- 前端构建。

## 12.9 验收标准

- 所有指标有正式定义和来源；
- 页面显示 as-of 和数据新鲜度；
- 不含未闭环 ROI/挽回指标；
- 不使用 Prototype 静态数据；
- 大表聚合在后端完成；
- 对账通过；
- 测试和构建通过。

---

# 13. 长期阻塞模块与解除条件

以下模块不属于当前 P 级实施队列，除非用户后续明确立项并补齐门禁。

| 模块 | 当前阻塞 | 最小解除条件 |
|---|---|---|
| 配送商预警 | 缺少经验证配送事实 | 配送字段、时间口径、只读 API |
| 配送责任归因 | 缺少责任定义和因果证据 | 责任规则、审计样本、人工核验 |
| SKU 收缩 | 缺少正式 SKU / 产品线概念 | SKU 主数据、映射、输入契约 |
| 价格竞争 | 低价不能证明竞争 | 价格事实、竞品定义、对照口径 |
| 竞品替代 | 缺少替代事实 | 竞品、适应症、采购转移证据 |
| 挽回核验 | 缺少闭环结果 | 核验事实表、状态机、标准 |
| ROI / 兑现率 | 缺少成本和收益闭环 | 成本、收益、归因窗口、财务口径 |
| 工单 | 缺少持久化和权限 | 工单表、状态机、权限、审计日志 |
| 企业微信转发 | 缺少正式通道 | 授权、模板、审计、失败重试 |
| 自动派单 | 缺少工作流 | 规则、权限、责任人、回滚 |
| 订单详情 | 缺少正式详情 API 和权限 | 明细 API、脱敏、访问控制 |
| 自动月度重跑 | 历史批次不可覆盖 | 版本化运行、审批、回滚 |
| Full pipeline | 运行边界未冻结 | 独立输入、产物、registry、验收 |

“需求形态分析”不得被新增为第三类业务模块。相关事实只能作为 Recurring 或 One-shot 的特征、证据或内部分析维度。

---

# 14. 每个模块的统一实施输出

Codex 完成任何模块后，必须按以下格式汇报。

## A. Module

```text
module_id:
module_name:
status_before:
status_after:
```

## B. Baseline

```text
branch:
starting_commit:
working_tree_before:
```

## C. Gate Verification

```text
required_gates:
passed_gates:
failed_gates:
blocking_evidence:
```

## D. Implemented Scope

说明实际完成内容。

## E. Explicitly Not Implemented

列出本模块禁止或延后的内容。

## F. Changed Files

逐文件说明。

## G. Data and API Contract

列出：

- source；
- schema；
- API；
- errors；
- caveats；
- performance path。

## H. Tests

逐项列出：

```text
command:
passed:
failed:
skipped:
```

## I. Build

前端涉及修改时：

```text
npm run build:
```

## J. Semantic Boundary Verification

至少确认：

```text
business categories remain Recurring and One-shot
detector score is not probability
rule-only does not create risk entity
no unsupported causal claim
no prototype static data
no historical batch overwrite
```

根据模块补充专项边界。

## K. Remaining Risks

只列真实剩余问题。

## L. Roadmap Update

说明：

```text
current module status:
next eligible module:
blocked modules:
roadmap file updated:
```

## M. Git Status

```bash
git status --short
git diff --stat
```

默认停止，不自动进入下一个模块。

---

# 15. 路线图更新规则

Codex 只能修改本文档中的以下内容：

1. “当前模块状态表”；
2. 各模块新增“实施结果”小节；
3. “变更记录”；
4. 经用户确认后的门禁或范围调整。

不得在实现过程中静默弱化：

- 业务分类；
- Detector 与概率边界；
- 历史批次不可覆盖；
- Prototype 不作为正式事实；
- 阻塞模块的最小解除条件。

若需要调整路线图，应先在最终报告中提出：

```text
proposed_change:
reason:
evidence:
impact:
```

未经用户明确同意，不得自行改写优先级或删除模块。

---

# 16. 变更记录

| 日期 | 基线/提交 | module_id | 状态变化 | 说明 |
|---|---|---|---|---|
| 2026-07-14 | `5a8668549328a8bd79bd22fa6c8acb15baf6a135` | Roadmap | 初始化 | 根据只读审计结果建立 P0–P3 分阶段实施计划 |
| 2026-07-15 | `2f8115506979ae0e2aa1f0e1ae02c068798672cc` | `P0-01`、`P1-01` | `DONE` | 已完成规则巡检语义收敛、过期查询测试更新和 Rule-only Detector 线索独立详情；相关测试与前端构建已验证。 |
| 2026-07-15 | `2f8115506979ae0e2aa1f0e1ae02c068798672cc` | `P1-02` | `BLOCKED` | 88,515 行 Recurring 主干产物尚无 manifest，API 仍发现 1,229 行 formal-v2-raw；Detector 表缺失不作为该模块阻塞证据。 |

---

# 17. 后续调用 Codex 的固定指令

后续无需再次粘贴单模块长 Prompt，可直接使用：

```text
请读取仓库中的《「终端不丢」P 级模块分阶段实施路线图》。

严格按照其中的“Codex 长期执行协议”“当前模块状态表”和“推荐实施队列”执行：

1. 检查当前分支、HEAD、工作区和 AGENTS.md；
2. 核对路线图状态；
3. 选择下一个满足门禁的模块；
4. 一次只实施一个模块；
5. 不得绕过数据、语义、性能或批次门禁；
6. 完成代码、测试、构建和文档同步；
7. 更新路线图状态与变更记录；
8. 按路线图规定的统一格式汇报；
9. 默认不要提交、推送、创建分支或 PR；
10. 完成本模块后停止，不要自动实施下一个模块。
```
