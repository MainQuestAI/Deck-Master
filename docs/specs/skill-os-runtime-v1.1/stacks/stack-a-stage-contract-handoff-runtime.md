# Stack A — Stage Contract & Handoff Runtime

## 目标

建立 Skill OS 内核，使所有 Stage 的进入、退出、交接、审批和过期判断具备统一运行时。

## 包含任务

- A0 Baseline & Version Freeze
- A1 Canonical Skill Manifest & Stage Contract Registry
- A2 Workflow State Resolver
- A3 Handoff Runtime
- A4 Approval & Preauthorization Runtime
- A5 Workflow CLI / Route / Next Step Integration

## 不包含

- 不改变 Sourcing Plan 主 schema。
- 不要求 Producer 输出 Page Package。
- 不改 Review Desk 主布局。

## Stack Exit Criteria

- 9 个 Stage Contract 可加载、可验证。
- 一个已有 Fixture Run 可生成 Workflow State。
- 可 prepare / accept / reject Handoff。
- 必需 Approval 能阻断 Stage。
- `run-state`、`next-step`、`route-skill`、`workflow status` 返回同一 Stage。
- Upstream Artifact 修改会使 Handoff / Approval stale。
