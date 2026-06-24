# 真实数据库 smoke test

当前 v0 阶段只实现单次可运行的风险评估和 smoke test。复杂增量更新、自动周期巡检、定期重训暂不实现。

本阶段目标：

1. 从真实数据库订单宽表中读取一个小时间窗口。
2. 执行数据质量检查。
3. 构建 FeatureSnapshot。
4. 执行 backbone prediction；active 模型不可用时 fallback 到 interval proxy。
5. 执行 dry-run，输出少量 P_alive 候选预览和 summary。

默认窗口策略：

- 若未提供 `date_from/date_to`，使用 `as_of_date` 向前 14 天。
- `row_limit` 默认 5000，且不会超过 5000。
- 不做全量读取，不做全量训练。
- SQL 查询只选择 canonical schema 所需列，不使用 `SELECT *`。

命令行运行：

```bash
python scripts/run_database_smoke_test.py --as-of-date 2026-06-24 --days 14 --row-limit 5000
```

可选过滤：

```bash
python scripts/run_database_smoke_test.py \
  --as-of-date 2026-06-24 \
  --days 14 \
  --row-limit 5000 \
  --enterprise-code ENT001 \
  --province-code 320000
```

输出目录：

```text
artifacts/smoke_tests/{timestamp}/summary.json
```

真实结果文件不提交到代码仓库，仓库中只保留 `artifacts/smoke_tests/README.md`。

## API

`POST /api/v0/smoke-test/database`

用于真实数据库小窗口 smoke test，返回 summary、最多 10 条 `palive_preview` 和 warning 汇总。
该 API 默认不落盘真实结果；命令行脚本才会写入 `artifacts/smoke_tests/{timestamp}/summary.json`。

`POST /api/v0/smoke-test/freshness`

只报告当前窗口的 `max_order_time`、`row_count`、时间范围和 warning。当前不持久化 last_check，不触发自动推理或自动重训。

## 后续扩展原则

未来可扩展为：

1. 每日检查订单表 `max(order_time)` 或变更时间戳。
2. 如果有新数据，则运行当天推理。
3. 推理只使用当前 active model。
4. 每周或每月累计足量数据后重新构建训练集。
5. 训练完成后进入 model registry。
6. 人工审核后切换 active model。

当前不实现上述完整流程，也不引入 Celery、APScheduler、Airflow、Prefect 等调度系统。

所有 P_alive、主干风险分和 RiskCardCandidate 都是算法验证阶段的候选输出，不是正式业务工单，也不是已校准概率。
