# Skill OS v1.1 Acceptance Matrix

日期：2026-06-24 · 目标：`1.1.0` · 基线：`4605213`

Master Spec §6 量化成功标准 → 证据映射。

| 指标 | 最低验收值 | 证据 |
|---|---:|---|
| 生产阶段 Contract 覆盖 | 9/9 | `tests/test_stage_contract_registry.py::test_nine_contracts_loaded` |
| Stage entry/exit 统一验证 | 100% | `tests/test_stage_validation.py`、`tests/test_workflow_state.py` |
| 必需 Transition Handoff 覆盖 | 100% | `tests/test_skill_handoff.py`（prepare/accept/consume/stale/supersede） |
| 高影响 Transition 无审批绕过 | 0 | `tests/test_workflow_approval.py::test_high_impact_transition_blocked_without_approval` |
| Final client export 无显式 Approval | 0 | `tests/test_workflow_approval.py::test_final_export_*`、`test_workflow_autopilot_v2::test_final_export_always_stops` |
| route / next-step / run-state / workflow-status 一致率 | 100% | `tests/test_workflow_cli.py::test_four_state_entries_share_current_skill_stage` |
| Stale Handoff / Approval 自动识别 | 100% | `tests/test_workflow_approval.py::test_approval_stale_on_fingerprint_change`、`test_skill_handoff::test_supersede_on_upstream_change_retains_old` |
| Sourcing Plan v2 页面覆盖率 | 100% | `tests/test_sourcing_plan_v2.py::test_one_decision_per_page_task` |
| Producer Page Package 覆盖率 | 100% required pages | `tests/test_page_package.py::test_assert_required_coverage_*` |
| Builder 读取 internal_only 字段 | 0 | `tests/test_page_package.py::test_internal_leak_detected`、`tests/test_build_manifest_v2.py::test_whitelist_projection_drops_internal_only` |
| Production 直接消费旧 preview_manifest | 0（除显式 adapter） | `tests/test_build_manifest_v2.py::test_production_direct_preview_input_blocked` |
| `ppt-*` 兼容回归 | 100% | `tests/test_skill_doc_contract.py::test_real_compat_docs_reference_public_stage`、manifest compat_aliases |
| Skill 文档 Contract 合规 | 100% public skills | `tests/test_skill_doc_contract.py::test_real_public_skill_docs_conform` |
| Clean install Codex / Claude Code | 均通过 | 安装器沿用 v1.0；C5 dogfood 待 1.1.0 release 重建后实跑（DEV-001） |
| 新 Run E2E | 通过 | `tests/test_skill_os_release_contract.py::test_skill_os_pipeline_smoke` |
| Legacy Run bootstrap E2E | 通过 | `tests/test_skill_os_migration.py::test_legacy_bootstrap_does_not_forge_approval` |
| Repair workflow E2E | 通过 | `tests/test_workflow_autopilot_v2.py::test_repair_mode_only_owner_stage`、`test_skill_handoff::test_reject_carries_repair_owner` |

Definition of Done（master spec §8）：

1. 所有 Stage 由 Contract Registry 驱动 ✅
2. 所有跨 Stage 推进都有 Handoff ✅
3. 所有要求审批的 Transition 都有有效 Approval ✅
4. Autopilot 无法绕过审批或最终导出确认 ✅
5. Builder 生产输入切换到 Page Package ✅
6. Review Desk 可展示/批准/驳回/恢复 Workflow ✅（前端 stage rail + HTTP accept/reject + API 投影）
7. Legacy Run 不丢状态，可安全 bootstrap ✅
8. `ppt-*` 和外部完整 Skill Package 不被覆盖或绕开 ✅（compat 文档 + manifest）
9. CI、RC、clean install、E2E 全部通过 — CI 已增强；clean install 待 1.1.0 release 重建（DEV-001）
10. 未完成项、deviation、风险全部写入正式记录 ✅（spec-deviation-log.md）

## 全量测试

`python -m pytest -q` → **1014 passed**（含 38 subtests），0 failed。
