# A1 — Canonical Manifest & Stage Contract Registry

## 1. 目标

消除 Skill metadata 多真源，建立 9 个生产 Stage 的版本化 Contract Registry。

## 2. In Scope

- Manifest loader。
- Stage Contract loader/validator。
- Manifest 1.1.0。
- Stage Contract schema 和 9 个 contract。

## 3. Out of Scope

不修改 Run State 阶段判断。

## 4. 允许修改路径

- `skills/manifest.json`
- `skills/stage-contracts.json`
- `scripts/skills/manifest.py`
- `docs/contracts/`
- `tests/test_skill_manifest.py`
- `tests/test_stage_contract_registry.py`

超出路径必须先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md`，说明原因、影响、兼容和验证。

## 5. 必须实现

1. Runtime/Installer/Router 可从 Manifest 读取。
2. 9 个 Stage Contract 字段完整。
3. compat aliases 和 backend dependencies 可解析。
4. 禁止重复 skill name / stage order / input type collision。
5. Contract hash 可进入 release lock。

## 6. 测试

- Manifest schema。
- 9/9 contract validation。
- duplicate / missing / bad reference negative tests。
- installer/route compatibility tests。

## 7. 成功标准

- 所有 Skill identity 由一个真源加载。
- 9 个 Stage Contract 可稳定读取。

## 8. 依赖与并发

依赖 A0。

## 9. Agent 交付报告

必须输出：修改文件、Schema 变化、迁移影响、测试命令与真实结果、未完成项、风险、建议评审重点。
