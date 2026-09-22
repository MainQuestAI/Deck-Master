# A0 — Baseline & Version Freeze

## 1. 目标

锁定当前 main、实际命令、Artifact 真源、版本号和实现偏差，避免后续任务按不同假设开发。

## 2. In Scope

- main / release / suite / contract 基线。
- 当前测试与安装事实。
- 实现 Spec、Deviation Log、Progress、Test Evidence。

## 3. Out of Scope

不修改 Runtime 行为。

## 4. 允许修改路径

- `docs/specs/skill-os/implementation/`
- `docs/specs/README.md`

超出路径必须先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md`，说明原因、影响、兼容和验证。

## 5. 必须实现

1. 记录 main SHA。
2. 统一目标版本 1.1.0 的映射。
3. 列出所有兼容命令和 schema 真源。
4. 记录本机外部能力路径，只写脱敏事实。
5. 建立 deviation log。

## 6. 测试

- JSON / Markdown parse。
- `git diff --check`。
- 记录当前全量测试，不得掩盖失败。

## 7. 成功标准

- 后续任务拥有唯一基线。
- 版本映射无歧义。

## 8. 依赖与并发

第一任务；完成前禁止其他 Stack 合并。

## 9. Agent 交付报告

必须输出：修改文件、Schema 变化、迁移影响、测试命令与真实结果、未完成项、风险、建议评审重点。
