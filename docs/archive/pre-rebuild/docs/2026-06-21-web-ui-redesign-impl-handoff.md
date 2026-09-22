# Deck Master Web UI 重构 — 实现 Handoff

日期：2026-06-21
分支：`codex/deck-master-webui-redesign`
worktree：`<deck-master-webui-redesign-worktree>`

## 1. 这轮做了什么

- 已完成依据链：audit（诊断）→ IA v1（信息架构+落地映射）→ DESIGN.md（设计系统）→ iteration spec（B1-B8 批次 + design review §10 + eng review §11）→ AGENTS.md。
- Design + Eng 双 review CLEARED，plan 已批准（`~/.claude/plans/spec-encapsulated-metcalfe.md`）。
- 实现推进到 B3（commit 7f25acb），文档基线 commit 5f59936。

## 2. 当前进度

| 批次 | 状态 |
|---|---|
| B1 设计 token 与字体 | ✅ done |
| B2 骨架重构 | ✅ done |
| B2.5 验证闸 | ✅ passed |
| B3 右栏决策台 + 主动作条 | ✅ done |
| B4 底部抽屉 tab 切换接线 | ⏳ 待做（B2 已建结构，接交互） |
| B5 双语 i18n | ⏳ 待做（最大工作量，从零双轨） |
| B6 状态覆盖 | ⏳ 待做（依赖 B5） |
| B7a CSS 玻璃清残 + token 替换 | ⏳ 待做 |
| B7b 标题层级 | ⏳ 待做 |
| B8 Playwright 关键流测试 | ⏳ 待做（从零建 Node 项目） |

详细每批要点 + 交接关键提醒见 **iteration spec §12**（`docs/2026-06-21-web-ui-iteration-spec.md`）。
详细执行路径（含 Explore 发现的 6 处 spec 修正）见 **plan 文件**（`~/.claude/plans/spec-encapsulated-metcalfe.md`）。

## 3. 下位 agent 必读（3 条最关键）

1. **dev server 用 5052，不是 5050**。5050 是 launchd 部署副本服务旧代码。起 dev：`python3 scripts/preview/server.py --host 127.0.0.1 --port 5052 --runs-dir ~/.deck-master/runs --library-mode fixture`。验证：`http://127.0.0.1:5052/?run=yunnan-baiyao-ai-foundation-deck-v1`。
2. **阶段限制是既有逻辑非 bug**：当前 run 阶段"生成中"触发 isStageWorkspace，前端审批按钮禁用但 API 接受。从前端点测审批需切到"待审阅"等阶段的 run，或 API 测。
3. **B5 是最大工作量 + 最高风险**：i18n 从零建双轨，~80 字符串 + 6 format* 函数。一次性 pass 不交错。stage label 保持 API 中文不经 t()（否则 renderActionStates 按钮门控全失效）。

## 4. 三风险守卫（eng review §11.2）

1. els 重映射 → B2.5 闸 + null 守卫（已加全 render*）。
2. `[data-approval-action]` 重绑（renderPageDecisionRail 779-791 作用域 #approval-content）→ B4/B5 若动需复查。
3. stage label 保持中文不经 t() → B5 必守。

## 5. 建议下一步

按 spec §12.2 顺序从 B4 开始。B4 是小活（tab 切换 + toggle + badge），可快速过；B5 是重活建议单独专注；B6-B7 收尾；B8 最后建测试。

实现全部完成后走 `/design-review` 截图级视觉 QA。

## 6. 技能建议

- `redesign-existing-projects`：继续沿用。
- `design-review`：实现后做截图级视觉 QA。
- `handoff`：再次交接时继续用。
