# 新A线接手入口

> **历史入口（2026-09-30 起由 [CONSOLIDATION.md](CONSOLIDATION.md) 取代）**：双线已合并为单一冲刺支线 `codex/webui-v4-completion`。

工作树：`/Users/dingcheng/.codex/worktrees/webui-a/Deck-Master`。分支：`codex/webui-a-implementation`。共同基线tag：`baseline/webui-v4-20260930`；运行 `git rev-parse HEAD`、`git status --short` 和 `git rev-parse baseline/webui-v4-20260930` 核对，实施前再核对远端main。

依次读取根AGENTS/任务路由/恢复手册、本目录README、[A-UI-SPEC.md](A-UI-SPEC.md)、[接口合同](INTERFACES.md)、[差距矩阵](GAP-MATRIX.md)和[A01](task-cards/A01.md)。按该卡开始，不从旧W01重新做12包，也不把本目录设计样本当运行实现。

已交付收讫设计17文件、53项功能核对、15开发卡/45新AC及87旧AC接续。当前产品代码仍为66da345，本次未实施新功能。定向148项测试与5项探针已运行；浏览器全流程/真实项目/最终安装均不是本轮已通过项。

A负责静态v2模块与浏览器视觉/交互；B负责核心/Task/schema/HTTP/CLI/Skill/打包。共享接口先main后消费，每卡独立复核。PR66未合入，A01先评审其有限修复；不能直接整体cherry-pick旧W12报告。B07承接旧安装与压力证据，其中压力仍失败。

按 [EXECUTION](EXECUTION.md) 管理工程切片与验收。写代码前可复用旧报告做背景，但只有准确SHA、真实层级证据才可关闭AC。发布和真实HOME迁移仍单列，不自动执行。
