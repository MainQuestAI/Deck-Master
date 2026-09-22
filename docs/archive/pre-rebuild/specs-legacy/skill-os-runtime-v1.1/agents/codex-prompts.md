# Codex Execution Prompts

## Stack A

```text
你正在开发 MainQuestAI/Deck-Master 的 Skill OS Runtime。
基线以 docs/specs/skill-os/ 中正式 Spec 为准。
按 A0 → A5 顺序执行，不得绕过依赖。
本 Stack 只建立 Stage Contract、Workflow State、Handoff、Approval 和统一 CLI；不要提前改变 Sourcing / Producer / Builder Artifact。
每个 Task 独立 commit，并记录真实测试结果。
```

## Stack B

```text
实现 Skill OS 的生产边界和 Autopilot v2。
先确认 Stack A 全部通过。
严格保持：Sourcing 管来源，Producer 管 Page Package，Builder 管文件构建。
Builder 只能消费白名单字段；Autopilot 不得创造 Approval，不得自动 client export。
跨 PPT-Deck-Pro-Max / PPT Master 的修改使用独立 PR 和固定 SHA。
```

## Stack C

```text
完成 Review Desk Skill OS 视图、兼容迁移、安装发布和最终验收。
不要重做 Review Desk v0.3 主布局。
所有 UI 状态从 Workflow API 读取。
必须覆盖 Legacy Run、ppt-* wrapper、external full package、Codex/Claude clean install 和三条 E2E。
```
