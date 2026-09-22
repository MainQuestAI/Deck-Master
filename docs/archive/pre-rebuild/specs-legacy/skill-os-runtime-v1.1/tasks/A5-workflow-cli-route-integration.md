# A5 — Workflow CLI & Route Integration

## 1. 目标

提供统一 `workflow` 命令组，并让 route、next-step、run-state 共用 Workflow Resolver。

## 2. In Scope

- CLI。
- compatibility aliases。
- route / next-step / run-state projection。
- typed events。

## 3. Out of Scope

不改 Autopilot 行为。

## 4. 允许修改路径

- `scripts/deck_master.py`
- `scripts/runtime/skill_route.py`
- `scripts/runtime/next_step.py`
- `tests/test_workflow_cli.py`
- `tests/test_skill_route.py`

超出路径必须先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md`，说明原因、影响、兼容和验证。

## 5. 必须实现

1. canonical commands 全部可用。
2. 旧命令继续可用。
3. 四个状态入口一致。
4. JSON stdout / exit code 符合 Spec。
5. Manifest 驱动 route。

## 6. 测试

- CLI positive/negative。
- route consistency matrix。
- alias compatibility。
- no raw mutation for validate/status。

## 7. 成功标准

- Stack A 全链路可在 CLI 验收。

## 8. 依赖与并发

依赖 A1-A4。

## 9. Agent 交付报告

必须输出：修改文件、Schema 变化、迁移影响、测试命令与真实结果、未完成项、风险、建议评审重点。
