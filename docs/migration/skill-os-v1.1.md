# Skill OS v1.1 Migration Guide

日期：2026-06-24 · 目标版本：1.1.0

## 1. 旧 Run 升级（C3）

旧 Run（有产物、无 `workflow/` 目录）升级到 Skill OS v1.1：

```
deck-master workflow status --run-dir <run>   # 自动推断
```

`LegacyBootstrap`（`scripts/workflow/migration.py`）扫描现有产物，推断阶段状态并写入
`workflow/workflow_state.json` 与 `workflow/legacy_bootstrap.json` 标记。

**非伪造不变量**：高影响阶段（brief/planner/sourcing/review）即使产物齐全，也只标记为
`awaiting_approval`，绝不自动写入 handoff 或 approval。必须由真实人工审批才能推进。

## 2. 回滚

```
LegacyBootstrap(run).rollback(run)
```

只删除 `workflow/` 下 Skill OS 派生的账册（legacy_bootstrap.json、workflow_state.json、
handoffs/、approvals/），原 Run 产物不动。

## 3. 旧 `ppt-*` alias

`ppt-library / ppt-deck-pro-max / ppt-master / ppt-quality-gate` 保留（D15），各 SKILL.md
已声明其映射的公开 stage。旧调用继续可用，产物走同一 Artifact Contract。

## 4. 旧 preview_manifest

生产构建不再直接消费 `preview_manifest`（D12）。需经显式 `legacy_preview_adapter`
（`scripts/build/manifest.py`）转为 page package，结果标记 `legacy_inferred: true` +
`status: draft`，必须复审。

## 5. 外部完整能力包

外部真实目录 / 符号链接一律保留；安装器以 manifest + smoke + contract 判断是否
production capable，不覆盖（C4）。
