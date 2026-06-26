# alg 算法实验工程

本目录是面向医药供应链订单风险分析的纯算法工程。当前目标是先完成数据理解、清洗规则沉淀、特征工程和传统机器学习验证，不做前端、后端服务、权限管理、工单系统、LangChain/Dify/Agent 封装。

## 项目定位

- 字段理解、数据质量诊断和 schema 标准化。
- 正则拆列、枚举映射和人工 review 表沉淀。
- 文件型分析层：授权导出的 CSV/Parquet -> 本地 Parquet 缓存 -> DuckDB/Polars/pandas 查询处理。
- 医疗机构 x 产品线等实体粒度的特征工程。
- 传统机器学习、规则模型、时间序列/间隔模型对比。
- 时间留出验证与 rolling cutoff backtest。
- 模型文件、特征 schema、验证报告和 handoff 包交付。

## 当前不做

当前阶段不做前端页面、FastAPI 后端服务、权限系统、工单系统、LLM Agent、自动调度和分布式计算。未来如果算法方案稳定，再考虑交给前后端同事适配业务系统。

## 本地数据策略

本地不部署数据库。Microsoft SQL Server / ClickHouse 数据通过授权流程导出为 CSV 或 Parquet 后放入本地数据目录，优先转换为 Parquet 缓存，再做分析。不要提交真实数据文件、数据库账号、密码、IP 或连接串。

目录职责：

- `data/` 是算法主链路运行时数据层，供后续 facts、features、train sets 使用。
- `exports/` 是人工复核、EDA、mapping review、小样本报告层，不作为算法主链路输入。
- `artifacts/` 是模型与交付物层。

推荐主链路：

```text
company export
-> data/01_raw
-> data/02_interim
-> data/03_cleaned
-> data/04_facts
-> data/05_features
-> data/06_train_sets
-> experiments
-> artifacts/promoted_models
-> artifacts/handoff
```

## 环境创建

推荐使用 mamba：

```bash
mamba env create -f environment.yml
mamba activate alg-ml
python -m ipykernel install --user --name alg-ml --display-name "Python (alg-ml)"
jupyter lab
```

如果没有 mamba，可以使用 conda：

```bash
conda env create -f environment.yml
conda activate alg-ml
python -m ipykernel install --user --name alg-ml --display-name "Python (alg-ml)"
jupyter lab
```

## 模块职责

- `src/alg/data_access/`: 文件型数据读取、SQL Server/ClickHouse 抽取接口预留。
- `src/alg/schema/`: 标准字段、字段映射、正则拆列和 schema 校验。
- `src/alg/cleaning/`: 订单清洗、缺失值、重复、异常值和编码质量检查。
- `src/alg/facts/`: 周/月粒度事实表构建。
- `src/alg/features/`: 通用特征、任务特征与特征注册。
- `src/alg/routing/`: 不同订单分布和需求形态的算法路由。
- `src/alg/tasks/`: die prediction、价值估计、异常检测三类任务数据集与指标。
- `src/alg/models/`: 规则模型、传统 ML、树模型、时间序列模型封装。
- `src/alg/validation/`: 时间切分、rolling backtest、泄漏检查。
- `src/alg/evaluation/`: 统计指标、业务指标和对比报告。
- `src/alg/artifacts/`: 模型交付包保存、加载、manifest 和导出。
- `src/alg/utils/`: 路径、日志、哈希、时间和 IO 工具。

## 第一阶段清洗任务

第一阶段聚焦 `BS_Agent_DingDan` 字段理解、EDA、初步清洗和清洗规则沉淀：

- Notebook: `notebooks/01_BS_Agent_DingDan_EDA_and_Cleaning.ipynb`
- 原始字段字典: `docs/data_dictionary/BS_Agent_DingDan字段说明.md`
- v2 输出字段字典: `docs/data_dictionary/BS_Agent_DingDan_v2_outputs.md`
- 机器 schema: `configs/data_schema/bs_agent_dingdan_schema.yaml`
- 映射配置: `configs/mappings/*.yaml`
- EDA/review 输出: `exports/eda/`、`exports/mappings/`
- 正式清洗输出: `data/03_cleaned/bs_agent_dingdan_model_base.parquet`
- 人工复核 sample 输出: `exports/clean/bs_agent_dingdan_clean_sample_v2.csv` 和 `exports/clean/bs_agent_dingdan_audit_sample.csv`

本阶段禁止把脱敏后的数值字段用于业务算法结论；这些字段仅用于脱敏破坏程度检查。

## BS_Agent_DingDan v2 Pipeline

稳定后的 v2 清洗流程已冻结为可复用入口：

```bash
set PYTHONPATH=src
python -m alg.cleaning.bs_agent_dingdan_pipeline \
  --table BS_Agent_DingDan \
  --output-format parquet \
  --generate-model \
  --generate-quality-report \
  --no-generate-clean \
  --no-generate-audit
```

生产级清洗入口是 `alg.cleaning.bs_agent_dingdan_pipeline.run_bs_agent_dingdan_cleaning_pipeline`。
`src/alg/cleaning/bs_agent_dingdan.py` 只保留内部 helper 和兼容函数，不作为主流程入口。

Notebook `notebooks/01_BS_Agent_DingDan_EDA_and_Cleaning.ipynb` 只用于复核和汇报展示；
它调用同一个 pipeline 入口，不维护第二套清洗逻辑。
clean/audit/review 输出字段语义以 `docs/data_dictionary/BS_Agent_DingDan_v2_outputs.md` 为准。

默认行为只生成 `data/03_cleaned/bs_agent_dingdan_model_base.parquet` 和
`exports/eda/bs_agent_dingdan_quality_report_v2.md`，不生成 clean/audit CSV。
如果已通过 editable install 安装本包，则不需要手动设置 `PYTHONPATH`。
`clean_sample_v2` 与 `audit_sample` 仅用于 sample/debug 和人工复核。

Raw cache 默认使用 `data/01_raw/BS_Agent_DingDan.parquet`，并写入同名元数据
`data/01_raw/BS_Agent_DingDan.meta.json`。默认缓存策略为
`--cache-policy reuse_if_enough`：当缓存行数大于等于 `max_rows` 时复用，否则回源 SQL
并覆盖缓存。可用参数：

- `--cache-policy always_reuse`：只要缓存存在就复用。
- `--cache-policy refresh` 或 `--refresh-cache`：无条件回源 SQL 并覆盖缓存。
- `--no-use-cache`：不读取缓存，强制回源 SQL。

`model_base` 是统一稳定输入，不是最终 `X_train`；clean/audit/review 输出的字段解释以 v2 输出字段字典为准：

- `row_uid`、`order_detail_id` 是追溯键，不直接进入 X。
- `purchase_time` 是排序、切分和聚合的时间索引，不应原样当作连续数值特征。
- `region_dirty_flag` 是质量控制字段，正式训练默认不进入 X。
- `order_phase_code`、`delivery_state_code`、`order_terminal_flag`、`order_failure_flag`
  是状态语义字段，若任务目标涉及完成、失败、终止、到货，可能造成标签泄漏。
- `delivery_rate`、`arrival_rate` 等比例字段来自数量字段，不代表配送时长。
- 不同任务应通过 feature view 配置从 `model_base` 生成各自的小 X，不提前生成巨大通用 X 表。
- 下游 facts/features 默认应从 `data/03_cleaned/bs_agent_dingdan_model_base.parquet` 读取。

后续可以新增：

- `feature_view_alive_prediction.yaml`
- `feature_view_quantity_forecast.yaml`
- `feature_view_delivery_quality.yaml`

每个 feature view 需要明确 input table、entity grain、time grain、target、
allowed columns、excluded columns、leakage rules、null handling 和 categorical encoding strategy。

## 时间留出验证

在 cutoff 月份 T，只使用 T 及以前的数据构造特征；预测当时仍可能存活的 entity 是否会在 T+1 到 T+H 的留出窗口内 die；再用留出窗口中的真实订单情况验证预测是否正确。

## 最小测试

```bash
pytest tests
```

## 后续优先任务

1. 执行 `BS_Agent_DingDan` Notebook，确认字段可靠性、重复记录语义、状态映射和数值脱敏破坏程度。
2. 基于 Parquet/DuckDB/Polars 打通数据清洗 -> facts -> features 的百万行级单机链路。
3. 为 die prediction 建立 rolling cutoff 数据集、baseline 规则模型和 LightGBM/XGBoost 对比实验。
