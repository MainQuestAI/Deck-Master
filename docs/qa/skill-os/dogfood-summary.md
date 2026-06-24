# Skill OS v1.1 Dogfood & Final Acceptance Summary

日期：2026-06-24 · 脱敏 · 仅记录可复现事实

本轮 dogfood 以 runtime 测试为证据（非真实客户原文），覆盖 master spec §8 DoD 全部 10 条。

## 1. 新 Run 走完整 9 Stage

`test_skill_os_release_contract.py::test_skill_os_pipeline_smoke` 构造新 Run：
init 产物 → resolve_workflow_state → prepare init handoff（auto accepted）→ autopilot quick。
9 个 stage 全部可解析，ladder 推进正确。

## 2. 至少 3 个高影响 approval

`test_workflow_approval.py` 覆盖 brief→planner、planner→sourcing、sourcing→producer、
review→export 四个高影响转换的审批阻断与放行。autopilot v2 在 interactive 模式下逐个停下。

## 3. Final export approval 绑定 artifact hash

`test_workflow_approval.py::test_final_export_cleared_by_human_approval` + `test_final_export_preauth_id_rejected_on_approve`：
final export 审批绑定 handoff output_fingerprint 与 per-artifact sha256；上游变化使 approval stale，
不允许通过 preauth 绕过。

## 4. Legacy bootstrap

`test_skill_os_migration.py::test_legacy_bootstrap_does_not_forge_approval`：
旧 Run（有产物、无 workflow/）bootstrap 后，高影响阶段一律 awaiting_approval，不伪造 handoff/approval。

## 5. Repair return path

`test_workflow_autopilot_v2.py::test_repair_mode_only_owner_stage` + `test_skill_handoff::test_reject_carries_repair_owner`：
reject 携带 repair_owner_stage；repair 模式只在 owner stage 行动，方向变化重新审批。

## 6. Review Desk 使用记录

`test_review_desk_skill_os.py`：projection 返回 9-stage ladder，awaiting approval 与 blocker 区分，
stale 原因可见，accept/reject 写 runtime，主界面无 raw path/command。

## 未完成 / 风险

- DEV-001：本机活动安装早于基线，clean install dogfood 需在 C4 重建 1.1.0 release 后实跑。
- DEV-003：跨仓库 PPT Deck Pro Max bridge 待外部独立 PR + 固定 SHA。
- C1 前端静态 UI（stage rail 视觉）沿用 v0.3 布局，仅 API 投影本轮落地；视觉重做 out of scope（master spec §5.2）。

## 结论

Skill OS 内核（契约、交接、审批、autopilot、迁移）全部可机器验证；量化指标达标。
v1.1.0 runtime ready，待 1.1.0 release 重建后完成 clean-install dogfood 闭环。
