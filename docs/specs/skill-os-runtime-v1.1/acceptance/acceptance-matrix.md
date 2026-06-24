# Acceptance Matrix

| ID | Requirement | Blocking | Evidence |
|---|---|---:|---|
| SO-001 | 9 个生产 Stage Contract 全部可验证 | P0 | registry test + schema report |
| SO-002 | Manifest 为 Skill identity 唯一真源 | P0 | no-duplicate-source test |
| SO-003 | Workflow State 可由事实重建 | P0 | rebuild determinism test |
| SO-004 | 所有 Stage Transition 生成 Handoff | P0 | E2E handoff trace |
| SO-005 | Brief/Planner/Sourcing 高影响审批不能绕过 | P0 | policy negative tests |
| SO-006 | Final client export 永远显式审批 | P0 | export negative test |
| SO-007 | Approval 绑定 Artifact hash，变更后 stale | P0 | mutation test |
| SO-008 | route/next-step/run-state/workflow-status 一致 | P0 | consistency matrix |
| SO-009 | Sourcing Plan v2 覆盖全部 Page Tasks | P0 | coverage validator |
| SO-010 | Required Page Package 覆盖全部生产页 | P0 | package index validator |
| SO-011 | Builder 不读取 internal_only | P0 | leakage test |
| SO-012 | Production 不直接消费 Preview Manifest | P0 | builder negative test |
| SO-013 | Autopilot 遵守 approval policy | P0 | all-mode tests |
| SO-014 | Review Desk 展示 Stage / Handoff / Approval | P1 | browser screenshots + API tests |
| SO-015 | Legacy Run bootstrap 不伪造 Approval | P0 | legacy migration test |
| SO-016 | `ppt-*` 兼容入口继续可用 | P1 | compatibility smoke |
| SO-017 | external full package 不被覆盖 | P0 | install/migration test |
| SO-018 | public SKILL.md 结构合规 | P1 | doc contract test |
| SO-019 | Codex / Claude Code clean install | P0 | temp HOME evidence |
| SO-020 | New / Legacy / Repair 三条 E2E | P0 | RC evidence pack |
