# Deck Master v1.1 Skill OS Runtime Master Spec

## 0. 文档控制

| 字段 | 内容 |
|---|---|
| 基线 | `origin/main @ 4605213f1ee3ba937e4658855582c7517b5af027` |
| 上一关键合并 | PR #8，merge `98101c212bae9c4461ce2c5448808a3dbec27138` |
| 目标版本 | Skill Suite / Runtime `1.1.0` |
| 迭代形态 | 一个业务轮次，三个顺序 Stack |
| 主仓库 | `MainQuestAI/Deck-Master` |
| 关联能力 | PPT Library、PPT Deck Pro Max、PPT Master、PPT Quality Gate |
| 默认环境 | local-first、Agent-facing、Codex 优先，兼容 Claude Code |
| Provider 原则 | Deck Master 继续保持零内置 LLM Provider |
| 评审基线 | 以本包和后续经批准的 deviation log 为准 |

## 1. 一页结论

Deck Master 已经拥有完整的 Skill 名称体系、CLI、Run State、Review Desk、Production Backend Gate 和 Release Tree，但当前 Skill 仍主要是命令说明，Runtime 仍主要根据 Artifact 是否存在推导阶段，Autopilot 仍会直接调用命令跨越多个业务阶段。

本轮不再增加新的 Skill 名称。核心工作是把现有 `deck-*` 体系升级为 Skill OS：

```text
用户意图
  → Skill 路由
  → Stage Contract 进入验证
  → Forcing Questions / 决策记录
  → CLI 执行
  → Exit Artifact 验证
  → Handoff
  → 用户审批或自动接受
  → 下游 Stage 进入
```

完成后，Agent 不能再以“命令返回 0”或“某个 JSON 存在”作为阶段完成依据。

## 2. 本轮业务目标

### 2.1 唯一目标

> 把 Deck Master 从 PPT 能力入口集合升级为专业 Solution Deck 本地工作流系统，使阶段、产物、确认、阻断、自动推进和返修路径全部可追踪、可验证、可恢复。

### 2.2 用户侧结果

用户处理一个 Run 时，应始终能看懂：

1. 当前处于哪个 Skill 阶段。
2. 当前阶段要解决什么业务问题。
3. 已经完成了哪些阶段。
4. 当前阶段还缺哪些材料、决策或产物。
5. 下一步推荐哪个 Skill。
6. 下一步是自动执行，还是需要用户确认。
7. 用户确认绑定的是哪一版 Brief、Narrative、Sourcing Plan 或最终 Artifact。
8. 上游内容变化后，哪些下游结果已变成 stale。

### 2.3 系统侧结果

- 9 个生产阶段均有版本化 Stage Contract。
- 进入和退出条件由同一 Runtime 验证。
- Handoff 为 append-only、可审计、带 Artifact Fingerprint。
- Approval 为 append-only，且绑定 Transition 和 Artifact Fingerprint。
- `route-skill`、`next-step`、`run-state`、`workflow status`、Review Desk 使用同一阶段解析结果。
- Autopilot 不能绕过高影响审批。
- `deck-sourcing`、`deck-producer`、`deck-builder` 的 Artifact 边界固定。
- 旧 Run 和旧 `ppt-*` 入口继续可用。

## 3. 当前基线判断

### 3.1 已有能力

- `skills/manifest.json` 已定义 14 个公开 `deck-*` Skill 与 4 个 `ppt-*` 兼容入口。
- `skill_route.py` 已能把 Runtime stage 与 input type 路由到公开 Skill。
- `run_state_resolver.py` 已输出 `recommended_skill`、`skill_stage` 和 `skill_route`。
- `workflow-autopilot` 已能连续执行若干确定性命令。
- Review Desk 已具备业务状态、页面审查、审批任务、质量和最终放行信息。
- Production Builder Backend Gate、Artifact Truth、Final Readiness 和 self-contained release 已存在。

### 3.2 本轮要解决的结构性缺口

- Skill identity、route metadata、installer metadata 存在多处重复真源。
- Stage 完成仍主要由文件存在性推导。
- 缺少 Stage entry / exit validator。
- 缺少跨 Stage 的 canonical handoff。
- 现有 Approval Task 主要服务 Review Desk，未成为 Workflow transition contract。
- Autopilot 没有统一审批策略和预授权模型。
- `deck-sourcing` 尚未输出稳定的 `sourcing_plan.v2`。
- `deck-producer` 尚未输出清晰隔离客户内容和内部说明的 `page_package.v1`。
- `deck-builder` 仍以 `preview_manifest` 为主要页面输入，未强制消费 Page Package。
- Review Desk 尚未提供完整的 Stage Ladder、Handoff 和 Transition Approval 视图。

## 4. 硬架构决策

### D1：保留现有 Skill 名称，不新增独立“访谈 Skill”

访谈深度通过每个 Stage Contract 的 `forcing_questions` 和 Decision Log 实现。`deck-brief`、`deck-planner`、`deck-sourcing`、`deck-producer` 分别承担本阶段的高价值提问。

### D2：生产阶段只有 9 个

```text
deck-init
→ deck-brief
→ deck-planner
→ deck-sourcing
→ deck-producer
→ deck-builder
→ deck-quality
→ deck-review
→ deck-learn（可选，交付后）
```

`deck-master` 和 `deck-autopilot` 是 Orchestrator，不是生产阶段。`deck-setup`、`deck-upgrade`、`deck-doctor` 是 Operations Lane，不进入主链路排序。

### D3：Stage Contract 是行为真源

每个 Stage 必须定义：

- 业务问题；
- Allowed previous stages；
- Entry required artifacts；
- First checks；
- Forcing questions；
- Exit artifacts；
- Exit criteria；
- Approval policy；
- Automatic / manual transition；
- Stop conditions；
- Staleness dependencies；
- Next Skill；
- User-visible copy。

### D4：`skills/manifest.json` 是 Skill identity 真源

Runtime、Installer、Route Resolver 和 Release Builder 不得继续维护独立 Skill 列表。它们必须读取同一 Manifest。

Stage 行为真源为：

```text
skills/stage-contracts.json
```

Manifest 通过 `stage_id` 引用 Stage Contract。

### D5：Artifact 和 Approval 是事实，Workflow State 是派生快照

- 原始 Artifact、Handoff、Approval、Decision Log 是事实源。
- `workflow/workflow_state.json` 是可重建派生快照。
- 不允许人工直接修改 `workflow_state.json` 来改变阶段。

### D6：Handoff 使用 append-only 记录

核心对象是 `deck_skill_handoff.v1`，存储在：

```text
workflow/handoffs/<handoff_id>.json
```

`workflow/current_handoff.json` 仅为最新 Handoff 投影，不是唯一事实源。

### D7：审批绑定 Transition 和 Fingerprint

Approval 必须绑定：

- from / to stage；
- handoff id；
- output artifact hashes；
- stage output fingerprint；
- actor；
- decision；
- timestamp；
- scope / expiry。

上游 Fingerprint 变化后，旧 Approval 自动 stale。

### D8：高影响 Transition 必须确认

Production / Benchmark 默认需要确认：

- `deck-brief → deck-planner`
- `deck-planner → deck-sourcing`
- `deck-sourcing → deck-producer`
- `deck-review → client export`

其中 `review → client export` 永远不可预授权。

### D9：机械门禁自动运行

满足前置条件后，以下 Transition 默认自动：

- `deck-init → deck-brief`
- `deck-producer → deck-builder`
- `deck-builder → deck-quality`
- `deck-quality → deck-review`
- `delivery recorded → deck-learn`

自动不等于无记录：每次必须生成 Handoff 和 Evidence。

### D10：允许显式预授权，但不能依赖模糊对话

Production 可通过 `workflow/preauthorization.json` 预授权部分高影响 Transition。预授权必须有 actor、scope、expiry、allowed transitions、material roots、cost ceiling 和 Fingerprint boundary。

自然语言中的“继续做”不能被长期解释为无限预授权。

### D11：Sourcing、Producer、Builder 边界固定

- Sourcing 只决定材料与证据来源。
- Producer 只形成页面内容包。
- Builder 只消费批准后的页面内容包并构建文件。

Builder 不得新增业务主张，也不得读取内部制作说明进入客户文件。

### D12：Page Package 是 Producer 与 Builder 的正式边界

Production Builder 默认只接受 `deck_page_package.v1`。旧 `preview_manifest` 通过显式 Legacy Adapter 转换，不再作为正式生产输入。

### D13：Quality 与 Review 分离

- Quality：自动和 Agent 辅助的文件级、内容安全和证据门禁。
- Review：人类判断、返修路由、最终 Artifact Approval、Export 决策。

Quality pass 不等于可交付。

### D14：Review Desk 只展示派生业务状态

主界面不得把 raw CLI、绝对路径或内部字段作为主文案。技术详情进入诊断抽屉。

### D15：兼容优先，不删除 `ppt-*`

`ppt-library`、`ppt-deck-pro-max`、`ppt-master`、`ppt-quality-gate` 在 v1.x 继续保留。它们必须映射到公开 Stage，并遵守同一 Handoff / Artifact Contract。

## 5. 范围

### 5.1 In Scope

- Stage Contract Registry。
- Workflow State Resolver。
- Entry / Exit Stage Validation。
- Handoff Runtime。
- Approval / Rejection / Preauthorization Runtime。
- Workflow CLI 子命令组。
- Route / Next Step / Run State 统一。
- Forcing Questions 与 Decision Log。
- `sourcing_plan.v2`。
- `page_package.v1`。
- `build_manifest.v2` 输入边界。
- Autopilot v2。
- Review Desk Skill OS 视图。
- Legacy Run Bootstrap。
- `ppt-*` 与外部完整 Skill Package 兼容。
- Installer / Release / RC Gate / Docs / Tests。

### 5.2 Out of Scope

- 新增新的用户主 Skill 名称。
- 重写 Narrative Engine 算法。
- 重做 PPT Library 检索引擎。
- 重写 PPT Master 视觉渲染内核。
- 云端多租户、用户登录、真实 RBAC。
- 自动替代最终人审。
- 把 LLM Provider 内置到 Deck Master。
- 本轮重做 Review Desk 整体视觉设计。

## 6. 成功标准

| 指标 | 最低验收值 |
|---|---:|
| 生产阶段 Contract 覆盖 | 9/9 |
| Stage entry/exit 统一验证 | 100% |
| 必需 Transition Handoff 覆盖 | 100% |
| 高影响 Transition 无审批绕过 | 0 |
| Final client export 无显式 Approval | 0 |
| route / next-step / run-state / workflow-status 一致率 | 100% |
| Stale Handoff / Approval 自动识别 | 100% |
| Sourcing Plan v2 页面覆盖率 | 100% |
| Producer Page Package 覆盖率 | 100% required pages |
| Builder 读取 internal_only 字段 | 0 |
| Production 直接消费旧 preview_manifest | 0，除显式 migration adapter |
| `ppt-*` 兼容回归 | 100% |
| Skill 文档 Contract 合规 | 100% public skills |
| Clean install Codex / Claude Code | 均通过 |
| 新 Run E2E | 通过 |
| Legacy Run bootstrap E2E | 通过 |
| Repair workflow E2E | 通过 |

## 7. 交付 Stack

### Stack A — Stage Contract & Handoff Runtime

建立 Skill OS 内核，不修改 Producer / Builder 业务输出形态。

### Stack B — Production Boundary & Autopilot v2

落地 Sourcing Plan v2、Page Package、Builder Input Contract、Forcing Questions 和审批感知 Autopilot。

### Stack C — Review Desk, Compatibility & Release Closure

完成 UI、旧 Run、`ppt-*`、外部 Skill Package、安装发布、RC 和真实 Dogfood。

## 8. Definition of Done

本轮只有在以下条件同时满足时才可宣布 Skill OS 完成：

1. 所有 Stage 由 Contract Registry 驱动。
2. 所有跨 Stage 推进都有 Handoff。
3. 所有要求审批的 Transition 都有有效 Approval。
4. Autopilot 无法绕过审批或最终导出确认。
5. Builder 生产输入切换到 Page Package。
6. Review Desk 可展示、批准、驳回和恢复 Workflow。
7. Legacy Run 不丢状态，可安全 bootstrap。
8. `ppt-*` 和外部完整 Skill Package 不被覆盖或绕开。
9. CI、RC、clean install、E2E 全部通过。
10. 未完成项、deviation 和风险全部写入正式记录，不允许用文档措辞掩盖。
