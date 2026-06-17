# Endgame Runtime Historical Evidence Archive

日期：2026-06-17

## 归档定位

本目录保存 `origin/codex/deck-master-endgame-runtime` 历史分支中的少量高价值证据。

这些文件只用于追溯 2026-06 Run OS 迁移期间的思路、验证记录和 QA 证据。当前生产基线以 `main` 在 v0.9.13 之后的 suite runtime、product capabilities、setup/readiness 和 UC story review 结构为准。

## 已归档文件

| 文件 | 来源 | 价值 |
|---|---|---|
| `run-os-migration-map.md` | `docs/migration/2026-06-run-os-migration-map.md` | Run OS 迁移保护清单，记录当时必须保护的能力边界 |
| `run-os-implementation-log.md` | `docs/migration/2026-06-run-os-implementation-log.md` | P0/P1 实现日志，记录阶段验证命令和能力演进 |
| `p1-run-os-core-qa-report.md` | `docs/migration/qa/p1-run-os-core/qa-report.md` | P1 Run OS Core QA 报告，保留质量阻断、交付写回、资产健康等验证结论 |

## 明确排除

以下内容未迁入当前 `main`：

- `docs/migration/qa/**` 下的大批截图。
- `docs/migration/review-cockpit-smoke/**` 下的浏览器 smoke 截图和 JSON。
- 旧分支中的 runtime、workspace、generation、preview、review、quality、skill 代码。
- 旧分支中的测试代码。
- 旧分支中会覆盖当前 v0.9.12 / v0.9.13 结构的 spec、product capability、setup/readiness 文档。

排除原因：这些内容属于旧实现分支的过程证据或旧 runtime 结构。当前主线已经有后续版本的运行时、产品能力套件和 UC story review 修复，直接迁移会增加误用风险。

## 使用规则

1. 仅作为历史证据读取。
2. 不作为当前路线图、当前实现说明或 release note 引用。
3. 如需复用旧 smoke 思路，请优先查看 `docs/qa/review-cockpit-smoke-scenarios.md`，那里已经转成当前主线可执行的覆盖矩阵。
4. 不从本目录反向恢复旧代码或旧截图目录。
