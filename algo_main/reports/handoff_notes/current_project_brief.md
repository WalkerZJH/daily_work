# algo_main 当前项目简要交接说明

更新时间：2026-06-26

## 当前工作重心

当前项目重心已经从原来的前后端验证链路转移到纯算法工程 `algo_main/`。暂时不考虑前端、后端 API、权限、工单系统、Agent、Dify/LangChain、自动调度或业务闭环。

当前阶段只做：

- 数据理解
- 数据清洗
- schema 标准化
- 字段可靠性验证
- 正则拆列与枚举映射沉淀
- 特征工程准备
- 传统机器学习/统计模型设计准备
- 模型交付结构准备

## 业务数据背景

主要数据表：`BS_Agent_DingDan`

当前真实数据源来自 Microsoft SQL Server，数据原先截取自 ClickHouse。未来数据量可能变大，并可能替换为 ClickHouse。当前本地不部署数据库，策略是：

```text
SQL Server / 授权导出
-> CSV/Parquet 小样本或全量分批缓存
-> 本地 Parquet
-> pandas / DuckDB / Polars 分析处理
-> clean parquet
-> facts/features/train sets
```

不要提交 `.env`、真实数据库连接信息、真实数据导出、真实模型文件。

## 当前已完成的主要工作

### 1. 纯算法项目骨架

已在 `algo_main/` 下建立 Python 包 `alg`，使用 `src/` 布局：

```text
algo_main/src/alg/
  data_access/
  schema/
  cleaning/
  facts/
  features/
  routing/
  tasks/
  models/
  validation/
  evaluation/
  artifacts/
  utils/
```

环境文件：

```text
algo_main/environment.yml
```

环境名：`ml`。

不包含 PyTorch/TensorFlow，只包含 Jupyter、pandas、polars、duckdb、pyarrow、SQLAlchemy、pyodbc、scikit-learn、lightgbm、xgboost 等传统数据分析和机器学习依赖。

### 2. 第一阶段数据清洗资产

按 `daily_work/notes/new_ver/第一阶段数据清洗工作安排.md` 建立：

```text
algo_main/notebooks/01_BS_Agent_DingDan_EDA_and_Cleaning.ipynb
algo_main/docs/data_dictionary/BS_Agent_DingDan字段说明.md
algo_main/configs/data_schema/bs_agent_dingdan_schema.yaml
algo_main/configs/mappings/order_status_map.yaml
algo_main/configs/mappings/hospital_grade_map.yaml
algo_main/configs/mappings/drug_category_map.yaml
algo_main/configs/mappings/ownership_map.yaml
algo_main/exports/eda/.gitkeep
algo_main/exports/clean/.gitkeep
algo_main/exports/mappings/.gitkeep
algo_main/exports/raw/.gitkeep
```

### 3. Notebook 重构

Notebook 已经被重构为 orchestration-only，即只做类似 `main` 的顺序调用，不再承载大量函数定义。

核心函数已迁移到：

```text
algo_main/src/alg/cleaning/bs_agent_dingdan.py
```

当前 Notebook 代码单元中 `def` 数量应为 `0`。

### 4. 数值字段脱敏新口径

旧口径已废弃：不再认为所有数值字段分别乘独立随机数。

新口径：

- 数量字段统一乘同一个随机数 `q`：采购数量、配送数量、到货数量、退回数量、作废数量。
- 金额字段统一乘同一个随机数 `m`：采购金额、配送金额、到货金额。
- 采购价格仍可能单独脱敏，暂不作为核心分析字段。

允许：

- `delivery_rate = 配送数量 / 采购数量`
- `arrival_rate = 到货数量 / 配送数量`
- `overall_arrival_rate = 到货数量 / 采购数量`
- 数量趋势
- 金额趋势
- 订单频次趋势
- 金额字段之间的相对关系

禁止：

- 使用 `采购金额 / 采购数量` 推断真实单价
- 使用 `采购价` 与 `采购金额 / 采购数量` 做一致性校验

这些规则已写入：

```text
algo_main/configs/data_schema/bs_agent_dingdan_schema.yaml
algo_main/docs/data_dictionary/BS_Agent_DingDan字段说明.md
algo_main/src/alg/cleaning/bs_agent_dingdan.py
algo_main/notebooks/01_BS_Agent_DingDan_EDA_and_Cleaning.ipynb
```

### 5. 医疗机构等级新口径

clean 表中直接使用字段【医疗机构等级】，不再使用【医疗机构详细等级】作为主清洗依据。

【医疗机构详细等级】暂认为错误或不可信，只保留 raw/audit，不进入 clean 主字段，也不进入算法字段。

输出字段：

```text
hospital_level_raw
hospital_level_label
hospital_level_code
```

`hospital_level_code` 是有序类别变量，不能默认当作连续变量。

### 6. 测试状态

最近一次在 `algo_main/` 下运行：

```powershell
C:\Users\admin\anaconda3\python.exe -m pytest tests
```

结果：

```text
12 passed
```

测试覆盖：

- 项目结构存在
- schema / Notebook / mapping 文件存在
- 数值脱敏 policy 存在
- 医疗机构等级策略正确
- Notebook 不再定义函数
- 清洗模块关键函数可导入
- temporal split 基础逻辑
- model package manifest 基础逻辑

## 新智能体应优先阅读的文件

建议按以下顺序阅读。

### A. 最新任务与业务口径

```text
daily_work/notes/new_ver/第一阶段数据清洗工作安排.md
```

这是当前第一阶段数据清洗任务的主要依据。

如需要了解更早需求背景，可读：

```text
daily_work/notes/raw_need/项目需求.md
```

但当前阶段不要继续做前后端、detector、P_alive 或工单。

### B. 算法工程入口说明

```text
algo_main/README.md
algo_main/environment.yml
algo_main/pyproject.toml
algo_main/.gitignore
```

重点确认项目定位、环境创建、本地数据策略、当前不做事项。

### C. 第一阶段 schema 与字段字典

```text
algo_main/docs/data_dictionary/BS_Agent_DingDan字段说明.md
algo_main/configs/data_schema/bs_agent_dingdan_schema.yaml
```

这是字段含义、清洗规则、算法可用性、数值脱敏边界的核心文件。

### D. 映射配置

```text
algo_main/configs/mappings/order_status_map.yaml
algo_main/configs/mappings/hospital_grade_map.yaml
algo_main/configs/mappings/drug_category_map.yaml
algo_main/configs/mappings/ownership_map.yaml
```

这些文件管理订单状态、医院等级、药品类别、所有制形式的初版映射。

### E. Notebook 主流程

```text
algo_main/notebooks/01_BS_Agent_DingDan_EDA_and_Cleaning.ipynb
```

只应作为 main/orchestration 看待。不要把大量函数重新写回 Notebook。

### F. Notebook 背后的函数模块

```text
algo_main/src/alg/cleaning/bs_agent_dingdan.py
```

这是当前最重要的代码文件。它包含：

- 路径构造
- schema/env 加载
- SQL Server TOP N 读取
- SQL 分批写 Parquet
- Parquet 读取
- 基础字段 profile
- 唯一标识符检查
- 地区映射
- 药品编码一致性检查
- 数值脱敏检查
- 状态映射
- 医院等级映射
- 企业字段关系检查
- 药品类别/所有制映射
- clean 表构建
- 数据质量报告生成

### G. 测试

```text
algo_main/tests/test_bs_agent_dingdan_cleaning_assets.py
algo_main/tests/test_project_structure.py
algo_main/tests/test_temporal_split.py
algo_main/tests/test_model_package_manifest.py
```

尤其是 `test_bs_agent_dingdan_cleaning_assets.py`，它约束 Notebook 不再定义函数，也约束数值脱敏和医院等级口径。

### H. Notebook 重建脚本

```text
algo_main/scripts/rebuild_cleaning_notebook.py
```

如果 Notebook 被手工改乱，可以用它重建 orchestration-only 版本。

## 当前不应优先看的旧项目目录

以下目录仍存在，但当前工作重心已不在这里：

```text
project/
front_end/
```

除非明确要恢复前后端，否则新智能体不应继续推进 FastAPI、Vue、detector API、权限、工单或 health 页面。

## 注意事项

1. 读取中文文件时必须显式 UTF-8，PowerShell 默认编码容易导致乱码。
2. 不要读取、打印或提交 `.env` 内容。
3. 不要提交真实数据、Parquet、CSV、模型文件或导出结果。
4. Notebook 只做 main 流程，函数代码放入 `src/alg/**/*.py`。
5. 当前没有执行真实 SQL Server 全量读取，也没有生成真实 clean 数据。
6. 若要试跑，先用 `mode="sql_sample"` 和较小 `max_rows`。
7. 若要全量缓存，必须走 `sql_full_to_parquet` + `chunksize`，不要一次性拉进 pandas。

## 建议下一步

听取用户的数据二次清洗要求，具体要求可以参考d`aily_work\notes\new_ver\二次清洗.md`
