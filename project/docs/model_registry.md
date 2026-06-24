# 模型注册

`ModelRegistry` 负责让 FastAPI 后端加载当前 active backbone 模型，并在模型不可用时自动回退。

配置文件：

```text
configs/model_registry.yaml
```

示例：

```yaml
active_backbone: palive_lgbm

models:
  palive_lgbm:
    active_version: null
    fallback: palive_interval_proxy
  palive_interval_proxy:
    active_version: builtin
  palive_bgnbd:
    active_version: null
    fallback: palive_interval_proxy
```

## 支持的模型

- `palive_lgbm`：训练产物模型，预测未来 H 天停购风险，再转换为候选 `p_alive`。
- `palive_interval_proxy`：内置 fallback，不依赖模型文件。
- `palive_bgnbd`：候选接口，当前不作为唯一主干方向。

## 加载校验

加载 `palive_lgbm` 时会检查：

- `model.pkl` 是否存在。
- `feature_schema.json` 是否存在。
- 当前推理特征是否覆盖训练所需字段。

如果 active 模型缺失、schema 不匹配或加载失败，系统不会让 dry-run 或 `/api/v0/backbone/predict` 崩溃，而是回退到 `palive_interval_proxy`，并返回警告：

```text
MODEL_REGISTRY_FALLBACK_TO_INTERVAL_PROXY
```

## 晋级模型

训练完成后可用脚本更新 active version：

```bash
python scripts/promote_model.py --model-name palive_lgbm --version 20260624123000
```

晋级只修改 `configs/model_registry.yaml`。真实模型产物位于 `artifacts/models/`，不提交到代码仓库。

## 输出限制

所有 backbone 输出当前仍是算法验证结果。即使字段名为 `p_alive`，在完成真实数据回测、校准和业务验收前，也不能解释为正式业务概率。
