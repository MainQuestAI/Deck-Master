# Deck Master v1.1 Skill OS Runtime Spec Pack

日期：2026-06-24  
基线：`origin/main @ 4605213f1ee3ba937e4658855582c7517b5af027`  
目标版本：`Deck Master Skill Suite 1.1.0`  
目标阶段：从“Skill 命名体系 + 命令集合”升级为“具备阶段契约、交接、审批、自动推进和可视化状态的 Skill OS”。

## 本地接入补充

本目录已被吸收到 Deck Master 仓库，作为 v1.1 Skill OS Runtime 候选实施基线。

本地补充文件：

- `LOCAL_ADOPTION.md`：记录吸收路径、本地验收结果、开工顺序和非绕行规则。
- `acceptance/decision-traceability.md`：补充 D1-D15 硬决策到任务、验收和负向测试的追踪。
- `acceptance/decision-requirements-traceability.csv`：机器可读的硬决策追踪表。

## 本包用途

本包是本轮正式开发基线，供 Codex、Claude Code 或其他实现 Agent 按顺序执行。它不是讨论稿。

本轮只有一个业务目标：

> 让 Deck Master 对每个生产阶段都能机器可读地回答：当前是谁负责、能否进入、缺什么、是否完成、下一步是谁、是否需要用户确认、确认绑定了哪些产物、上游变化后哪些结果已过期。

## 交付结构

- `00-master-spec.md`：总目标、范围、硬决策、成功标准。
- `01-baseline-gap-register.md`：当前主分支事实与差距。
- `02-skill-os-architecture.md`：总体架构与真源关系。
- `03-stage-contract-model.md`：全阶段进入、退出、交接和审批模型。
- `04-cli-runtime-contract.md`：统一 Workflow CLI 及兼容别名。
- `05-artifact-contracts.md`：Workflow、Sourcing、Page Package、Build 数据边界。
- `06-production-boundaries.md`：Sourcing / Producer / Builder / Quality / Review 硬边界。
- `07-approval-autopilot-policy.md`：审批、预授权和 Autopilot v2。
- `08-review-desk-integration.md`：Review Desk Skill OS 视图。
- `09-compatibility-migration-release.md`：旧 Run、`ppt-*`、外部完整 Skill 包、安装发布。
- `stacks/`：三个顺序 Stack。
- `tasks/`：15 个可独立执行的任务 Spec。
- `schemas/`：9 个 Draft 2020-12 JSON Schema。
- `examples/`：关键 Artifact 示例。
- `acceptance/`：验收矩阵、QA 计划、RC 清单、追踪矩阵。
- `agents/`：Agent 执行、评审和提示词协议。
- `iteration-plan.json`：机器可读任务依赖。
- `combined-spec.md`：全部 Markdown 合并版。

## 执行顺序

```text
Stack A：Stage Contract & Handoff Runtime
    ↓
Stack B：Production Boundary & Autopilot v2
    ↓
Stack C：Review Desk, Compatibility & Release Closure
```

不得并行跨越以下依赖：

- A1 完成前不得实现独立的 route / next-step 新真源。
- A3/A4 完成前不得改造 Autopilot 自动跨阶段。
- B3 完成前不得让 Builder 以 `page_package` 为正式输入。
- B5 完成前不得在 UI 提供“连续执行”按钮。
- C4 完成前不得把 Suite version 宣称为 1.1.0 ready。

## 基线说明

PR #8 已在 `98101c212bae9c4461ce2c5448808a3dbec27138` 合并，建立 v1 Skill Suite；当前 main 又包含 Review Desk v0.3。现有 `route-skill`、`run-state`、`next-step`、`workflow-autopilot` 必须保留兼容，但其事实源需迁移到本轮 Stage Contract Runtime。
