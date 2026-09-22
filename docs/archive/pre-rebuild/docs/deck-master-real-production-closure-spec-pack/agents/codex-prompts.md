# Codex Execution Prompts

## 1. Master Integrator

```text
你正在开发 MainQuestAI/Deck-Master。

Baseline:
- origin/main @ 14fc43dc6e955928100f02f0e82af5b833c29177
- 先核验，不要假定本地 HEAD 一致。

先阅读：
- README.md
- 00-master-spec.md
- 01-baseline-gap-register.md
- 02-cross-repo-contracts.md
- agents/agent-execution-protocol.md

第一步只执行 A0。
在仓库提交实际 implementation spec、baseline lock、capability lock 草案和 deviation log。
不要在 A0 实现业务功能。

完成后输出：
1. 核验事实；
2. 当前 Gap；
3. 实际 Stack 拆分；
4. 分支 implementation spec 路径；
5. 测试基线；
6. 需要用户决定的阻断项。
```

## 2. Stack A

```text
实现 Stack A：v0.9.14 Real Production Runtime。

必须先读取 A0 实际 implementation spec。
按 A1 → A2/A3/A4 → A5 顺序执行。
核心目标：Production 不再生成 placeholder；真实 Agent 结果可回写；PPT Master 产出真实 HTML/PDF/PNG/PPTX。

硬约束：
- Deck Master 零内置 LLM Provider。
- Run 是唯一状态源。
- completed 必须有有效 artifact。
- fixture 只允许 fixture/dev。
- 所有偏差写 spec-deviation-log.md。

每个 Task 独立提交。
完成后运行全量测试和一条真实非 fixture smoke。
```

## 3. Stack B

```text
实现 Stack B：v0.9.15 Artifact Truth & Final Readiness。

先确认 Stack A 已完成并合并。
按 B1 → B2/B3 → B4 → B5 执行。

硬目标：
- fake extension、corrupt package、checksum mismatch、stale artifact 全部阻断；
- parse failure 必须 P0；
- final_readiness.json 是唯一最终结论；
- Export、Review Workspace、Benchmark 不得复制 readiness 逻辑；
- Production placeholder 回归由 CI 阻断。
```

## 4. Stack C

```text
实现 Stack C：v0.9.16 Release, Benchmark & RC。

按 C1/C3 → C2/C4 → C5 执行。

硬目标：
- release tree 自包含；
- 删除或移动原 repo 后 CLI 仍可用；
- clean install、upgrade、rollback；
- ≥3 real cases；
- RC report 缺任一证据必须 blocked；
- 只提交脱敏 benchmark metadata 和 metrics。
```

## 5. 单任务模板

```text
你正在执行 {TASK_ID}。

请读取：
- 00-master-spec.md
- 对应 Stack Spec
- tasks/{TASK_FILE}
- 分支内实际 implementation spec
- spec-deviation-log.md

只实现本 Task。
不要扩展到后续 Task。
先写出：
1. 当前事实；
2. 计划修改文件；
3. 兼容策略；
4. 测试矩阵。

实现后：
- 运行 Task tests；
- 运行相关 regression；
- git diff --check；
- 更新 test-evidence.md；
- 更新 deviation log；
- 输出真实结果和未完成项。
```
