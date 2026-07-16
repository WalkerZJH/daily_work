# Detector 模块完成度与链路通畅性审计

审计时间：2026-07-16（Asia/Shanghai）  
审计性质：只读核验；除本报告及两份配套报告外未修改生产代码、配置、registry 或结果目录。

## 1. 总结论

- **Release A：完成。** 10 个非配送 Detector 均为真实实现、默认启用、具备企业级只读配置快照、独立 compute/validate/publish、registry 解析和稳定 API 读取能力。23 个定向测试通过；2026-01-01 稳定发布日可由 API 发现全部 10 个 Detector。
- **Release B：部分完成，不能认定完成。** clues 的筛选、排序、分页、加载/错误/空态及单条规则详情骨架已实现并可构建，但真实名称合并、10 个 Detector 中文名、实体级全部当前命中详情和当前运行服务版本一致性仍有功能断点。
- **Detector 链路：稳定历史链路通畅，Release B 展示链路有局部断点。** compute → validate → publish → registry → API 对已发布稳定日通畅；API → display lookup、中文 label、entity-all-hits detail 不完整。
- **当前物化：未完成，进程已在审计末段全部退出，未受本审计干预。** 未停止、暂停、重启或新增任何物化进程，未打开活动目录中的 Parquet。8 个状态文件均为 `completed=false`，因此必须先诊断再决定是否以新 run/retry 继续。
- **Release C：已有部分提前实现。** `a5d49b8`、`be68bbe`、`f8658cc` 已加入跨日 Detector event aggregation、覆盖测试和流式聚合；当前 09:58 启动的后端 OpenAPI 尚未暴露源码中的 results/event-aggregates 路由，不能认定 Release C 已发布完成。

## 2. 当前进程保护信息

审计开始时有 8 个进程，均于 `2026-07-16 15:46:40 +08:00` 启动，命令均为 `python -m production_pipeline.materialize_daily_detector_range`，输入为：

`algo_main/data/entity_complete_v2_coverage_expansion/11_business_detector_adaptation/cleaned_detector_input/batch_id=cleaned-detector-facts-v2-20260716`

输出根为 `data/project_result_batches`，Detector 集合为本报告所列 10 个规则，均带 `--resume-existing`。

| PID | 日期区间 | run_id |
|---:|---|---|
| 22180 | 2025-01-02..2025-02-14 | zz-2025-admin-full-v1-q1 |
| 4004 | 2025-02-15..2025-03-31 | zz-2025-admin-full-v1-q1b |
| 30796 | 2025-04-01..2025-05-15 | zz-2025-admin-full-v1-q2 |
| 25080 | 2025-05-16..2025-06-30 | zz-2025-admin-full-v1-q2b |
| 19912 | 2025-07-01..2025-08-15 | zz-2025-admin-full-v1-q3 |
| 6428 | 2025-08-16..2025-09-30 | zz-2025-admin-full-v1-q3b |
| 12460 | 2025-10-01..2025-11-15 | zz-2025-admin-full-v1-q4 |
| 20900 | 2025-11-16..2025-12-31 | zz-2025-admin-full-v1-q4b |

`ACTIVE_MATERIALIZATION_PATHS`：`data/project_result_batches/.detector_staging`，以及 `data/project_result_batches/detector_run_date=2025-01-02` 至 `2025-12-31` 中上述 8 个 run-id 对应的 component/staging 路径。目录采用按日期、detector_id、batch_id 分层，进程命令未给出独立 registry 参数；正式 registry 目标按源码为输出根的 observation registry。本审计只看了进程、目录名和时间戳，没有打开这些路径内的 Parquet。

审计末段再次查询时 8 个 PID 均已不存在；本审计没有执行任何停止命令。只读 range status JSON 显示：q1 `27`、q1b `10`、q2 `25`、q2b `9`、q3 `23`、q3b `8`、q4 `22`、q4b `8` 个日期完成，8 个文件的 `completed` 均为 false。该批次应标记为 **materialization incomplete / no live matching process**，不能标记算法失败，也不得直接覆盖或重用已有目录。

## 3. Git 状态

- 审计开始：分支 `main`，HEAD `f8658cc599f80f4d21eababffc9cb0ce3ce0c673`，工作区干净，`origin/main=f76bf3e55ef6a810dde988ae060d510e3c4b1ef7`。
- 审计期间外部变化：HEAD 先前移至 `50646c084af5844eb7b7c1f42592beb5e44b2ac5`（`perf: reuse detector snapshot records`），当时短暂出现 `M production_pipeline/materialize_daily_detector_range.py` 与 `?? tests/test_detector_range_resume.py`；随后外部提交 `b1d72fc4aae3f7a28f8d7bbbc9ab18624ed1e614`（`perf: skip snapshots for resumed detector dates`）纳入这两项。报告落盘前 HEAD 为 `b1d72fc`，除三份审计报告外工作区干净。本审计没有生成、修改、还原、暂存或提交上述生产代码/测试变化。
- Release A 提交 `f76bf3e` 仍在当前 HEAD 历史中；Release B 提交为 `3521c87`。
- 本审计仅新增三份约定报告。前端 build 只写入已忽略的 `front_end/dist/`。

## 4. Release A 完成度

判定：**完成**。

证据：

1. `risk_algorithm_core/detector_catalog.py` 与 `configs/risk_algorithm_core/daily_detector_rules.yaml`：10 个目标 Detector 均为 `implemented`、`enabled: true`，有独立 id、version、method 和可直接运行默认值。
2. `risk_algorithm_core/daily_detector_runner.py`：按 `selected_ids` 选择 evaluator；每个企业解析唯一 config profile；结果带 `detector_version/config_id/config_hash` 及证据字段。
3. `production_pipeline/run_daily_detector.py`：每个 detector 独立校验、staging、原子发布，拒绝覆盖已有正式目录；语义明确为 `no_monthly_model_dependency`。
4. `production_pipeline/materialize_daily_detector_range.py`：支持 Detector、日期区间、可选企业和 resume；本轮未实际调用。
5. `production_pipeline/rebuild_observation_registry.py` 与 `risk_model_core/repositories.py`：registry 解析与 component composition 存在；临时目录测试证明独立发布不会改写另一 Detector。
6. GET `/api/v1/daily-detector/dates`：2026-01-01 稳定日登记 10 个 ready run，包括 0 命中的 `order_price_spread_warning`；0 命中未被误判为未实现。
7. GET `/api/v1/daily-detector/status?observation_date=2026-01-01&manufacturer_code=DFC...`：`ready=true`、精确日期、10 个 run id、无 fallback。

特别核验：

- `purchase_quantity_trend` 明确为 `simplified_ratio_v1`，不是 MK/Theil-Sen/CUSUM。
- 价格规则使用 `purchase_unit_price` 直接单价；可比组按 `drug_code × purchase_unit`。
- `sku_shrink`、`fulfillment_gap`、`price_competition`、`peer_contrast` 仍禁用/范围外；未混入本次 10 个规则。

## 5. 10 个 Detector 状态矩阵

所有行均表示“实现及稳定历史发布 complete / 当前 2025 全年新 run 物化 incomplete，且无存活进程”。

| Detector | 实现/默认启用 | 方法 | 稳定 2026-01-01 run | 当前状态 |
|---|---|---|---|---|
| purchase_interval_ipi | 是 | median_mad_robust_z_v1 | ready，11244 hits（全局） | complete；current materialization incomplete |
| purchase_quantity_trend | 是 | simplified_ratio_v1 | ready，12657 | complete；current materialization incomplete |
| purchase_frequency_drop | 是 | recent_base_rate_ratio_v1 | ready，660 | complete；current materialization incomplete |
| purchase_quantity_spike | 是 | recent_base_quantity_ratio_v1 | ready，1720 | complete；current materialization incomplete |
| purchase_frequency_spike | 是 | recent_base_frequency_ratio_v1 | ready，25 | complete；current materialization incomplete |
| low_price_warning | 是 | configured_price_or_prior_market_p05_v1 | ready，11 | complete；current materialization incomplete |
| order_price_spread_warning | 是 | recent_max_min_ratio_v1 | ready，0 | complete；current materialization incomplete |
| purchase_price_level_shift | 是 | recent_baseline_median_ratio_v1 | ready，57 | complete；current materialization incomplete |
| first_purchase_fact | 是 | first_normal_completed_purchase_fact_v1 | ready，5 | complete；current materialization incomplete |
| reactivated_purchase_fact | 是 | normal_purchase_after_silence_v1 | ready，10 | complete；current materialization incomplete |

这些 hit 数是 `/api/v1/daily-detector/dates` 的全局 run 元数据，不是指定企业筛选后的列表 total。

## 6. 增量链路、发布、registry 与 API

链路结论：

`单 detector → 日期区间 → 可选企业 → config profile → compute → validate → 独立 Parquet → 原子 publish → observation registry → API` 在源码和隔离测试中完整存在。

- 隔离性：`--detector-id` 仅把选中 id 传入 runner；component 路径包含 detector_id/version/run_id；月度 scoring、候选池和月度写入不在调用链中。
- 配置：每企业唯一 profile，缺失配置会拒绝发布；snapshot 只保存 config id/hash，历史结果不改写。
- 查询：repository 只读已发布表，不触发重算。
- registry：临时目录集成测试成功重建并解析日期分区；正式 registry 未被本审计写入。
- 当前运行服务：`uvicorn` PID 18160 于 09:58 启动，早于当日 15:xx 的源码/提交。其 OpenAPI 缺少当前源码已有的 `/api/v1/detectors/results` 和 `/api/v1/detectors/event-aggregates`，属于**服务版本陈旧**，本轮按禁令未重启。

API 状态：

| API | controller/service/repository | 状态 | 主要缺口 |
|---|---|---|---|
| GET `/api/v1/daily-detector/clues` | `routes_detector_results.daily_detector_clues` → `DetectorResultService.clues` → component repository | 基本通畅 | 支持 detector_level，不支持名为 `severity` 的参数；display lookup 空 |
| GET `/api/v1/detectors/clues` | `detector_clues` → `clues` | 通畅 | 用 `run_date/drug_group`，不是 `observation_date/drug_code`；未带用户 header |
| GET `/api/v1/detectors/clues/{id}` | `detector_clue_detail` → `clue_detail` | 单条规则通畅 | 不是 entity-all-hits；活动服务未返回 evaluation 完整字段 |
| GET `/api/v1/risk-entities/{id}/detector-evidence` | route → `risk_entity_detector_evidence` | 仅月度候选适用 | Detector-only entity 无 risk_entity_id，不能走此链路 |
| GET `/api/v1/display-lookup/status` | display lookup service → 月度 repository | status ready | 与 Detector composite repository 实际 lookup 能力不一致 |

## 7. Release B 完成度

判定：**部分完成**。

已完成：

- clues 页面业务职责保持为指定企业 × 观察日期的规则命中列表。
- `draftFilters/appliedFilters`、应用、重置、规则大类/小类、命中等级、排序字段/方向、每页条数、已应用摘要、加载/错误/空态、分页、响应式样式和操作按钮均有实现。
- 列表 mapper 正确优先采用 display_name/name，再回退 code；字段 camelCase 映射本身不是名称丢失点。
- 单条 rule-only detail 能显示 evidence payload；候选模式能显示月度概率、horizon、金额和趋势。
- 前端 build 成功。

阻塞：

1. **P0 display lookup 断点**：`CompositeDetectorResultRepository.load_entity_display_lookup()` 明确返回空 DataFrame。稳定月度 lookup 中示例实体存在完整 master 名称，但 Detector API 无法取得。
2. **P1 中文名称未接入**：catalog 的 10 个 `detector_name` 均为英文，service 和前端均直接使用该值。
3. **P1 entity-all-hits detail 未实现**：列表只传 clueId，进入单条规则详情；示例实体实际有 3 个命中，但详情只取一个 clue。
4. **P1 活动后端版本陈旧**：API 进程未加载当前 HEAD 的新增路由/详情增强。
5. **P2 美化策略文档已定位**：文档实际位于 `daily_work/notes/new_ver/前端美化/clues页面美化策略（待实现）.md`；初次审计漏检了 `daily_work` 目录层级。Release B 已完整读取并按该文档实施、测试。

## 8. 数量口径结论

`expected_semantic_difference`，但 UI 文案不足以让用户理解差异。

- 顶部“规则命中数”来自 `/daily-detector/status.clue_count`；service 对指定企业和日期读取原始 clue 行并直接 `len(clues)`，不接受 detector category/id/level 筛选，也不去重。
- “已应用：N 条结果”来自 `/daily-detector/clues.total`；service 先应用 detector category/id/level，保留 hit_flag，再按 `detector_clue_id` 去重。
- 因此 12350 与 7069 可以分别代表“该企业该日全部存储命中行”和“当前筛选后的可见、去重结果”。当前稳定样例在无额外筛选时 status 与 list 均为 4488，说明分页 total 没有被误写为当前页长度。
- 最小修复是将顶部文案改为“全部规则命中行（筛选前）”或让 summary 同步应用同一筛选/去重契约；不是修改分页。

## 9. 当前可验证范围与物化结束后补验

已验证：源码、配置、隔离临时目录测试、2026-01-01 稳定 registry/API、稳定 2025-12 `entity_display_lookup` 的示例行、当前 GET API、前端 build。

当前进程已退出，但批次状态未完成；后续仅需补验：

1. 诊断 8 个 `completed=false` 的退出原因；不得直接重启或覆盖，retry 需遵守 versioned run-id 与 staging 保留规则；
2. 每个目标日期、企业、Detector 是否在 observation registry 中精确解析到新 run；
3. 新 run 的 validation/publish 状态、日期覆盖和 0-hit 空态；
4. 新 run API 是否仍不 fallback，且名称/中文/detail 缺口修复后再做端到端回归；
5. 当前未完成路径在稳定后再读取结果表；本轮不等待、不读取、不判错。

## 10. 测试结果

| 命令 | 结果 | 分类 |
|---|---|---|
| 根目录 pytest：Release A rules/config/component validation/incremental | 12 passed | Detector regression passed |
| `project/` pytest：clues API/display lookup fixture/detail/pagination | 11 passed，2 warnings | API fixture tests passed；warning 为 httpx deprecation 与 pytest cache 权限 |
| `npm run build` | success，43 modules | frontend build passed |
| HEAD 更新后 resume/incremental pytest | 5 passed | 新增 resume fast-path 与 component isolation passed |
| 首次混合 pytest（错误 cwd） | 4 collection errors，0 tests run | test invocation error：`app` import path，不是产品失败 |

注意：display lookup fixture 测试使用 InMemory repository，未覆盖生产 `CompositeDetectorResultRepository.load_entity_display_lookup()` 返回空表的路径，因此“测试通过”与真实 API 名称缺失并不矛盾。

## 11. 最终结论

Release A 后端代码与稳定历史发布链路可以认定完成；当前 2025 全年新 run 状态为 `implementation complete / current materialization incomplete / no live process`。Release B 不能认定完成，阻塞集中在展示映射、中文 catalog、实体级多 Detector 详情和运行服务版本，而不是 10 个算法未实现。Release C 的跨日聚合已有代码和测试，但未在当前活动服务中完整暴露。
