# C3 — Legacy Run, ppt-* & External Package Compatibility

## 1. 目标

保证升级不会破坏旧 Run、旧 Skill 调用和外部完整能力包。

## 2. In Scope

- workflow bootstrap。
- legacy preview adapter。
- ppt wrappers。
- generic external package manifest。
- migration/rollback。

## 3. Out of Scope

不删除旧 alias。

## 4. 允许修改路径

- `scripts/workflow/migration.py`
- `scripts/skills/installer.py`
- `skills/ppt-*/`
- `docs/migration/`
- `tests/test_skill_os_migration.py`

超出路径必须先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md`，说明原因、影响、兼容和验证。

## 5. 必须实现

1. 旧 Run inference 不伪造 approval。
2. 旧 alias 输出 canonical artifacts。
3. external real dir/symlink 均保留。
4. manifest + smoke + contract 判断 production capable。
5. rollback。

## 6. 测试

- old run snapshots。
- foreign symlink / real dir / adapter-only。
- rollback。
- old CLI prompts。

## 7. 成功标准

- 现有用户升级后主链路不丢失。

## 8. 依赖与并发

依赖 A1-A5、B3-B4。

## 9. Agent 交付报告

必须输出：修改文件、Schema 变化、迁移影响、测试命令与真实结果、未完成项、风险、建议评审重点。
