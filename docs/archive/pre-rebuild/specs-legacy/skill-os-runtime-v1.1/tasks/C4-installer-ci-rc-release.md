# C4 — Installer, CI, RC & Release Closure

## 1. 目标

把 Skill OS 的合同、命令、迁移和 E2E 固化到 release 和 CI。

## 2. In Scope

- release tree。
- capability lock。
- schema validation。
- clean install。
- RC gate。
- docs / release notes。

## 3. Out of Scope

CI 不运行私有客户原文。

## 4. 允许修改路径

- `scripts/skills/installer.py`
- `scripts/runtime/rc_gate.py`
- `.github/workflows/`
- `docs/releases/`
- `tests/`

超出路径必须先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md`，说明原因、影响、兼容和验证。

## 5. 必须实现

1. release 包含 Stage Contracts / schemas / migrations。
2. JSON Schema 实际验证，不只是 parse。
3. Codex/Claude temp HOME。
4. route consistency / handoff / approval / autopilot / bootstrap smoke。
5. archive/checksum。

## 6. 测试

- Linux CI。
- temp HOME。
- moved repo。
- install/upgrade/rollback。
- invalid contract lock。
- RC pass/block fixtures。

## 7. 成功标准

- Main CI 全绿。
- Release Artifact 可验证。
- 缺任何 required evidence 时 RC blocked。

## 8. 依赖与并发

依赖 C1-C3。

## 9. Agent 交付报告

必须输出：修改文件、Schema 变化、迁移影响、测试命令与真实结果、未完成项、风险、建议评审重点。
