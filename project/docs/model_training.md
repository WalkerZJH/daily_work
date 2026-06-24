# 主干模型训练

当前阶段目标是让“训练数据构建 -> 模型训练 -> 模型注册 -> 后端推理调用”跑通，用真实数据验证算法合理性。这里不做正式排期、不做完整工单系统、不做复杂产品闭环。

## 训练样本

分析单元固定为：

```text
org_code × product_line_code
```

训练样本粒度为：

```text
org_code, product_line_code, origin_date
```

标签 `label_churn_H` 的定义：

- `1`：该 unit 在 `origin_date` 之后 `horizon_days` 天内没有有效采购。
- `0`：该 unit 在未来 `horizon_days` 天内有有效采购。
- 未来窗口不完整的样本会丢弃。

有效采购口径集中在 `app/features/label_builder.py`：默认要求 `purchase_qty > 0`，且 `void_qty = 0` 或缺失。

## 特征

特征由 `app/features/unit_snapshot_builder.py` 生成，只使用 `origin_date` 及之前的数据，避免时间穿越。

第一版特征覆盖：

- 基础字段：地区、医院等级、生产企业等。
- RFM：最近采购间隔、各窗口采购次数、活跃天数。
- 采购间隔：均值、中位数、标准差、MAD、超期比例等。
- 采购量和金额：30/90/180/365 天窗口，以及近期相对基线比例。
- 品规：90 天和 365 天 SKU 数、收缩比例。
- 价格：90 天可比单价均值、最小值、最大值、近期相对基线比例。
- 配送：配送率、到货率、配送延迟、拒绝类状态数量。
- 需求形态：`adi`、`cv2`、`demand_profile`。

缺失值允许保留为 NaN，不强行填 0。

## 构建训练集

```bash
python scripts/build_training_dataset.py --config configs/palive_training.yaml
```

也可以指定输出路径：

```bash
python scripts/build_training_dataset.py --config configs/palive_training.yaml --output artifacts/training/palive_training_dataset.csv
```

## 训练 palive_lgbm

```bash
python scripts/train_lgbm_churn.py --config configs/palive_training.yaml --input artifacts/training/palive_training_dataset.csv
```

脚本优先尝试 LightGBM；如果未安装 LightGBM，则使用 `scikit-learn` 的 `HistGradientBoostingClassifier` fallback。

训练按时间切分训练集和验证集，不做随机切分。

输出指标包括：

- ROC-AUC
- PR-AUC
- Brier score
- Precision@K
- Recall@K
- 分箱校准表

模型产物保存到：

```text
artifacts/models/palive_lgbm/{timestamp}/
```

目录内包含：

- `model.pkl`
- `feature_schema.json`
- `model_card.json`
- `metrics.json`
- `training_config.yaml`

`model_card.json` 必须说明分析单元、标签定义、预测窗口、训练/验证时间范围、模型类型、特征 schema 版本和限制。当前所有模型均为实验候选，不是生产校准概率。
