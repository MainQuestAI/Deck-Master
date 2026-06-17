# Deck Master Endgame Runtime Branch Retirement Audit

日期：2026-06-17

## 结论

`origin/codex/deck-master-endgame-runtime` 应按历史分支退役处理。它保留了 Run OS 迁移期间的证据和 Review Cockpit smoke 思路，但分支代码基线已经落后于当前 `main`。

本轮处理建议是：只归档少量证据文档和测试思路，等待本归档 PR 合入后，再由老板确认是否删除远程历史分支。

## 分支事实

| 项目 | 值 |
|---|---|
| 历史分支 | `origin/codex/deck-master-endgame-runtime` |
| 分支头 | `0ff9b55` |
| 与当前 `main` 分叉点 | `b58732deb7131c4e4a7bdcf82c1fb976b9092586` |
| 当前执行基线 | `main @ e812ea4` |
| 新归档分支 | `codex/archive-endgame-runtime-evidence` |

## 为什么不能直接合并

该分支相对当前 `main` 的差异已经超出文档归档范围，直接合并会产生高风险覆盖：

| 风险面 | 观察 |
|---|---|
| CI / 基础仓库结构 | 历史分支删除 `.github/workflows/ci.yml`、多份 `.gstack` QA 报告和基线文件 |
| v0.9.12 / v0.9.13 文档 | 历史分支删除 suite runtime、product capability suite、release notes、QA 文档等当前主线证据 |
| Product Capabilities | 历史分支缺少当前 `product_capabilities/**` 和 suite skill 拆分结构 |
| Runtime / Setup | 历史分支会删除或替换当前 `runtime/setup_status.py`、`runtime/run_state_resolver.py`、`runtime/orchestration.py` 等后续主线结构 |
| Skill Suite | 历史分支会删除当前 `skills/deck-planner`、`deck-review`、`ppt-master`、`ppt-library`、`ppt-deck-pro-max`、`ppt-quality-gate` 等能力入口 |
| 测试矩阵 | 历史分支测试数量和覆盖目标停留在 Run OS 迁移阶段，会覆盖当前 UC story review 后的测试形态 |
| Review Cockpit | 历史分支有旧 smoke 脚本和截图证据，但当前主线已经引入 source badge、quality freshness、render readiness 等新版行为 |

## 可迁移资产

| 资产 | 迁移方式 | 当前位置 |
|---|---|---|
| Run OS 迁移保护清单 | 原文归档，新增 README 标注历史用途 | `docs/archive/endgame-runtime-2026-06/run-os-migration-map.md` |
| Run OS 实现进度日志 | 原文归档，作为阶段验证记录 | `docs/archive/endgame-runtime-2026-06/run-os-implementation-log.md` |
| P1 Run OS Core QA 报告 | 原文归档，作为 QA 结论证据 | `docs/archive/endgame-runtime-2026-06/p1-run-os-core-qa-report.md` |
| Review Cockpit smoke 思路 | 提炼成当前主线场景矩阵 | `docs/qa/review-cockpit-smoke-scenarios.md` |

## 明确排除资产

| 资产 | 处理 | 原因 |
|---|---|---|
| `docs/migration/qa/p1-run-os-core/**/*.png` | 不迁移 | 截图体积大，主要服务旧分支 QA 复盘 |
| `docs/migration/review-cockpit-smoke/**/*.png` | 不迁移 | 旧 UI smoke 截图不应进入当前路线图 |
| `docs/migration/**/browser_smoke_report.json` | 不迁移 | JSON 证据可从历史分支追溯，当前主线只需要场景矩阵 |
| `scripts/**` | 不迁移 | 会覆盖当前 v0.9.13 之后的 runtime、setup、generation、review 结构 |
| `tests/**` | 不迁移 | 旧测试依赖旧 Review Cockpit 结构，直接搬运会制造维护负担 |
| `skills/**` | 不迁移 | 会覆盖当前 suite skill 拆分 |
| `product_capabilities/**` | 不迁移 | 当前主线已有正式 product capability suite |

## 删除远程历史分支的条件

远程分支删除前必须同时满足：

1. 本归档分支合入 `main`。
2. `docs/archive/endgame-runtime-2026-06/` 三份证据文档可从 `main` 追溯。
3. `docs/qa/review-cockpit-smoke-scenarios.md` 已列清旧 smoke 场景去向。
4. `main` 工作区干净。
5. GitHub 上没有需要保留的 `codex/deck-master-endgame-runtime` PR。
6. 老板明确确认可以删除远程分支。

## 后续动作

本 PR 合入后，建议最后执行一次只读确认：

```bash
git branch -r --contains 0ff9b55
gh pr list --repo MainQuestAI/Deck-Master --head codex/deck-master-endgame-runtime --state all
```

如果没有需要保留的 PR，且老板确认删除，再执行远程分支删除。
