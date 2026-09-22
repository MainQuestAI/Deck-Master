# Skill OS Runtime v1.1 — 开发计划

分支：`feat/skill-os-runtime-v1.1`
工作区：`<deck-master-skill-os-worktree>`
基线：`4605213` · 目标：`1.1.0` · 基线测试：836 passed

## 执行原则

- 严格按 Stack A → B → C 顺序；栈内按依赖序。
- 每个任务遵守 task spec 的「允许修改路径」；越界先写 deviation log。
- 每个任务完成后：跑相关测试 + 全量回归 + commit + 更新 deviation log 进度表。
- 红线（非绕行）全程守。

## Stack A — Stage Contract & Handoff Runtime

| 任务 | 允许路径（核心） | 交付物 | 验证 |
|---|---|---|---|
| A0 ✅ | docs/specs/skill-os/implementation, docs/specs/README.md | baseline-freeze.md, deviation log | 836 passed |
| A1 | skills/manifest.json, skills/stage-contracts.json, scripts/skills/manifest.py, docs/contracts/, tests/test_skill_manifest.py, tests/test_stage_contract_registry.py | manifest 1.1.0 + stage_id；9 contracts；loader+校验（dup name/alias/stage order/input collision）；contract hash | loader/contract 负向测试 |
| A2 | scripts/workflow/, scripts/runtime/run_state_resolver.py, docs/contracts/workflow-state.v1.schema.json, tests/test_workflow_state.py, tests/test_stage_validation.py | workflow state resolver；entry/exit validator；fingerprint/stale 传播；snapshot 重建 | empty/new/partial/completed/stale |
| A3 | scripts/workflow/handoff.py, docs/contracts/skill-handoff.v1.schema.json, tests/test_skill_handoff.py | append-only handoff prepare/consume/stale/supersede；idempotency；file lock；current 投影 | prepare/dup/consume/stale/supersede/concurrent |
| A4 | scripts/workflow/approval.py, scripts/workflow/policy.py, docs/contracts/stage-approval.v1.schema.json, docs/contracts/workflow-policy.v1.schema.json, tests/test_workflow_approval.py | approval accept/reject/revoke；preauth；stale；non-bypassable；final export 不可预授权 | 全 transition policy/expired/revoked/fingerprint/dup |
| A5 | scripts/deck_master.py, scripts/runtime/skill_route.py, scripts/runtime/next_step.py, tests/test_workflow_cli.py, tests/test_skill_route.py | `workflow` CLI 组；route/next-step/run-state 共用 resolver；alias 兼容；manifest 驱动 route | CLI 正负向 + route 一致性矩阵 |

**Stack A Exit**：9 contract 可加载；fixture run 出 workflow state；handoff prepare/accept/reject；approval 阻断；四入口同一 stage；上游变化使 handoff/approval stale。

## Stack B — Production Boundary & Autopilot v2

| 任务 | 交付物 |
|---|---|
| B1 | forcing questions + decision log（每个 stage 的 forcing_questions 落地、decision_log.jsonl append-only） |
| B2 | sourcing_plan.v2（页面全覆盖） |
| B3 | page_package.v1 + producer 契约（客户可见字段隔离 internal_only） |
| B4 | build_manifest.v2 + builder 输入边界（消费 page_package，旧 preview_manifest 走 legacy adapter） |
| B5 | autopilot v2（interactive/preauthorized/quick/repair/review-only 五模式，审批感知） |

## Stack C — Review Desk, Compat & Release

| 任务 | 交付物 |
|---|---|
| C1 | Review Desk Skill OS 视图（stage ladder / handoff / transition approval） |
| C2 | skill doc + manifest 合规（100% public skills） |
| C3 | legacy run bootstrap + ppt-* 兼容迁移 |
| C4 | installer / CI / RC / release（1.1.0 release 构建） |
| C5 | dogfood + final acceptance（clean install Codex/Claude Code、E2E、legacy、repair） |

## schema 文件名约定

`docs/contracts/` 沿用 house style（`<thing>.v<n>.schema.json`，如 `stage-contract.v1.schema.json`）；schema 内部 `schema_version` const 保留 `deck_*` 命名（如 `deck_stage_contract.v1`），与 spec pack 一致。

## 进度

见 `spec-deviation-log.md` 任务进度表。每完成一个任务即更新并 commit。
