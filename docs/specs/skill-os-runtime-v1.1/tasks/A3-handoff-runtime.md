# A3 — Skill Handoff Runtime

## 1. 目标

实现 append-only Handoff prepare、consume、stale、supersede 和 current projection。

## 2. In Scope

- Handoff schema。
- prepare / list / inspect / consume。
- idempotency。
- event。
- file lock。

## 3. Out of Scope

不实现用户审批策略。

## 4. 允许修改路径

- `scripts/workflow/handoff.py`
- `docs/contracts/skill-handoff.v1.schema.json`
- `tests/test_skill_handoff.py`

超出路径必须先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md`，说明原因、影响、兼容和验证。

## 5. 必须实现

1. Exit validation 不通过时不能 prepare。
2. 相同 fingerprint 幂等。
3. 上游变化标记 stale。
4. superseded 记录保留。
5. current_handoff 只是投影。

## 6. 测试

- prepare/duplicate/consume/stale/supersede。
- concurrent write。
- unsafe path / bad hash。

## 7. 成功标准

- 所有 Stage Transition 可生成可审计 Handoff。

## 8. 依赖与并发

依赖 A2。

## 9. Agent 交付报告

必须输出：修改文件、Schema 变化、迁移影响、测试命令与真实结果、未完成项、风险、建议评审重点。
