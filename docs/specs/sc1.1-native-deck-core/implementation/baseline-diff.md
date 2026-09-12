# SC-1.1 Q0｜基线差异（baseline-diff）

- 日期：2026-09-07；分支 `codex/sc1.1-native-core`（stacked on PR #30）
- 实现/评审基线：`4977f89573d18a282c605360dc55f751443a2b21`（PR #30 HEAD，open/unmerged，base `bcb5b37`）
- 本工作树 HEAD：`4181c01` = 基线 + spec pack 落库提交（docs-only，无代码变更）
- PR #30 状态：open，等待用户合并（DELIVERY_PLAN 约束：不得为开工擅自合并/force push）；分支策略 = stacked development，以 4977f89 为增量评审基线
- 工作区：`.claude/worktrees/sc1-solution-core`；主仓库保持 `main`（bcb5b37）未触碰
- venv：`.venv`（Python 3.12，`pip install -e ".[dev]"`）
- 测试基线复跑：见 acceptance-tracking（PR30 报告的 1583 passed 需独立复跑佐证，结果记录于本目录）
- 用户未提交修改：无（开工时两仓库均 clean）
