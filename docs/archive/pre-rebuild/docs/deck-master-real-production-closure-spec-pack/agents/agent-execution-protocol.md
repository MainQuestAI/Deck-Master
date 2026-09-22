# Agent Execution Protocol

## 1. 评审基线原则

本包是规划基线，不是最终开发事实。

每个开发分支开始时，Agent 必须在仓库提交实际执行 Spec：

```text
docs/specs/real-production-closure/implementation/
  baseline-lock.json
  implementation-spec.md
  implementation-spec.json
  spec-deviation-log.md
  test-evidence.md
```

后续 PR 评审必须：

> 以该分支实际提交的 implementation spec 为 baseline，不能直接把本规划包中未被采用的设计当成缺陷。

## 2. Spec Drift

任何偏差必须记录：

| 字段 | 内容 |
|---|---|
| task_id | 原任务 |
| planned | 原设计 |
| actual | 实际设计 |
| reason | 原因 |
| impact | 影响 |
| compatibility | 兼容性 |
| tests | 证明 |
| reviewer_status | accepted / rejected / pending |

未记录的关键偏差视为缺陷。

## 3. 单任务执行规则

1. 只实现当前 task。
2. 先读依赖 task 的结果。
3. 不以“顺手优化”为由扩范围。
4. 新 artifact 必须有 schema version。
5. 坏输入不得覆盖好状态。
6. Production 不允许 fixture fallback。
7. 关键写操作必须原子化。
8. 所有外部结果必须做 run/session/path validation。
9. 不能声称运行了未实际运行的测试。
10. 完成后输出标准交付报告。

## 4. 并行规则

允许并行：

- A2 与 A4，在 A1 contract 冻结后；
- B1 与 B3 的框架；
- C1 与 C3。

不允许并行修改同一状态语义：

- Generation status；
- Final readiness；
- Release activation。

## 5. PR 规则

每个 PR 包含：

- Task ID；
- actual spec；
- changed files；
- migration；
- tests；
- evidence；
- known limits；
- deviation log；
- rollback。

## 6. Codex 核验标记

涉及以下事实必须写“需要 Codex 核验”直至实际执行：

- 当前 HEAD；
- 测试数；
- 命令可运行；
- dependency installed；
- clean install；
-真实 benchmark；
- 本机 suite status；
- release artifact。
