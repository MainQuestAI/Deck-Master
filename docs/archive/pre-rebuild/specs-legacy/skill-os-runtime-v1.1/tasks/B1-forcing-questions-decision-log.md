# B1 — Forcing Questions & Decision Log

## 1. 目标

把访谈能力纳入各 Stage Contract，并让关键答案成为可追踪事实。

## 2. In Scope

- Question resolver。
- Decision record schema/runtime。
- brief/planner/sourcing/producer question packs。
- blocking question logic。

## 3. Out of Scope

不新增独立访谈 Skill；不内置模型。

## 4. 允许修改路径

- `scripts/workflow/questions.py`
- `scripts/workflow/decisions.py`
- `skills/stage-contracts.json`
- `docs/contracts/decision-record.v1.schema.json`
- `tests/test_workflow_questions.py`

超出路径必须先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md`，说明原因、影响、兼容和验证。

## 5. 必须实现

1. 只返回当前缺口问题。
2. required / assumption-allowed 可区分。
3. blocking 未答时 exit validation 失败。
4. answer 绑定 fingerprint。
5. stale answer 可识别。

## 6. 测试

- stage-specific question matrix。
- no-question happy path。
- required unanswered。
- stale decision。

## 7. 成功标准

- 访谈深度由 Runtime 约束，不依赖 Agent 自觉。

## 8. 依赖与并发

依赖 Stack A。

## 9. Agent 交付报告

必须输出：修改文件、Schema 变化、迁移影响、测试命令与真实结果、未完成项、风险、建议评审重点。
