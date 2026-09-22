# B3 — Canonical Final Readiness

## 1. 元数据

| 字段 | 内容 |
|---|---|
| Task ID | `B3` |
| Repository | `MainQuestAI/Deck-Master` |
| Depends on | B1, B2 |
| Delivery | 独立提交或独立 PR，必须可回滚 |

## 2. 目标

建立唯一最终 readiness，消除 CLI、UI、Export、Benchmark 的口径分散。

## 3. In Scope

- readiness schema。
- check registry。
- blocker aggregation。
- CLI。
- run-state integration。
- freshness。

## 4. Out of Scope

不修复各个 Gate 的业务规则。

## 5. 必须实现

1. 新增 `runtime/final_readiness.py`。
2. 输出 `final_readiness.json`。
3. required checks 按 profile 配置。
4. 每个 check 返回 status、reason、refs。
5. status 只允许 ready/degraded/blocked。
6. Run 最终 stage 读取它。
7. 所有 consumer 禁止复制判断逻辑。

## 6. 允许 / 预期修改路径

- `scripts/runtime/final_readiness.py`
- `scripts/runtime/run_state_resolver.py`
- `scripts/deck_master.py`
- `docs/contracts/`
- `tests/test_final_readiness.py`

超出路径需要在 `spec-deviation-log.md` 记录原因、影响和验证。

## 7. 测试

- all ready。
- each single blocker。
- multiple blockers。
- degraded optional。
- stale refresh。
- profile variation。
- deterministic order。

## 8. 成功标准

- CLI/UI/export 同一 run 返回同一结论。
- 每个 blocker 有可执行 next action。

## 9. 风险

旧 API 可能依赖旧字段；需保留 derived compatibility fields。

## 10. Agent 交付报告

Agent 完成后必须输出：

1. 实际修改文件；
2. 与本 Spec 的偏差；
3. 数据迁移；
4. 测试命令和真实结果；
5. 未完成项；
6. 风险；
7. 建议评审重点。
