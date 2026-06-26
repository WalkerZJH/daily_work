# 1. Conda 环境：面向 Jupyter、数据分析、传统 ML、SQL Server

建议环境名：

```bash
ml
```

建议使用 `mamba` 创建环境，因为它兼容 conda 环境管理逻辑，但解析依赖通常更快；`environment.yml` 是 conda 生态内标准的环境描述文件，可以包含 `name`、`channels`、`dependencies` 等字段。([Mamba](https://mamba.readthedocs.io/en/latest/user_guide/mamba.html?utm_source=chatgpt.com "Mamba User Guide — documentation"))

## `environment.yml`

```yaml
name: ml

channels:
  - conda-forge
  - defaults

dependencies:
  # ===== 基础运行环境 =====
  - python=3.11
  - pip
  - ipykernel
  - jupyterlab
  - notebook
  - ipywidgets

  # ===== 数值计算与表格处理 =====
  - numpy
  - scipy
  - pandas
  - polars
  - pyarrow
  - duckdb

  # ===== 数据库连接 =====
  - sqlalchemy
  - pyodbc
  - python-dotenv

  # ===== 传统机器学习 =====
  - scikit-learn
  - imbalanced-learn
  - statsmodels
  - lightgbm
  - xgboost

  # ===== 特征、模型持久化、模型交付 =====
  - joblib
  - cloudpickle
  - skops
  - pyyaml
  - pydantic

  # ===== 可视化与 EDA =====
  - matplotlib
  - seaborn
  - plotly
  - missingno

  # ===== 数据质量与开发工具 =====
  - pandera
  - pytest
  - tqdm
  - rich
  - loguru
  - black
  - ruff

  # ===== 可选 pip 包 =====
  - pip:
      - category-encoders
```

创建环境：

```bash
mamba env create -f environment.yml
mamba activate ml
python -m ipykernel install --user --name ml --display-name "Python (ml)"
jupyter lab
```

如果没有 mamba，可以先在 base 环境安装：

```bash
conda install -n base -c conda-forge mamba
```

SQL Server 连接还需要系统层安装 **Microsoft ODBC Driver for SQL Server**。Python 里的 `pyodbc` 只是绑定，Windows 上通常还需要单独安装 Microsoft ODBC Driver 18；微软文档说明 Driver 18 是用于连接 SQL Server/Azure SQL 等的原生 ODBC 驱动。([微软学习](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server?view=sql-server-ver17&utm_source=chatgpt.com "Download ODBC Driver for SQL Server - ODBC Driver for SQL Server | Microsoft Learn"))

---

# 2. 为什么这个环境适合你当前项目

你当前不是深度学习项目，主要需求是：

```text
SQL 数据抽取
→ 脏数据清洗
→ 特征工程
→ 多算法对比
→ 时间切分验证
→ 模型文件交付
→ 后续可接入业务
```

所以环境重点不是 PyTorch/TensorFlow，而是：

|模块|作用|
|---|---|
|`polars`|大表清洗、特征聚合、Lazy 执行|
|`duckdb`|本地 Parquet 查询、临时分析、SQL 化验证|
|`pyarrow/parquet`|中间数据缓存|
|`scikit-learn`|传统 ML 主框架|
|`lightgbm/xgboost`|表格数据强基线|
|`statsmodels`|时间序列、统计检验、趋势建模|
|`pandera/pydantic`|schema 校验、输入输出约束|
|`joblib/skops`|模型持久化与交付|
|`jupyterlab`|EDA、清洗验证、算法探索|

Polars 的 Lazy API 会对查询做优化，例如 predicate pushdown、projection pushdown、slice pushdown、公共子计划消除等；这比直接 pandas 全量读入更适合你未来数据变大的情况。([Polars](https://docs.pola.rs/user-guide/lazy/optimizations/?utm_source=chatgpt.com "Optimizations - Polars user guide"))  
DuckDB 可以直接查询 Parquet，并且会并行处理 Parquet、自动下推过滤条件、仅读取相关列，适合本地离线分析和缓存层查询。([DuckDB](https://duckdb.org/docs/current/guides/file_formats/query_parquet?utm_source=chatgpt.com "Querying Parquet Files – DuckDB"))

---

# 3. 推荐项目目录

建议目录如下：

```text
gyl_algorithm_project/
│
├─ environment.yml
├─ README.md
├─ .env.example
├─ pyproject.toml
│
├─ configs/
│  ├─ data_source.yaml              # SQL Server / ClickHouse / Parquet 数据源配置
│  ├─ schema_mapping.yaml           # 原始列名 → 标准列名映射
│  ├─ regex_column_rules.yaml       # 正则拆列规则
│  ├─ feature_registry.yaml         # 通用特征定义
│  ├─ task_registry.yaml            # 任务定义：die预测/流失风险/价值估计等
│  ├─ analyzer_registry.yaml        # 不同订单分布 → 不同分析器路由
│  └─ validation.yaml               # 时间留出验证配置
│
├─ data/
│  ├─ 00_external/                  # 外部手工文件、字典表、映射表
│  ├─ 01_raw/                       # 原始抽取数据，只做落盘，不修改语义
│  ├─ 02_interim/                   # 字段拆分、类型修正、临时中间层
│  ├─ 03_cleaned/                   # 清洗后的标准订单表
│  ├─ 04_facts/                     # 月粒度/周粒度事实表
│  ├─ 05_features/                  # 通用特征表和任务特征表
│  ├─ 06_train_sets/                # 按任务生成的训练/验证/测试数据
│  └─ 07_outputs/                   # detector 结果、预测结果、导出结果
│
├─ notebooks/
│  ├─ 00_data_access_check.ipynb
│  ├─ 01_eda_raw_schema.ipynb
│  ├─ 02_cleaning_probe.ipynb
│  ├─ 03_feature_probe.ipynb
│  ├─ 04_task_die_label_probe.ipynb
│  ├─ 05_model_compare.ipynb
│  └─ 06_backtest_analysis.ipynb
│
├─ src/
│  ├─ gyl_alg/
│  │  ├─ __init__.py
│  │  │
│  │  ├─ data_access/
│  │  │  ├─ mssql_loader.py
│  │  │  ├─ clickhouse_loader.py
│  │  │  ├─ parquet_loader.py
│  │  │  └─ base.py
│  │  │
│  │  ├─ schema/
│  │  │  ├─ standard_columns.py
│  │  │  ├─ schema_mapper.py
│  │  │  ├─ regex_splitter.py
│  │  │  └─ validators.py
│  │  │
│  │  ├─ cleaning/
│  │  │  ├─ clean_orders.py
│  │  │  ├─ code_quality.py
│  │  │  ├─ missing_values.py
│  │  │  ├─ duplicate_check.py
│  │  │  └─ outlier_check.py
│  │  │
│  │  ├─ facts/
│  │  │  ├─ build_monthly_fact.py
│  │  │  ├─ build_weekly_fact.py
│  │  │  └─ aggregation_utils.py
│  │  │
│  │  ├─ features/
│  │  │  ├─ base_features.py
│  │  │  ├─ activity_features.py
│  │  │  ├─ value_features.py
│  │  │  ├─ trend_features.py
│  │  │  ├─ stability_features.py
│  │  │  ├─ seasonality_features.py
│  │  │  └─ feature_builder.py
│  │  │
│  │  ├─ routing/
│  │  │  ├─ distribution_profiler.py
│  │  │  ├─ demand_shape_gate.py
│  │  │  ├─ analyzer_router.py
│  │  │  └─ routing_rules.py
│  │  │
│  │  ├─ tasks/
│  │  │  ├─ die_prediction/
│  │  │  │  ├─ label_builder.py
│  │  │  │  ├─ dataset_builder.py
│  │  │  │  ├─ metrics.py
│  │  │  │  └─ task_config.yaml
│  │  │  │
│  │  │  ├─ value_estimation/
│  │  │  │  ├─ label_builder.py
│  │  │  │  ├─ dataset_builder.py
│  │  │  │  ├─ metrics.py
│  │  │  │  └─ task_config.yaml
│  │  │  │
│  │  │  └─ anomaly_detection/
│  │  │     ├─ label_builder.py
│  │  │     ├─ dataset_builder.py
│  │  │     ├─ metrics.py
│  │  │     └─ task_config.yaml
│  │  │
│  │  ├─ models/
│  │  │  ├─ base_model.py
│  │  │  ├─ sklearn_models.py
│  │  │  ├─ tree_models.py
│  │  │  ├─ time_series_models.py
│  │  │  ├─ rule_based_models.py
│  │  │  └─ model_factory.py
│  │  │
│  │  ├─ validation/
│  │  │  ├─ temporal_split.py
│  │  │  ├─ rolling_backtest.py
│  │  │  ├─ die_event_check.py
│  │  │  └─ leakage_check.py
│  │  │
│  │  ├─ evaluation/
│  │  │  ├─ classification_metrics.py
│  │  │  ├─ ranking_metrics.py
│  │  │  ├─ regression_metrics.py
│  │  │  ├─ business_metrics.py
│  │  │  └─ report_builder.py
│  │  │
│  │  ├─ artifacts/
│  │  │  ├─ save_model_package.py
│  │  │  ├─ load_model_package.py
│  │  │  ├─ manifest.py
│  │  │  └─ export_bundle.py
│  │  │
│  │  └─ utils/
│  │     ├─ paths.py
│  │     ├─ logging.py
│  │     ├─ hashing.py
│  │     ├─ time_utils.py
│  │     └─ io.py
│
├─ experiments/
│  ├─ die_prediction/
│  │  ├─ exp_001_rule_baseline/
│  │  ├─ exp_002_logistic_regression/
│  │  ├─ exp_003_lightgbm/
│  │  └─ exp_004_xgboost/
│  │
│  ├─ value_estimation/
│  │  ├─ exp_001_average_amount/
│  │  └─ exp_002_lgbm_regressor/
│  │
│  └─ anomaly_detection/
│     ├─ exp_001_iqr_rule/
│     └─ exp_002_isolation_forest/
│
├─ artifacts/
│  ├─ candidate_models/             # 实验模型，不一定交付
│  ├─ promoted_models/              # 通过验证、准备交付的模型包
│  └─ handoff/                      # 给同事/主项目使用的最终交付包
│
├─ reports/
│  ├─ data_quality/
│  ├─ feature_quality/
│  ├─ model_comparison/
│  ├─ temporal_backtest/
│  └─ handoff_notes/
│
├─ scripts/
│  ├─ 01_extract_raw.py
│  ├─ 02_clean_orders.py
│  ├─ 03_build_facts.py
│  ├─ 04_build_features.py
│  ├─ 05_train_task.py
│  ├─ 06_run_backtest.py
│  ├─ 07_export_model_bundle.py
│  └─ 08_score_latest.py
│
└─ tests/
   ├─ test_schema_mapping.py
   ├─ test_cleaning.py
   ├─ test_feature_builder.py
   ├─ test_temporal_split.py
   ├─ test_die_label_builder.py
   └─ test_model_package.py
```

---

# 4. 数据分层设计

你的数据很脏，所以必须严格区分数据层次。不要把“清洗、特征、训练集、预测结果”混在一个目录。

## 数据层定义

|层级|目录|含义|是否允许人工修改|
|---|---|---|---|
|L0|`00_external/`|外部映射表、字典、人工规则|可以|
|L1|`01_raw/`|SQL Server 原始抽取结果|不建议|
|L2|`02_interim/`|列名拆分、类型转换、正则解析后的中间表|可以重建|
|L3|`03_cleaned/`|标准字段订单表|不应人工改|
|L4|`04_facts/`|月/周/日粒度事实表|不应人工改|
|L5|`05_features/`|算法特征表|不应人工改|
|L6|`06_train_sets/`|任务训练集、验证集、测试集|不应人工改|
|L7|`07_outputs/`|预测结果、风险名单、debug 输出|可导出|

推荐最核心的基础表是：

```text
data/04_facts/monthly_order_fact.parquet
```

字段示例：

```text
entity_id
hospital_code
product_line_code
enterprise_code
month
order_count
amount_sum
quantity_sum
active_days
first_order_date
last_order_date
days_since_last_order
```

其中 `entity_id` 建议统一生成，例如：

```text
hospital_code + "::" + product_line_code
```

如果未来企业 code 不止一个，可以改成：

```text
hospital_code + "::" + product_line_code + "::" + enterprise_code
```

---

# 5. 列名脏、字段需要正则拆分时怎么放

这部分应该放在：

```text
src/gyl_alg/schema/
```

而不是放在 cleaning 或 features 里。

原因是：  
**列名解析属于 schema 标准化，不是业务清洗，也不是特征工程。**

建议三个模块分开：

```text
schema_mapper.py     # 原始列名 → 标准列名
regex_splitter.py    # 从复杂列名/字段中正则拆出结构化信息
validators.py        # 校验标准字段是否齐全、类型是否正确
```

配置文件：

```yaml
# configs/schema_mapping.yaml

raw_to_standard:
  DingDanRiQi: order_date
  YiYuanCode: hospital_code
  ChanXianCode: product_line_code
  QiYeCode: enterprise_code
  JinE: amount
  ShuLiang: quantity
```

正则拆分规则：

```yaml
# configs/regex_column_rules.yaml

product_line_parse:
  source_col: raw_product_line_name
  patterns:
    - name: product_line_code_from_bracket
      regex: ".*?\\[(?P<product_line_code>[A-Za-z0-9_-]+)\\].*"
    - name: product_line_name_before_code
      regex: "^(?P<product_line_name>.*?)\\s*[-_]\\s*(?P<product_line_code>[A-Za-z0-9]+)$"
```

这样做的好处是：  
以后列名规则变了，不用改算法，只改配置。

---

# 6. 多任务、多模型、多指标怎么组织

你不能把所有模型都放在一个 `models/` 目录里直接训练。因为不同任务的标签、指标、切分方式都不同。

应该是：

```text
tasks/
  die_prediction/
  value_estimation/
  anomaly_detection/
```

每个任务内部负责：

```text
label_builder.py      # 标签定义
dataset_builder.py    # 训练样本构造
metrics.py            # 指标定义
task_config.yaml      # 任务配置
```

而 `models/` 只提供算法实现：

```text
models/
  sklearn_models.py
  tree_models.py
  time_series_models.py
  rule_based_models.py
```

也就是说：

```text
task = 解决什么问题
model = 用什么算法解决
metric = 如何评价
analyzer/router = 哪类对象用哪套分析方法
```

不要混在一起。

---

# 7. 订单分布路由：L0.5 应该保留，而且要前置

你提到“不同订单分布情况使用不同分析器”，这就是你之前说的 **L0.5 需求形态分类闸门**。它不属于前后端适配，而属于算法路由，应该保留。

建议放在：

```text
src/gyl_alg/routing/
  distribution_profiler.py
  demand_shape_gate.py
  analyzer_router.py
  routing_rules.py
```

## 路由的输入

使用 `monthly_order_fact`，对每个 `entity_id` 计算订单分布画像：

```text
history_months
active_months
active_ratio
zero_month_ratio
mean_amount
std_amount
cv_amount
last_order_gap_months
max_consecutive_zero_months
monthly_order_count_mean
monthly_order_count_std
trend_slope
seasonality_strength
```

## 初始路由类型

建议先设计 5 类：

|路由类型|含义|推荐分析器|
|---|---|---|
|`stable_regular`|稳定、连续、有周期采购|趋势 + 分类模型|
|`sparse_regular`|稀疏但有规律|间隔模型 + 规则模型|
|`bursty_irregular`|爆发式、不规律|异常检测 + 鲁棒统计|
|`new_entity`|历史太短|冷启动规则|
|`inactive_or_dead`|已长期无采购|不再预测 die，转入已流失确认|

示例：

```python
def route_entity(profile):
    if profile.history_months < 4:
        return "new_entity"

    if profile.last_order_gap_months >= 6:
        return "inactive_or_dead"

    if profile.active_ratio >= 0.7 and profile.cv_amount <= 1.0:
        return "stable_regular"

    if profile.active_ratio < 0.3:
        return "sparse_regular"

    return "bursty_irregular"
```

这部分先用规则就够，不要一开始就训练一个路由模型。你的当前数据质量还没有稳定到适合学习路由器。

---

# 8. 时间序列“留一/留多月”验证怎么设计

你这里的验证不是普通随机划分，而是**时间滚动留出验证**。

正确逻辑是：

```text
在 cutoff 月份 T：
  只使用 T 及以前的数据构造特征
  对当时仍可能存活的 entity 预测 die 风险
  查看 T+1 到 T+H 的留出月份中它是否真的 die / 不再采购
```

这里 H 可以是 1、2、3、6 个月。你说“留一法实际上可能留多个月”，在时间序列里更准确叫：

```text
rolling-origin temporal backtest
```

或：

```text
rolling cutoff validation
```

## 样本构造方式

设：

```text
T = cutoff_month
H = holdout_horizon_months
G = grace_months
```

例如：

```text
T = 2025-06
H = 3
G = 0 或 1
```

那么：

```text
训练特征窗口：<= 2025-06
测试观察窗口：2025-07 ~ 2025-09
```

标签可以定义为：

```text
die_label = 1
当且仅当 entity 在测试观察窗口内没有任何订单
```

但这只是“未来 H 个月未采购”，不一定是永久死亡。所以建议命名为：

```text
die_within_horizon
```

而不是绝对的 `is_dead`。

更严谨的定义：

```text
die_within_horizon = 1
如果 entity 在 cutoff T 时仍被认为 alive，
且在 (T, T+H] 内没有任何订单。
```

如果你希望允许一个缓冲期：

```text
die_within_horizon = 1
如果 entity 在 (T, T+H+G] 内没有任何订单。
```

其中 `G` 是 grace window，用于避免正常采购间隔较长的对象被误判为死亡。

---

# 9. die 预测任务的指标不要只用 AUC

这个任务的最终结果大概率是“给业务方一批风险对象”，因此它本质上更像**风险排序任务**，不是纯分类任务。

建议指标分三类。

## 9.1 分类指标

```text
PR-AUC
ROC-AUC
F1
precision
recall
Brier score
```

如果正样本很少，`PR-AUC` 比 `ROC-AUC` 更有意义。

## 9.2 排序指标

```text
Precision@K
Recall@K
Lift@K
Top-K hit rate
```

例如：

```text
预测风险最高的 100 个对象中，有多少在留出窗口中真的 die？
```

这比单纯 AUC 更接近业务使用方式。

## 9.3 业务指标

```text
captured_amount_at_k
risk_amount_sum
avoidable_loss_proxy
```

如果当前没有利润数据，可以先用：

```text
近 N 月平均采购金额
```

作为价值 proxy。

---

# 10. 模型文件交付规范

你提到“完成每次算法更新，取得算法模型文件后，需要方便转交”。这里必须建立标准模型包，而不是只交 `.pkl`。

scikit-learn 官方文档明确指出，`pickle`、`joblib`、`cloudpickle` 都基于 pickle 协议，加载时可能执行任意代码；`skops.io` 相对更安全，可以检查和控制受信任类型；`joblib` 的优势是加载性能和内存映射，但同样要求信任来源。官方文档还说明，使用这些 Python 对象持久化方式时，不支持跨 scikit-learn 版本加载模型。([Scikit-learn](https://scikit-learn.org/stable/model_persistence.html?utm_source=chatgpt.com "11. Model persistence — scikit-learn 1.9.0 documentation"))

因此建议交付包结构如下：

```text
artifacts/promoted_models/
  die_prediction/
    die_lgbm_v20260625_001/
      model.skops                 # 首选交付格式
      model.joblib                # 内部可信环境可用
      preprocessor.joblib         # 特征处理器/编码器/标准化器
      feature_schema.json         # 输入特征名、类型、顺序
      label_definition.yaml       # die 标签定义
      task_config.yaml            # 任务配置
      train_config.yaml           # 训练参数
      validation_report.json      # 时间留出验证结果
      metrics.csv                 # 各 cutoff 指标
      feature_importance.csv      # 特征重要性
      prediction_sample.csv       # 推理样例
      manifest.json               # 模型包总说明
      README.md                   # 给同事看的使用说明
```

`manifest.json` 必须包含：

```json
{
  "model_id": "die_lgbm_v20260625_001",
  "task": "die_prediction",
  "model_type": "lightgbm",
  "entity_grain": ["hospital_code", "product_line_code"],
  "train_data_range": ["2023-01", "2025-03"],
  "validation_cutoffs": ["2025-04", "2025-05", "2025-06"],
  "holdout_horizon_months": 3,
  "feature_version": "feat_v2",
  "label_version": "die_label_v1",
  "code_version": "git_commit_hash",
  "python_version": "3.11",
  "created_at": "2026-06-25"
}
```

交付时应该导出到：

```text
artifacts/handoff/
  die_lgbm_v20260625_001.zip
```

这才是可转交给同事的东西。

---

# 11. 实验目录：允许同一任务跑多个模型

你需要同时保留实验过程和最终交付模型。建议区别：

```text
experiments/          # 试验记录，不一定可交付
artifacts/            # 模型产物，可能可交付
reports/              # 给人看的结论
```

示例：

```text
experiments/die_prediction/exp_003_lightgbm/
  config.yaml
  train.log
  metrics.csv
  cutoff_metrics.csv
  feature_importance.csv
  error_cases.csv
  model.joblib
  notes.md
```

当某个实验通过验证，再提升为 promoted model：

```text
artifacts/promoted_models/die_prediction/die_lgbm_v20260625_001/
```

最后导出：

```text
artifacts/handoff/die_lgbm_v20260625_001.zip
```

这解决的是：

```text
实验很多
模型很多
但最终交付物必须少而清晰
```

---

# 12. 当前最推荐的算法路线

按照你的描述，die 预测应该先从以下顺序做：

## 阶段 A：规则 baseline

目的不是追求最强，而是建立可解释下限。

```text
last_order_gap_months
active_ratio
max_consecutive_zero_months
recent_amount_drop_ratio
```

示例规则：

```text
若最近 3 个月无采购，且历史 active_ratio >= 0.5，则标记为高风险
```

## 阶段 B：传统 ML baseline

模型：

```text
LogisticRegression
RandomForest
HistGradientBoosting
LightGBM
XGBoost
```

其中 LightGBM / XGBoost 适合表格特征，但必须防止时间泄漏。

## 阶段 C：路由后多分析器

```text
stable_regular      → 趋势变化 + 分类模型
sparse_regular      → 间隔模型 + 规则阈值
bursty_irregular    → 异常检测 + 分位数规则
new_entity          → 冷启动规则
inactive_or_dead    → 不预测，只确认状态
```

不要一开始就把所有对象扔给一个统一模型。订单分布差异太大时，统一模型很可能学到的是“谁历史活跃度低”，而不是“谁真的要 die”。

---

# 13. 关键设计结论

我建议你当前就按下面的技术边界推进：

```text
1. 环境：
   conda/mamba + Jupyter + Polars + DuckDB + scikit-learn + LightGBM/XGBoost

2. 数据：
   SQL Server 抽取后落 Parquet，不以 CSV 作为算法缓存主格式

3. 目录：
   raw/interim/cleaned/facts/features/train_sets/outputs 分层

4. 清洗：
   schema 标准化、正则拆列、质量校验独立成模块

5. 特征：
   先构建 monthly_order_fact，再构建任务特征

6. 任务：
   die_prediction/value_estimation/anomaly_detection 分任务管理

7. 模型：
   同一任务允许多模型实验，实验模型和交付模型分离

8. 路由：
   保留 L0.5 demand_shape_gate，根据订单分布选择分析器

9. 验证：
   使用 rolling cutoff temporal backtest，不做随机划分

10. 交付：
    每个模型必须导出完整 model bundle，而不是单独 .pkl
```

最小可执行主链路应该是：

```text
SQL Server
→ raw parquet
→ schema mapping / regex split
→ cleaned orders
→ monthly_order_fact
→ distribution profile
→ analyzer routing
→ task dataset
→ rolling cutoff validation
→ model comparison
→ promoted model bundle
→ handoff zip
```

后续 Codex prompt 应该围绕这条链路写，不要让 Codex 去做前端、API、权限、业务工单或自然语言线索整合。