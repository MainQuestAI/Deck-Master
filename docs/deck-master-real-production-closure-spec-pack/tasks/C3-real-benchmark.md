# C3 — Real Case Benchmark

## 1. 元数据

| 字段 | 内容 |
|---|---|
| Task ID | `C3` |
| Repository | `MainQuestAI/Deck-Master` |
| Depends on | Stack B complete; A0 benchmark candidates |
| Delivery | 独立提交或独立 PR，必须可回滚 |

## 2. 目标

用真实客户项目证明生产闭环和业务效果。

## 3. In Scope

- real case schema。
- local-only inputs。
- baseline。
- metrics。
- manual review。
- aggregate report。

## 4. Out of Scope

不把客户原文提交到公开仓库；不以 fixture 代替 real case。

## 5. 必须实现

1. 建立 ≥3 个 real case。
2. 原始路径留本地。
3. Repo 保存脱敏 metadata。
4. 自动采集时间、接受率、修改次数、artifact validity。
5. 人工记录质量结论。
6. 生成 aggregate RC report。
7. 失败案例不得删除。

## 6. 允许 / 预期修改路径

- `benchmarks/cases/real_*` metadata
- `scripts/benchmark/`
- `docs/qa/real-benchmark/`
- `tests/test_real_benchmark_contract.py`

超出路径需要在 `spec-deviation-log.md` 记录原因、影响和验证。

## 7. 测试

- local path absent。
- missing baseline。
- invalid artifact。
- acceptance calculation。
- aggregate median。
- privacy scan。

## 8. 成功标准

- 3 case 完整。
- 指标达到 Master Spec。
- 0 私有原文入库。
- 报告可复核。

## 9. 风险

真实项目差异大，必须同时保留定量指标和人工说明。

## 10. Agent 交付报告

Agent 完成后必须输出：

1. 实际修改文件；
2. 与本 Spec 的偏差；
3. 数据迁移；
4. 测试命令和真实结果；
5. 未完成项；
6. 风险；
7. 建议评审重点。
