# B5 — Workflow Autopilot v2

## 1. 目标

把现有直接命令循环升级为 Contract-aware、Approval-aware、Evidence-first 的工作流执行器。

## 2. In Scope

- mode policies。
- validate/action/exit/handoff loop。
- preauthorization consumption。
- repair routing。
- evidence report。

## 3. Out of Scope

不自动回答业务问题；不自动 client export。

## 4. 允许修改路径

- `scripts/workflow/autopilot.py`
- `scripts/deck_master.py`
- `tests/test_workflow_autopilot_v2.py`

超出路径必须先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md`，说明原因、影响、兼容和验证。

## 5. 必须实现

1. 每步执行统一算法。
2. 高影响审批停下。
3. 自动门禁继续。
4. preauth scope 校验。
5. final export 永远停止。
6. repair owner routing。

## 6. 测试

- all modes。
- approval stop。
- preauth valid/expired/out-of-scope。
- stale handoff。
- no-stage-advance loop。
- final export stop。

## 7. 成功标准

- Autopilot 无审批绕过。
- 每步 Evidence 完整。

## 8. 依赖与并发

依赖 B1-B4。

## 9. Agent 交付报告

必须输出：修改文件、Schema 变化、迁移影响、测试命令与真实结果、未完成项、风险、建议评审重点。
