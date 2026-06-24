# C2 — Skill Docs & Manifest Conformance

## 1. 目标

把公开 Skill 从命令索引升级为完整工作流入口，并用自动检查防止漂移。

## 2. In Scope

- 14 public SKILL.md。
- 4 compat SKILL.md。
- doc structure validator。
- Manifest/frontmatter consistency。

## 3. Out of Scope

不改变 Skill 名称。

## 4. 允许修改路径

- `skills/*/SKILL.md`
- `scripts/skills/validator.py`
- `tests/test_skill_doc_contract.py`

超出路径必须先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md`，说明原因、影响、兼容和验证。

## 5. 必须实现

1. Use When / Do Not Use / First Checks / Forcing Questions / Runtime Ownership / Allowed Commands / Exit Artifacts / Next Skill / Stop Conditions / Safety Rules 全部存在。
2. 文档命令真实存在。
3. exit artifacts 与 Manifest 一致。
4. compat wrapper 指向 public stage。

## 6. 测试

- all skill docs。
- bad section/frontmatter/command。
- compatibility trigger。

## 7. 成功标准

- 100% public skill conformance。

## 8. 依赖与并发

依赖 A1，可在 B5 后收口。

## 9. Agent 交付报告

必须输出：修改文件、Schema 变化、迁移影响、测试命令与真实结果、未完成项、风险、建议评审重点。
