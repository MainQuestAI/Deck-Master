# Stack C — Review Desk, Compatibility & Release Closure

## 目标

把 Skill OS 状态呈现给用户，完成旧 Run、旧 Skill、外部完整 Package、安装发布和真实工作流验证。

## 包含任务

- C1 Review Desk Skill OS View
- C2 Skill Docs & Manifest Conformance
- C3 Legacy / `ppt-*` / External Package Compatibility
- C4 Installer / CI / RC / Release
- C5 Dogfood & Final Acceptance

## Stack Exit Criteria

- Review Desk 可显示 9 阶段、Handoff、Approval、Stale 和 Next Skill。
- 所有 public SKILL.md 通过结构 Contract。
- 旧 Run 可 bootstrap。
- 旧 `ppt-*` 入口可回写 canonical Workflow。
- Codex / Claude Code clean install 通过。
- 新 Run、Legacy Run、Repair 三条 E2E 通过。
- Final client export 无显式 Artifact-bound Approval 时硬阻断。
