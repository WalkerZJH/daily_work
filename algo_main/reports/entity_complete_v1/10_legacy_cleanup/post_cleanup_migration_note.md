# Post-Cleanup Migration Note For Future Codex Runs

不得再搜索、读取、引用 reports/alive_prediction_* 作为 fallback。
不得再读取 data/04_facts/alive_prediction 或 data/05_features/alive_prediction。
旧 one-shot / M3 / M4 / M5 / M7 legacy 输出不可再作为当前结论。
缺失模块必须在 entity_complete_v1 或 entity_complete_v2 下重新实现。
