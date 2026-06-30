# AGENTS.md

Deck Master Web UI 重构线程的 AI agent 指引。本文件给 Codex / Claude Code / OpenCode 等所有在本 worktree 工作的 agent 读。

## Design System

实现任何视觉或 UI 改动前，先读 `DESIGN.md`。

- 所有字体、颜色、间距、审美方向在 `DESIGN.md` 定义，为设计源真相。
- 未经老板明确批准，不得偏离 `DESIGN.md`。已锁定的方向（记忆点=严肃工具感、Satoshi/Geist/IBM Plex Mono、冷墨底+琥珀铜单点、去玻璃改发丝实面）不要擅自推翻。
- 当前重构线程依据：`docs/2026-06-21-web-ui-redesign-audit.md`（问题诊断）+ `docs/2026-06-21-web-ui-ia-v1.md`（信息架构与落地映射）。改 `scripts/preview/static/` 前先读这两份。
- 信息架构已锁定：首屏围绕当前页，run 级信息降为顶部状态带 + 底部抽屉；右栏动作收敛为主动作+次动作。落地映射见 IA v1 §7。
- QA / review 时，凡不符合 `DESIGN.md` 的代码（错误字体、玻璃面板、多余强调色、大圆角、弹跳动效）一律标记为偏离。
