# Deck Master v1.1 Skill OS Runtime — Combined Spec

---

<!-- SOURCE: README.md -->

# Deck Master v1.1 Skill OS Runtime Spec Pack

日期：2026-06-24
基线：`origin/main @ 4605213f1ee3ba937e4658855582c7517b5af027`
目标版本：`Deck Master Skill Suite 1.1.0`
目标阶段：从“Skill 命名体系 + 命令集合”升级为“具备阶段契约、交接、审批、自动推进和可视化状态的 Skill OS”。

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

---

<!-- SOURCE: 00-master-spec.md -->

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

---

<!-- SOURCE: 01-baseline-gap-register.md -->

# Baseline & Gap Register

## 1. 已确认基线

| 项目 | 当前状态 |
|---|---|
| Main | `4605213f1ee3ba937e4658855582c7517b5af027` |
| PR #8 | 已合并，v1 Skill Suite Runtime |
| Review Desk | v0.3 已合入 main |
| Skill manifest | `1.0.0`，14 个公开 `deck-*` + 4 个兼容 `ppt-*` |
| Route Resolver | Runtime stage / input type → public skill |
| Run State | 输出 `recommended_skill` / `skill_stage` / `skill_route` |
| Autopilot | 可直接调用 brief、plan、generation、quality、build、export 命令 |
| Approval | Review Desk 存在 approval task，但不是 Stage Transition Contract |
| Builder | Production Backend Gate 已存在；contract-smoke 输出被标记 non-client-deliverable |
| Release | self-contained tree、stage/verify/activate/rollback 已存在 |

## 2. 问题注册表

| ID | 问题 | 影响 | 本轮处理 |
|---|---|---|---|
| G-01 | Skill 行为只是薄文档 | Agent 容易把命令跑完当成完成 | Stage Contract + Skill Doc Contract |
| G-02 | Manifest、Route、Installer metadata 重复 | 漂移和兼容风险 | 单一 Manifest 真源 |
| G-03 | Stage 完成由文件存在性推断 | 无法表达确认、过期和部分完成 | Workflow State Resolver |
| G-04 | 无跨 Stage Handoff | 下游无法验证上游交付 | Handoff Runtime |
| G-05 | Approval 未绑定 Transition / Fingerprint | 旧确认可能错误复用 | Approval Runtime |
| G-06 | Autopilot 直接跨高影响阶段 | 方向、成本、来源和导出可被绕过 | Autopilot v2 Policy |
| G-07 | 访谈机制散落且不阻断 | 关键业务信息不足 | Forcing Questions + Decision Log |
| G-08 | Sourcing / Producer / Builder 边界模糊 | 内容与构建责任混写 | 三段 Artifact Contract |
| G-09 | Builder 正式输入仍是 Preview | 内部字段和旧结构易泄漏 | Page Package + Build Manifest v2 |
| G-10 | UI 看不到 Stage Handoff | 用户不知道为什么不能继续 | Skill OS Stage View |
| G-11 | 旧 Run 没有 Handoff / Approval | 升级后状态不确定 | Legacy Bootstrap |
| G-12 | 外部完整 Skill Package 识别与采用不统一 | 可能覆盖或绕开高价值能力 | Generic external package contract |

## 3. 不应重复开发的能力

本轮不得重新实现以下已存在能力：

- Setup / Suite 安装基础。
- Production Builder Backend Gate。
- Generation Result v2 的 run/session/hash 绑定。
- Artifact Validator 基础。
- Final Readiness 基础。
- Review Desk 页面级审查。
- Release staging / verification / rollback。

本轮只在必要处接入 Workflow Contract。

## 4. 需要 Codex 开工前核验的本地事实

- 当前 main 的实际全量测试数和结果。
- 本机 `~/.deck-master/current` 是否指向 `4605213f1ee3ba937e4658855582c7517b5af027`。
- Codex / Claude Code skill links 状态。
- 完整 PPT Master / PPT Library / PPT Deck Pro Max 的安装路径和版本。
- 当前本地真实 Run 中是否存在可用于 Legacy Bootstrap 的代表样本。
- Review Desk v0.3 的截图基线是否仍可重放。

这些事实不得在开发报告中凭推测填写。

---

<!-- SOURCE: 02-skill-os-architecture.md -->

# Skill OS Overall Architecture

## 1. 六层模型

```text
Layer 1  User Skill Entry
         deck-init / brief / planner / sourcing / producer / builder / quality / review / learn

Layer 2  Stage Contract Runtime
         registry / validator / handoff / approval / staleness / transition policy

Layer 3  Execution Runtime
         existing CLI commands / capability adapters / external Agents

Layer 4  Artifact Truth
         brief / plans / page packages / build artifacts / quality / readiness

Layer 5  Review Desk
         stage ladder / blockers / handoff / approval / repair / export

Layer 6  Install & Release
         manifest / contracts / symlinks / capability lock / RC gate
```

## 2. 真源关系

### 2.1 Static Truth

| 真源 | 作用 |
|---|---|
| `skills/manifest.json` | Skill identity、public/compat、input types、exit artifacts、stage id |
| `skills/stage-contracts.json` | Stage behavior、entry/exit、approval、next stage、staleness |
| `docs/contracts/*.schema.json` | Runtime Artifact schema 真源 |

### 2.2 Run Truth

| 真源 | 作用 |
|---|---|
| Existing run artifacts | 业务和执行事实 |
| `workflow/handoffs/*.json` | 跨 Stage 交付事实 |
| `workflow/approval_log.jsonl` | 审批事实 |
| `workflow/decision_log.jsonl` | 用户答案、假设和关键决策 |
| `workflow/preauthorization.json` | 可选预授权边界 |

### 2.3 Derived Projection

| 投影 | 作用 |
|---|---|
| `workflow/workflow_state.json` | 当前全阶段快照，可重建 |
| `workflow/current_handoff.json` | 最新 Handoff 投影 |
| `run-state` API | Runtime + Skill Stage 联合状态 |
| Review Desk payload | 用户可见状态 |

## 3. 依赖方向

```text
Manifest + Stage Contracts
            ↓
Artifact Validators + Approval Resolver
            ↓
Workflow State Resolver
            ↓
route-skill / next-step / run-state / workflow status
            ↓
Autopilot + Review Desk
```

禁止反向依赖：

- UI 不得自行推导 Stage。
- SKILL.md 不得定义 Runtime 未实现的完成条件。
- Installer 不得拥有独立于 Manifest 的 required skill list。
- Autopilot 不得绕开 Stage Validator 直接调用下一阶段。

## 4. Stage 与 Runtime Sub-stage

Skill Stage 是业务层，Runtime Stage 是技术层。

例如 `deck-producer` 可包含：

```text
needs_generation_session
awaiting_agent_execution
generation_running
needs_generation_import
needs_preview_refresh
```

Workflow State 必须同时返回：

- `current_skill_stage = deck-producer`
- `runtime_stage = awaiting_agent_execution`

不能继续把两者混成一个字段。

## 5. Staleness 模型

### 5.1 Fingerprint Chain

每个 Stage 输出 Fingerprint 由以下内容组成：

```text
contract_version
+ validated input artifact hashes
+ decision record hashes
+ output artifact hashes
+ approval binding（如有）
```

### 5.2 传播规则

- Brief 变化：Planner 及其全部下游 stale。
- Narrative / Page Tasks 变化：Sourcing 及其下游 stale。
- Sourcing Plan 变化：Producer 及其下游 stale。
- Page Package 变化：Builder、Quality、Review、Export stale。
- Build Artifact 变化：Quality、Review、Final Approval stale。
- Quality Report 变化：Review / Final Readiness stale。

Stale 只改变状态，不自动删除旧产物。旧产物保留用于审计。

## 6. 并发和写入

- Handoff 和 Approval 使用 append-only。
- Snapshot 使用原子替换。
- 同一 Run 的 Transition mutation 必须使用文件锁。
- Handoff prepare / accept 必须支持 idempotency key。
- 重复 accept 同一 Fingerprint 返回 already_accepted，不生成第二次有效审批。

## 7. 外部 Agent 关系

Deck Master 不负责 LLM 推理，但负责：

- 构造 Stage-aware Agent task；
- 注入 Contract、已批准 Handoff 和允许读取的 Artifact；
- 校验 Agent handback；
- 记录 Decision / Handoff / Evidence；
- 阻止未批准的下游进入。

---

<!-- SOURCE: 03-stage-contract-model.md -->

# Stage Contract Model

## 1. Stage Status

统一状态：

```text
not_started
entry_blocked
ready
in_progress
awaiting_questions
awaiting_approval
completed
stale
failed
skipped
```

只有 `completed` 且 Handoff 已被自动接受或人工批准，下一 Stage 才能进入 `ready`。

## 2. Production Stage Contract Matrix

| Stage | 业务问题 | Entry Artifact | Forcing Questions | Exit Artifact | Transition | Approval |
|---|---|---|---|---|---|---|
| `deck-init` | 项目资料、边界和目录是否准备好 | workspace / material roots | 扫描范围、隐私边界、客户可见禁词 | project metadata、material inventory、workspace policy | → brief | 自动；扫描外部目录需 source consent |
| `deck-brief` | 客户问题、目标、受众、主张和证据是什么 | context manifest、material inventory | 决策对象、成功标准、非谈判约束、禁用主张、证据缺口 | deck brief、claim seed、brief decisions | → planner | production/benchmark 必须确认，可受限预授权 |
| `deck-planner` | Deck 怎么讲、多少页、每页承担什么任务 | approved brief handoff | 主叙事、反方疑问、页数、证明顺序、CTA | narrative plan、page tasks | → sourcing | production/benchmark 必须确认，可受限预授权 |
| `deck-sourcing` | 每页使用什么材料、证据和资产 | approved planner handoff | 来源权威、复用许可、时效、截图权限、生成策略 | sourcing_plan.v2 | → producer | production/benchmark 必须确认，可受限预授权 |
| `deck-producer` | 每页具体表达什么，客户可见内容是什么 | approved sourcing handoff | 页面主张、证据是否可公开、视觉主角、内部/客户边界 | page_package.v1、generation result v2 | → builder | 自动，前提是 required packages 全部 valid |
| `deck-builder` | 如何把批准内容构建成文件 | valid page packages、certified backend | 无业务访谈，仅环境/字体/输出模式确认 | build_manifest.v2、artifact manifest、render result | → quality | 自动 |
| `deck-quality` | 文件和客户可见内容是否安全、完整、可解析 | completed build handoff | 仅在规则冲突或人工判断项时提问 | quality bundle、repair findings | → review | 自动；有 P0/P1 时 handoff 为 blocked review |
| `deck-review` | 是否可交付，返修应回到哪个阶段 | quality handoff、final artifacts | 风险接受、最终版本、交付对象、审批人 | final readiness、final artifact approval、export queue | → export / repair | client export 永远人工确认 |
| `deck-learn` | 哪些经验可安全沉淀 | delivery outcome | 脱敏、可复用范围、胜负原因 | learning pack、feedback events | next run | 自动或人工选择，不阻断交付 |

## 3. Operations Lane

### `deck-setup`

- 不进入 Production Stage 序列。
- 可阻断所有 production stages。
- 输出 setup / suite readiness。

### `deck-upgrade`

- 只处理 release stage / verify / activate / rollback。
- Upgrade 后必须重跑 Workflow Contract compatibility check。

### `deck-doctor`

- 只诊断，不隐式修改业务 Artifact。
- 修复动作必须通过明确 repair command。

## 4. Orchestrator

### `deck-master`

- 读取 Workflow State。
- 路由到负责 Skill。
- 不替代 Stage 完成。

### `deck-autopilot`

- 只执行 Contract 允许的 Transition。
- 每步先 validate，再 action，再 exit validate，再 handoff。
- 不自行创造 Approval。

## 5. Entry Validation

统一检查顺序：

1. Setup / Workspace。
2. Allowed previous stage。
3. Required Handoff 是否 accepted。
4. Required artifacts 是否存在、合法、fresh。
5. Approval 是否有效。
6. Backend / external capability 是否 ready。
7. 当前 Stage 是否已有进行中执行，避免重复。

## 6. Exit Validation

统一检查顺序：

1. Required artifacts 全部存在。
2. Artifact schema valid。
3. Artifact semantic validator pass。
4. Fingerprint 可计算。
5. Blocking forcing questions 为 0。
6. Exit criteria pass。
7. Stop conditions 未触发。
8. 可生成 Handoff。

## 7. Handoff Lifecycle

```text
draft
→ awaiting_approval / auto_accept
→ accepted
→ consumed
```

异常状态：

```text
rejected
stale
superseded
cancelled
```

## 8. Repair Routing

Quality / Review finding 必须带 `repair_owner_stage`：

- 内容事实、主张错误 → producer 或 brief。
- 叙事结构错误 → planner。
- 来源不足或权限问题 → sourcing。
- 版式、构建、字体、渲染 → builder。
- 客户可见内部语言 → producer；若由模板产生则 builder。

Repair Handoff 可自动创建，但进入高影响 Stage 前仍执行对应审批策略。

---

<!-- SOURCE: 04-cli-runtime-contract.md -->

# CLI & Runtime Contract

## 1. 统一命令组

正式入口：

```bash
deck-master workflow status
deck-master workflow validate-stage
deck-master workflow questions
deck-master workflow decision record
deck-master workflow handoff prepare
deck-master workflow handoff accept
deck-master workflow handoff reject
deck-master workflow approval list
deck-master workflow preauthorize
deck-master workflow bootstrap
deck-master workflow autopilot
```

## 2. 兼容别名

| 兼容命令 | 正式映射 |
|---|---|
| `workflow-status` | `workflow status` |
| `validate-stage` | `workflow validate-stage` |
| `skill-handoff` | `workflow handoff prepare` |
| `accept-handoff` | `workflow handoff accept` |
| `workflow-autopilot` / `autopilot-v1` | `workflow autopilot` |

现有 `route-skill`、`next-step`、`run-state` 保留，但必须调用同一个 Workflow State Resolver。

## 3. 命令定义

### 3.1 `workflow status`

输出全 Stage 状态、当前 Stage、Runtime Sub-stage、Artifact、Approval、Handoff、Blocker、Next Skill。

必要字段：

```text
schema_version
run_id
current_skill_stage
runtime_stage
stages[]
recommended_next_skill
required_next_skill
approval_required
approval_status
current_handoff
missing_artifacts
stale_artifacts
allowed_actions
blocked_actions
```

### 3.2 `workflow validate-stage`

```bash
deck-master workflow validate-stage   --run-dir <run>   --stage deck-planner   --phase entry|exit
```

返回：

- valid；
- missing / invalid / stale artifacts；
- missing decisions；
- pending approvals；
- blocking conditions；
- warnings；
- next actions。

只读，不写状态。

### 3.3 `workflow questions`

```bash
deck-master workflow questions --run-dir <run> --stage deck-brief
```

根据 Stage Contract 和当前缺口返回：

- blocking questions；
- recommended questions；
- assumption-allowed questions；
- answer format；
- evidence requirement。

### 3.4 `workflow decision record`

记录用户答案、明确假设或审查决定。必须绑定 Stage 和当前 input fingerprint。

### 3.5 `workflow handoff prepare`

只在 Exit Validation 通过后生成 Handoff。相同 idempotency key + fingerprint 返回已有 Handoff。

### 3.6 `workflow handoff accept/reject`

- Accept 生成 append-only approval record。
- Reject 必须记录理由和 repair owner stage。
- 不允许直接编辑 Handoff JSON。

### 3.7 `workflow preauthorize`

只允许 production advanced user 显式创建。必须声明 transitions、expiry、actor、scope、cost ceiling。

### 3.8 `workflow bootstrap`

用于旧 Run：扫描现有 Artifact，生成 legacy inference report 和初始 Workflow State，但不伪造历史 Approval。

### 3.9 `workflow autopilot`

每轮算法：

```text
resolve state
→ validate current stage entry
→ ask/stop on blocking questions
→ execute allowed action
→ validate exit
→ prepare handoff
→ apply approval policy
→ accept or stop
→ recompute state
```

## 4. Exit Code

| Code | 含义 |
|---:|---|
| 0 | 成功或已达到预期 stop condition |
| 2 | 用户输入 / 参数错误 |
| 3 | Entry blocked |
| 4 | Exit validation failed |
| 5 | Approval required |
| 6 | Handoff stale / conflict |
| 7 | Capability unavailable |
| 8 | Unsafe production action blocked |

JSON stdout 必须始终可解析；诊断写 stderr。

## 5. Idempotency

以下命令必须幂等：

- `workflow status`
- `validate-stage`
- `questions`
- `handoff prepare`（同 fingerprint）
- `handoff accept`（同 approval binding）
- `bootstrap`

## 6. Event

每个 mutation 写 typed event：

```text
workflow.stage.entered
workflow.stage.completed
workflow.stage.stale
workflow.handoff.prepared
workflow.handoff.accepted
workflow.handoff.rejected
workflow.approval.stale
workflow.preauthorization.used
workflow.autopilot.stopped
```

---

<!-- SOURCE: 05-artifact-contracts.md -->

# Artifact Contracts

## 1. Run 目录新增结构

```text
<run>/
  workflow/
    workflow_state.json
    current_handoff.json
    handoff_index.json
    handoffs/
      <handoff_id>.json
    approval_log.jsonl
    decision_log.jsonl
    preauthorization.json          # optional
    bootstrap_report.json          # legacy only
    evidence/
      <stage_id>/
  sourcing_plan.v2.json
  page_packages/
    index.json
    <page_id>.json
  build/
    build_manifest.v2.json
```

## 2. `deck_skill_handoff.v1`

核心字段：

- handoff identity；
- from / to Stage；
- contract version；
- status；
- input / output artifact refs 与 hashes；
- stage output fingerprint；
- exit validation；
- decisions；
- unresolved warnings；
- approval policy；
- accepted/rejected metadata；
- stale / superseded metadata。

## 3. `deck_workflow_state.v1`

这是派生快照，包含：

- current Skill Stage；
- Runtime Sub-stage；
- 9 个 Stage 的状态；
- completed / stale stages；
- current Handoff；
- Approval summary；
- missing / invalid / stale artifacts；
- next Skill；
- allowed / blocked actions；
- source fingerprint；
- resolver version。

## 4. `deck_stage_approval.v1`

Approval Log 每行一条记录。状态变更使用新记录，不覆盖旧行。

必须绑定：

- approval id；
- handoff id；
- transition；
- stage output fingerprint；
- bound artifact hashes；
- actor / role；
- decision；
- reason；
- created / decided / expires；
- preauthorization reference（如有）。

## 5. `deck_decision_record.v1`

记录：

- question id / category；
- answer；
- actor；
- source type；
- stage；
- required / assumption allowed；
- evidence refs；
- input fingerprint；
- created at。

## 6. `deck_sourcing_plan.v2`

每个 Page Task 必须有一条决定：

```text
reuse
adapt
generate
evidence
manual
blocked
```

每条决定至少包含：

- page / task identity；
- claim / evidence need；
- selected source candidates；
- source authority 与 freshness；
- reuse permission / usage constraint；
- asset role；
- missing evidence；
- production budget class；
- decision reason / confidence；
- approval readiness。

Sourcing Plan 不得包含最终客户页正文。

## 7. `deck_page_package.v1`

### 7.1 允许 Builder 读取

```text
customer_visible
audience_context
visual_spec
asset_bindings
citations
style_refs
build_requirements
```

### 7.2 Builder 禁止读取到客户文件

```text
internal_only
production_rationale
agent_instructions
unresolved_questions
review_conversation
private_source_excerpt
```

### 7.3 最小结构

- identity / order；
- customer-visible title / subtitle / body blocks / labels / footnotes；
- speaker notes（独立）；
- visual composition；
- approved assets；
- claim / evidence bindings；
- provenance；
- internal-only notes；
- quality intent；
- build requirements；
- source fingerprint。

## 8. `deck_build_manifest.v2`

必须引用 `page_package`，而不是直接引用任意 Preview 字段。

每页记录：

- page package path / hash；
- page order；
- customer payload hash；
- approved asset hashes；
- target output modes；
- editability target；
- style lock；
- backend requirement。

## 9. Legacy Adapter

旧 `preview_manifest` 到 `page_package` 的转换必须：

- 显式调用；
- 写 `legacy_imported=true`；
- 不创造缺失正文或证据；
- 缺少客户可见字段时阻断；
- 生成 migration report；
- 重新进入 Review。

---

<!-- SOURCE: 06-production-boundaries.md -->

# Production Boundary Contracts

## 1. Deck Sourcing

### 输入

- approved Planner Handoff；
- page tasks；
- claim / evidence graph；
- material inventory；
- PPT Library candidates；
- project reference assets。

### 输出

- `sourcing_plan.v2.json`；
- optional candidate review pack；
- source / evidence gaps。

### 禁止

- 写最终页面标题和正文；
- 生成 HTML/PPTX；
- 把低权威来源静默当成已批准证据；
- 未记录权限就复用客户或第三方资产。

## 2. Deck Producer

### 输入

- accepted Sourcing Handoff；
- approved Brief / Narrative / Page Tasks；
- sourcing_plan.v2；
- style / brand / customer-visible policy。

### 输出

- required pages 的 `page_package.v1`；
- page package index；
- generation result v2 / preview refs；
- unresolved page-level blockers。

### 禁止

- 装配整套交付文件；
- 修改已批准 Narrative，而不创建回退 Handoff；
- 把 internal-only 字段混入 customer-visible；
- 以缺少证据的推断冒充事实。

## 3. Deck Builder

### 输入

- accepted Producer Handoff；
- valid Page Packages；
- certified PPT Master Backend；
- output profile。

### 输出

- build manifest v2；
- HTML / PDF / PNG / PPTX；
- artifact manifest；
- render result；
- build warnings。

### 禁止

- 新增业务主张；
- 改写页面观点；
- 读取 internal-only 字段进入客户文件；
- production 直接消费旧 preview manifest；
- backend 不可用时降级成 contract-smoke 并宣称完成。

## 4. Deck Quality

### 输入

- completed Builder Handoff；
- final artifact bundle；
- page packages / claims / evidence；
- customer visible policy。

### 输出

- artifact validation；
- customer-visible safety；
- evidence / brand / confidentiality / render / delivery findings；
- repair owner stage。

### 禁止

- 代表用户批准风险；
- 修改最终 Artifact；
- 把质量 pass 直接转换为 client export approval。

## 5. Deck Review

### 输入

- Quality Handoff；
- final artifacts；
- findings；
- page decisions；
- final readiness facts。

### 输出

- review decision；
- repair handoff 或 final approval；
- export queue；
- delivery record。

### 禁止

- 未绑定 Artifact hash 的批准；
- 未解决 P0 时导出；
- 用 Preview Approval 替代 Final Artifact Approval。

## 6. 外部能力 Adapter

### PPT Library

现有 selection 输出可由 Deck Master Adapter 归一化为 Sourcing Plan v2。第一阶段不要求 PPT Library 内核改造。

### PPT Deck Pro Max

必须能够输出或引用 Page Package。过渡期可通过 Generation Result v2 中的 `page_package_ref` 接入。

### PPT Master

必须声明对 Build Manifest v2 的兼容或由 Deck Builder Adapter 转换。完整 Backend 的 capability manifest 必须声明 supported contract versions。

### PPT Quality Gate

Findings 必须带 repair owner stage 或由 Deck Master Adapter 归一化。

---

<!-- SOURCE: 07-approval-autopilot-policy.md -->

# Approval & Autopilot v2 Policy

## 1. Policy Profiles

### `interactive`（production 默认）

所有高影响 Transition 停止并等待用户确认。

### `preauthorized`

只在存在有效 `workflow/preauthorization.json` 时启用。不得覆盖 final client export。

### `quick`

仅用于 fixture / dev；可自动推进到 Review，不得自动 client export。

### `repair`

只处理 Findings 指向的 owner Stage。涉及 Brief / Planner / Sourcing 方向变化时重新审批。

### `review-only`

不执行上游生产动作，只运行 Quality、Review、Readiness 和审批。

## 2. Transition Policy Matrix

| Transition | Interactive | Preauthorized | Quick | Repair | Review-only |
|---|---|---|---|---|---|
| init → brief | auto | auto | auto | n/a | blocked |
| brief → planner | approve | allowed if scoped | auto | approve when affected | blocked |
| planner → sourcing | approve | allowed if scoped | auto | approve when affected | blocked |
| sourcing → producer | approve | allowed with cost/source scope | auto in dev | approve when affected | blocked |
| producer → builder | auto | auto | auto | auto | blocked |
| builder → quality | auto | auto | auto | auto | allowed |
| quality → review | auto | auto | auto | auto | allowed |
| review → repair | prepare handoff | prepare handoff | prepare handoff | allowed | allowed |
| review → client export | **always approve** | **always approve** | blocked | **always approve** | **always approve** |

## 3. Preauthorization

必须包含：

- actor / role；
- created / expires；
- run id；
- allowed transitions；
- approved material roots；
- allowed source classes；
- max generated pages / cost class；
- protected transitions；
- baseline fingerprint；
- revoke status。

以下永远不可预授权：

- client export；
- P0 override；
- confidentiality override；
- source permission override。

## 4. Autopilot Stop Conditions

Autopilot 必须停止于：

- missing required material；
- blocking forcing question；
- high-impact approval required；
- external Agent execution required；
- backend unavailable；
- handoff stale / conflict；
- P0 finding；
- final artifact approval required；
- client export ready。

## 5. Autopilot Evidence

每个 Step 写：

- stage before / after；
- validation refs；
- action；
- artifact refs；
- handoff id；
- approval decision / preauthorization reference；
- elapsed time；
- stop reason。

## 6. 用户确认语义

接受 Handoff 的 UI / CLI 必须展示：

- 这次确认会进入哪个 Stage；
- 当前确认绑定的关键产物版本；
- 会触发的自动动作；
- 预计产生的成本或外部调用；
- 如何撤销或返修。

不得只展示“继续 / 确认”而不说明范围。

---

<!-- SOURCE: 08-review-desk-integration.md -->

# Review Desk Skill OS Integration

## 1. 本轮 UI 原则

不重做 Review Desk v0.3 的整体布局。本轮在现有顶部状态带、三栏审查台和底部抽屉中加入 Skill OS 信息。

## 2. 最小 Skill OS 视图

### 顶部状态带

- 当前 Skill Stage；
- Runtime Sub-stage；
- Stage status；
- 下一推荐 Skill；
- Approval badge；
- Resume / Review Handoff 主动作。

### 左侧 Stage Rail

显示 9 个生产 Stage：

- completed；
- current；
- awaiting approval；
- stale；
- blocked；
- not started。

### 中央工作区

- 当前 Stage 的业务问题；
- Required output 概览；
- Blocking questions；
- Artifact preview / summary；
- 当前 Stage exit readiness。

### 右侧决策区

顺序固定：

1. Stage 定位；
2. 输入 / 输出 Artifact；
3. 缺口与风险；
4. Handoff summary；
5. Approval / rejection history；
6. 处理动作。

### 技术抽屉

仅在展开后显示：

- raw stage id；
- CLI command；
- absolute path；
- contract version；
- hashes；
- backend diagnostics。

## 3. API

建议新增：

```text
GET  /api/workflow-status/<run_id>
GET  /api/workflow-handoffs/<run_id>
GET  /api/workflow-questions/<run_id>?stage=<stage>
POST /api/workflow-handoff/<run_id>/accept
POST /api/workflow-handoff/<run_id>/reject
POST /api/workflow-autopilot/<run_id>/resume
```

现有 Workspace API 可嵌入 `runtime.skill_os` projection，但不得由前端自行拼 Stage 状态。

## 4. 用户可见文案

业务文案示例：

- “方案简报已完成，等待确认后进入叙事规划。”
- “页面来源方案尚有 3 个证据缺口。”
- “页面内容包已齐，系统将自动进入文件构建。”
- “最终文件已通过自动检查，等待交付审批。”

禁止主界面展示：

- `needs_narrative_plan`；
- raw command；
- local absolute path；
- JSON filename 作为主动作；
- internal-only page fields。

## 5. UI Acceptance

- 任何 Run 都能显示 current skill stage。
- Awaiting approval 状态不可与普通 blocker 混淆。
- Handoff accept/reject 后 1 次刷新内状态一致。
- Stale Stage 有明确原因和返修 owner。
- Final export 按钮只在 final approval valid 时可用。
- 无 Preview 的早期 Stage 仍能使用 Stage 工作区。

---

<!-- SOURCE: 09-compatibility-migration-release.md -->

# Compatibility, Migration & Release

## 1. Legacy Run Bootstrap

### 1.1 原则

- 不重写原 Artifact。
- 不伪造历史 Approval。
- 根据现有 Artifact 推断最高可证明 Stage。
- 推断状态标记 `legacy_inferred=true`。
- 在下一个高影响 Transition 或 client export 前要求确认。

### 1.2 输出

```text
workflow/bootstrap_report.json
workflow/workflow_state.json
```

Report 记录：

- discovered artifacts；
- inferred completed stages；
- missing contracts；
- approvals not provable；
- stale risks；
- required next action。

## 2. `ppt-*` Compatibility

| 旧入口 | 新公开 Stage | 规则 |
|---|---|---|
| `ppt-library` | `deck-sourcing` | selection 必须进入 Sourcing Plan / Handoff |
| `ppt-deck-pro-max` | `deck-producer` | result 必须引用 Page Package 或可归一化 |
| `ppt-master` | `deck-builder` | build result 必须进入 Builder Handoff |
| `ppt-quality-gate` | `deck-quality` | findings 必须进入 Quality Bundle |

旧入口在 v1.x 不删除。兼容 Skill 文档必须说明 public Stage 和 handback 规则。

## 3. 外部完整 Skill Package / Ability-style Compatibility

不得只按目录名称判断是否采用外部完整 Skill。定义通用 external package manifest：

```text
skill name
package version
contract versions
operations
entry command
smoke command
handoff contracts
source repository / SHA
production_capable
```

规则：

- 已安装的完整 real directory 不被覆盖。
- Symlink 到外部完整包同样允许。
- 只有 manifest + smoke + contract compatibility 通过，才可标记 production capable。
- Adapter-only 包不得冒充完整能力。
- 外部包的输出仍必须回写 Deck Master Run。

## 4. Manifest Migration

`skills/manifest.json` 升级到 1.1.0：

- 每个 public production skill 增加 `stage_id`；
- 引用 `stage_contract_version`；
- 增加 `transition_role`；
- compat skill 增加 `public_stage`；
- Installer / Router 从 Manifest 加载。

`skills/stage-contracts.json` 随 Release Tree 发布并写入 capability lock。

## 5. Version Governance

A0 必须统一：

- suite version；
- runtime version；
- skill conformance version；
- contract version；
- release notes version。

不得继续出现 Skill Suite 1.0.0、runtime 0.9.x、release docs 另一版本但无映射说明的情况。

## 6. Release Tree

必须新增：

```text
skills/stage-contracts.json
contracts/workflow/
workflow-migrations/
```

Release verification 检查：

- Manifest / Stage Contract 引用完整；
- Skill docs frontmatter 与 Manifest 一致；
- Schema hash lock；
- external package compatibility metadata；
- Workflow CLI smoke；
- legacy bootstrap smoke。

## 7. Deprecation

- 本轮不删除命令。
- 旧顶层命令只增加 machine-readable `canonical_command`。
- v1.2 前不把 deprecation warning 放进用户主文案。
- 删除任何别名前必须有使用证据和迁移说明。

---

<!-- SOURCE: stacks/stack-a-stage-contract-handoff-runtime.md -->

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

---

<!-- SOURCE: stacks/stack-b-production-boundary-autopilot.md -->

# Stack B — Production Boundary & Autopilot v2

## 目标

把 Sourcing、Producer、Builder 的职责和 Artifact 边界固定，并让 Autopilot 按 Stage Contract 和 Approval Policy 工作。

## 包含任务

- B1 Forcing Questions & Decision Log
- B2 Sourcing Plan v2
- B3 Page Package v1 & Producer Contract
- B4 Build Manifest v2 & Builder Whitelist
- B5 Autopilot v2

## 关键约束

- Production Builder 不再直接消费旧 Preview Manifest。
- Builder 只能读取 Page Package 白名单字段。
- Sourcing Plan 不得包含最终页正文。
- Producer 不得构建最终文件。
- Autopilot 不得自行接受高影响 Handoff。

## Stack Exit Criteria

- 一个新 Production Run 可从 approved planner handoff 走到 Quality Handoff。
- Brief / Planner / Sourcing 审批按策略停顿。
- Producer required pages 均有 valid Page Package。
- Builder customer-visible leakage test 为 0。
- Repair mode 可按 finding owner 返回正确 Stage。

---

<!-- SOURCE: stacks/stack-c-review-desk-compat-release.md -->

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

---

<!-- SOURCE: tasks/A0-baseline-version-freeze.md -->

# A0 — Baseline & Version Freeze

## 1. 目标

锁定当前 main、实际命令、Artifact 真源、版本号和实现偏差，避免后续任务按不同假设开发。

## 2. In Scope

- main / release / suite / contract 基线。
- 当前测试与安装事实。
- 实现 Spec、Deviation Log、Progress、Test Evidence。

## 3. Out of Scope

不修改 Runtime 行为。

## 4. 允许修改路径

- `docs/specs/skill-os/implementation/`
- `docs/specs/README.md`

超出路径必须先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md`，说明原因、影响、兼容和验证。

## 5. 必须实现

1. 记录 main SHA。
2. 统一目标版本 1.1.0 的映射。
3. 列出所有兼容命令和 schema 真源。
4. 记录本机外部能力路径，只写脱敏事实。
5. 建立 deviation log。

## 6. 测试

- JSON / Markdown parse。
- `git diff --check`。
- 记录当前全量测试，不得掩盖失败。

## 7. 成功标准

- 后续任务拥有唯一基线。
- 版本映射无歧义。

## 8. 依赖与并发

第一任务；完成前禁止其他 Stack 合并。

## 9. Agent 交付报告

必须输出：修改文件、Schema 变化、迁移影响、测试命令与真实结果、未完成项、风险、建议评审重点。

---

<!-- SOURCE: tasks/A1-manifest-stage-contract-registry.md -->

# A1 — Canonical Manifest & Stage Contract Registry

## 1. 目标

消除 Skill metadata 多真源，建立 9 个生产 Stage 的版本化 Contract Registry。

## 2. In Scope

- Manifest loader。
- Stage Contract loader/validator。
- Manifest 1.1.0。
- Stage Contract schema 和 9 个 contract。

## 3. Out of Scope

不修改 Run State 阶段判断。

## 4. 允许修改路径

- `skills/manifest.json`
- `skills/stage-contracts.json`
- `scripts/skills/manifest.py`
- `docs/contracts/`
- `tests/test_skill_manifest.py`
- `tests/test_stage_contract_registry.py`

超出路径必须先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md`，说明原因、影响、兼容和验证。

## 5. 必须实现

1. Runtime/Installer/Router 可从 Manifest 读取。
2. 9 个 Stage Contract 字段完整。
3. compat aliases 和 backend dependencies 可解析。
4. 禁止重复 skill name / stage order / input type collision。
5. Contract hash 可进入 release lock。

## 6. 测试

- Manifest schema。
- 9/9 contract validation。
- duplicate / missing / bad reference negative tests。
- installer/route compatibility tests。

## 7. 成功标准

- 所有 Skill identity 由一个真源加载。
- 9 个 Stage Contract 可稳定读取。

## 8. 依赖与并发

依赖 A0。

## 9. Agent 交付报告

必须输出：修改文件、Schema 变化、迁移影响、测试命令与真实结果、未完成项、风险、建议评审重点。

---

<!-- SOURCE: tasks/A2-workflow-state-resolver.md -->

# A2 — Workflow State Resolver

## 1. 目标

基于 Contract、Artifact、Handoff、Approval 推导全 Stage 状态，同时保留 Runtime Sub-stage。

## 2. In Scope

- Workflow State v1。
- Stage entry/exit validator。
- Fingerprint / stale propagation。
- Snapshot writer。

## 3. Out of Scope

不实现 Handoff mutation 和 Approval mutation。

## 4. 允许修改路径

- `scripts/workflow/`
- `scripts/runtime/run_state_resolver.py`
- `docs/contracts/workflow-state.v1.schema.json`
- `tests/test_workflow_state.py`
- `tests/test_stage_validation.py`

超出路径必须先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md`，说明原因、影响、兼容和验证。

## 5. 必须实现

1. 9 个 Stage 状态可推导。
2. current skill stage 与 runtime stage 分开。
3. missing / invalid / stale artifact 分类。
4. 上游变化传播 stale。
5. Snapshot 可完全重建。

## 6. 测试

- empty/new/partial/completed/stale runs。
- upstream mutation stale propagation。
- corrupt handoff/approval ignored as invalid fact。
- deterministic resolver output。

## 7. 成功标准

- 同一 Run 重算结果稳定。
- 不再只按单文件存在判断完成。

## 8. 依赖与并发

依赖 A1。

## 9. Agent 交付报告

必须输出：修改文件、Schema 变化、迁移影响、测试命令与真实结果、未完成项、风险、建议评审重点。

---

<!-- SOURCE: tasks/A3-handoff-runtime.md -->

# A3 — Skill Handoff Runtime

## 1. 目标

实现 append-only Handoff prepare、consume、stale、supersede 和 current projection。

## 2. In Scope

- Handoff schema。
- prepare / list / inspect / consume。
- idempotency。
- event。
- file lock。

## 3. Out of Scope

不实现用户审批策略。

## 4. 允许修改路径

- `scripts/workflow/handoff.py`
- `docs/contracts/skill-handoff.v1.schema.json`
- `tests/test_skill_handoff.py`

超出路径必须先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md`，说明原因、影响、兼容和验证。

## 5. 必须实现

1. Exit validation 不通过时不能 prepare。
2. 相同 fingerprint 幂等。
3. 上游变化标记 stale。
4. superseded 记录保留。
5. current_handoff 只是投影。

## 6. 测试

- prepare/duplicate/consume/stale/supersede。
- concurrent write。
- unsafe path / bad hash。

## 7. 成功标准

- 所有 Stage Transition 可生成可审计 Handoff。

## 8. 依赖与并发

依赖 A2。

## 9. Agent 交付报告

必须输出：修改文件、Schema 变化、迁移影响、测试命令与真实结果、未完成项、风险、建议评审重点。

---

<!-- SOURCE: tasks/A4-approval-preauthorization-runtime.md -->

# A4 — Approval & Preauthorization Runtime

## 1. 目标

建立绑定 Handoff、Transition 和 Artifact Fingerprint 的审批与显式预授权。

## 2. In Scope

- Approval log。
- accept / reject / revoke。
- preauthorization。
- stale approval。
- non-bypassable policy。

## 3. Out of Scope

不实现 UI。

## 4. 允许修改路径

- `scripts/workflow/approval.py`
- `scripts/workflow/policy.py`
- `docs/contracts/stage-approval.v1.schema.json`
- `docs/contracts/workflow-policy.v1.schema.json`
- `tests/test_workflow_approval.py`

超出路径必须先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md`，说明原因、影响、兼容和验证。

## 5. 必须实现

1. 高影响 Transition 缺审批时阻断。
2. final export 不可预授权。
3. approval 绑定 hashes。
4. expiry/revoke/stale 生效。
5. reject 携带 repair owner。

## 6. 测试

- all transition policies。
- expired / revoked / wrong fingerprint。
- attempted final export preauth。
- duplicate decisions。

## 7. 成功标准

- 不存在无绑定 Approval。
- final export 绕过率 0。

## 8. 依赖与并发

依赖 A3。

## 9. Agent 交付报告

必须输出：修改文件、Schema 变化、迁移影响、测试命令与真实结果、未完成项、风险、建议评审重点。

---

<!-- SOURCE: tasks/A5-workflow-cli-route-integration.md -->

# A5 — Workflow CLI & Route Integration

## 1. 目标

提供统一 `workflow` 命令组，并让 route、next-step、run-state 共用 Workflow Resolver。

## 2. In Scope

- CLI。
- compatibility aliases。
- route / next-step / run-state projection。
- typed events。

## 3. Out of Scope

不改 Autopilot 行为。

## 4. 允许修改路径

- `scripts/deck_master.py`
- `scripts/runtime/skill_route.py`
- `scripts/runtime/next_step.py`
- `tests/test_workflow_cli.py`
- `tests/test_skill_route.py`

超出路径必须先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md`，说明原因、影响、兼容和验证。

## 5. 必须实现

1. canonical commands 全部可用。
2. 旧命令继续可用。
3. 四个状态入口一致。
4. JSON stdout / exit code 符合 Spec。
5. Manifest 驱动 route。

## 6. 测试

- CLI positive/negative。
- route consistency matrix。
- alias compatibility。
- no raw mutation for validate/status。

## 7. 成功标准

- Stack A 全链路可在 CLI 验收。

## 8. 依赖与并发

依赖 A1-A4。

## 9. Agent 交付报告

必须输出：修改文件、Schema 变化、迁移影响、测试命令与真实结果、未完成项、风险、建议评审重点。

---

<!-- SOURCE: tasks/B1-forcing-questions-decision-log.md -->

# B1 — Forcing Questions & Decision Log

## 1. 目标

把访谈能力纳入各 Stage Contract，并让关键答案成为可追踪事实。

## 2. In Scope

- Question resolver。
- Decision record schema/runtime。
- brief/planner/sourcing/producer question packs。
- blocking question logic。

## 3. Out of Scope

不新增独立访谈 Skill；不内置模型。

## 4. 允许修改路径

- `scripts/workflow/questions.py`
- `scripts/workflow/decisions.py`
- `skills/stage-contracts.json`
- `docs/contracts/decision-record.v1.schema.json`
- `tests/test_workflow_questions.py`

超出路径必须先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md`，说明原因、影响、兼容和验证。

## 5. 必须实现

1. 只返回当前缺口问题。
2. required / assumption-allowed 可区分。
3. blocking 未答时 exit validation 失败。
4. answer 绑定 fingerprint。
5. stale answer 可识别。

## 6. 测试

- stage-specific question matrix。
- no-question happy path。
- required unanswered。
- stale decision。

## 7. 成功标准

- 访谈深度由 Runtime 约束，不依赖 Agent 自觉。

## 8. 依赖与并发

依赖 Stack A。

## 9. Agent 交付报告

必须输出：修改文件、Schema 变化、迁移影响、测试命令与真实结果、未完成项、风险、建议评审重点。

---

<!-- SOURCE: tasks/B2-sourcing-plan-v2.md -->

# B2 — Sourcing Plan v2

## 1. 目标

把每页来源、证据、权限、时效和生产决策固化为 Producer 的唯一来源输入。

## 2. In Scope

- schema/runtime migration。
- PPT Library adapter。
- per-page completeness。
- approval readiness。

## 3. Out of Scope

不写最终页正文；不修改 PPT Library 内核。

## 4. 允许修改路径

- `scripts/sourcing/`
- `scripts/tools/ppt_library_client.py`
- `docs/contracts/sourcing-plan.v2.schema.json`
- `tests/test_sourcing_plan_v2.py`

超出路径必须先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md`，说明原因、影响、兼容和验证。

## 5. 必须实现

1. 每个 page task 一条决定。
2. 允许六类 decision。
3. source authority/freshness/permission 字段。
4. 缺口显式。
5. v1 safe migration。

## 6. 测试

- 0/1/multiple candidates。
- permission blocked。
- stale evidence。
- incomplete page coverage。
- v1 migration。

## 7. 成功标准

- Producer 不再猜测来源决策。

## 8. 依赖与并发

依赖 A5，可与 B1 部分并行。

## 9. Agent 交付报告

必须输出：修改文件、Schema 变化、迁移影响、测试命令与真实结果、未完成项、风险、建议评审重点。

---

<!-- SOURCE: tasks/B3-page-package-producer-contract.md -->

# B3 — Page Package v1 & Producer Contract

## 1. 目标

建立 Producer 与 Builder 的正式页面级边界，隔离客户可见内容和内部制作信息。

## 2. In Scope

- Page Package schema。
- index / validator。
- generation result refs。
- PPT Deck Pro Max adapter contract。

## 3. Out of Scope

不构建最终文件；不重写 production intelligence 算法。

## 4. 允许修改路径

- `scripts/production/`
- `scripts/generation/`
- `docs/contracts/page-package.v1.schema.json`
- `tests/test_page_package.py`
- PPT Deck Pro Max bridge 对应分支

超出路径必须先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md`，说明原因、影响、兼容和验证。

## 5. 必须实现

1. required pages 全覆盖。
2. customer_visible / internal_only 严格分区。
3. claim/evidence/asset bindings。
4. source fingerprint。
5. Generation Result 可引用 package。

## 6. 测试

- schema / content boundary。
- internal leakage negative tests。
- missing page / evidence。
- cross-repo bridge contract smoke。

## 7. 成功标准

- Builder 可只依赖 Page Package。

## 8. 依赖与并发

依赖 B1、B2。跨仓库变更需独立 PR 和固定 SHA。

## 9. Agent 交付报告

必须输出：修改文件、Schema 变化、迁移影响、测试命令与真实结果、未完成项、风险、建议评审重点。

---

<!-- SOURCE: tasks/B4-build-manifest-v2-builder-boundary.md -->

# B4 — Build Manifest v2 & Builder Boundary

## 1. 目标

让 Production Builder 只消费批准的 Page Package 白名单字段。

## 2. In Scope

- Build Manifest v2。
- Page Package projection。
- legacy preview adapter。
- PPT Master adapter contract。

## 3. Out of Scope

不重做 PPT Master 视觉内核。

## 4. 允许修改路径

- `scripts/runtime/build.py`
- `scripts/runtime/builder_backend.py`
- `scripts/build/`
- `docs/contracts/build-manifest.v2.schema.json`
- `tests/test_build_manifest_v2.py`

超出路径必须先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md`，说明原因、影响、兼容和验证。

## 5. 必须实现

1. production direct preview input blocked。
2. whitelist projection。
3. package hash / asset hash。
4. backend contract version check。
5. legacy adapter 显式且重新 Review。

## 6. 测试

- internal field leakage。
- missing/changed package。
- backend v1/v2 compatibility。
- legacy adapter。
- source fingerprint。

## 7. 成功标准

- 客户 Artifact 中 internal-only 泄漏为 0。

## 8. 依赖与并发

依赖 B3。

## 9. Agent 交付报告

必须输出：修改文件、Schema 变化、迁移影响、测试命令与真实结果、未完成项、风险、建议评审重点。

---

<!-- SOURCE: tasks/B5-autopilot-v2.md -->

# B5 — Workflow Autopilot v2

## 1. 目标

把现有直接命令循环升级为 Contract-aware、Approval-aware、Evidence-first 的工作流执行器。

## 2. In Scope

- mode policies。
- validate/action/exit/handoff loop。
- preauthorization consumption。
- repair routing。
- evidence report。

## 3. Out of Scope

不自动回答业务问题；不自动 client export。

## 4. 允许修改路径

- `scripts/workflow/autopilot.py`
- `scripts/deck_master.py`
- `tests/test_workflow_autopilot_v2.py`

超出路径必须先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md`，说明原因、影响、兼容和验证。

## 5. 必须实现

1. 每步执行统一算法。
2. 高影响审批停下。
3. 自动门禁继续。
4. preauth scope 校验。
5. final export 永远停止。
6. repair owner routing。

## 6. 测试

- all modes。
- approval stop。
- preauth valid/expired/out-of-scope。
- stale handoff。
- no-stage-advance loop。
- final export stop。

## 7. 成功标准

- Autopilot 无审批绕过。
- 每步 Evidence 完整。

## 8. 依赖与并发

依赖 B1-B4。

## 9. Agent 交付报告

必须输出：修改文件、Schema 变化、迁移影响、测试命令与真实结果、未完成项、风险、建议评审重点。

---

<!-- SOURCE: tasks/C1-review-desk-skill-os-view.md -->

# C1 — Review Desk Skill OS View

## 1. 目标

在 Review Desk v0.3 中展示 Stage Ladder、Handoff、Approval、Stale 和 Next Skill。

## 2. In Scope

- API projection。
- stage rail。
- handoff accept/reject。
- resume autopilot。
- safe display copy。

## 3. Out of Scope

不重做整体布局；不在前端推导 Stage。

## 4. 允许修改路径

- `scripts/preview/workspace_api.py`
- `scripts/preview/server.py`
- `scripts/preview/static/`
- `tests/test_review_desk_skill_os.py`
- `tests/test_preview_static_contract.py`

超出路径必须先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md`，说明原因、影响、兼容和验证。

## 5. 必须实现

1. 9 Stage 状态展示。
2. awaiting approval 与 blocker 区分。
3. accept/reject 写 Runtime。
4. stale 原因可见。
5. raw path/command 不上主界面。

## 6. 测试

- 早期无 Preview。
- awaiting approval。
- stale。
- repair。
- ready for export。
- mobile / desktop smoke。

## 7. 成功标准

- 用户不需理解 Runtime code 即可推进。

## 8. 依赖与并发

依赖 B5。

## 9. Agent 交付报告

必须输出：修改文件、Schema 变化、迁移影响、测试命令与真实结果、未完成项、风险、建议评审重点。

---

<!-- SOURCE: tasks/C2-skill-doc-manifest-conformance.md -->

# C2 — Skill Docs & Manifest Conformance

## 1. 目标

把公开 Skill 从命令索引升级为完整工作流入口，并用自动检查防止漂移。

## 2. In Scope

- 14 public SKILL.md。
- 4 compat SKILL.md。
- doc structure validator。
- Manifest/frontmatter consistency。

## 3. Out of Scope

不改变 Skill 名称。

## 4. 允许修改路径

- `skills/*/SKILL.md`
- `scripts/skills/validator.py`
- `tests/test_skill_doc_contract.py`

超出路径必须先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md`，说明原因、影响、兼容和验证。

## 5. 必须实现

1. Use When / Do Not Use / First Checks / Forcing Questions / Runtime Ownership / Allowed Commands / Exit Artifacts / Next Skill / Stop Conditions / Safety Rules 全部存在。
2. 文档命令真实存在。
3. exit artifacts 与 Manifest 一致。
4. compat wrapper 指向 public stage。

## 6. 测试

- all skill docs。
- bad section/frontmatter/command。
- compatibility trigger。

## 7. 成功标准

- 100% public skill conformance。

## 8. 依赖与并发

依赖 A1，可在 B5 后收口。

## 9. Agent 交付报告

必须输出：修改文件、Schema 变化、迁移影响、测试命令与真实结果、未完成项、风险、建议评审重点。

---

<!-- SOURCE: tasks/C3-legacy-compat-migration.md -->

# C3 — Legacy Run, ppt-* & External Package Compatibility

## 1. 目标

保证升级不会破坏旧 Run、旧 Skill 调用和外部完整能力包。

## 2. In Scope

- workflow bootstrap。
- legacy preview adapter。
- ppt wrappers。
- generic external package manifest。
- migration/rollback。

## 3. Out of Scope

不删除旧 alias。

## 4. 允许修改路径

- `scripts/workflow/migration.py`
- `scripts/skills/installer.py`
- `skills/ppt-*/`
- `docs/migration/`
- `tests/test_skill_os_migration.py`

超出路径必须先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md`，说明原因、影响、兼容和验证。

## 5. 必须实现

1. 旧 Run inference 不伪造 approval。
2. 旧 alias 输出 canonical artifacts。
3. external real dir/symlink 均保留。
4. manifest + smoke + contract 判断 production capable。
5. rollback。

## 6. 测试

- old run snapshots。
- foreign symlink / real dir / adapter-only。
- rollback。
- old CLI prompts。

## 7. 成功标准

- 现有用户升级后主链路不丢失。

## 8. 依赖与并发

依赖 A1-A5、B3-B4。

## 9. Agent 交付报告

必须输出：修改文件、Schema 变化、迁移影响、测试命令与真实结果、未完成项、风险、建议评审重点。

---

<!-- SOURCE: tasks/C4-installer-ci-rc-release.md -->

# C4 — Installer, CI, RC & Release Closure

## 1. 目标

把 Skill OS 的合同、命令、迁移和 E2E 固化到 release 和 CI。

## 2. In Scope

- release tree。
- capability lock。
- schema validation。
- clean install。
- RC gate。
- docs / release notes。

## 3. Out of Scope

CI 不运行私有客户原文。

## 4. 允许修改路径

- `scripts/skills/installer.py`
- `scripts/runtime/rc_gate.py`
- `.github/workflows/`
- `docs/releases/`
- `tests/`

超出路径必须先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md`，说明原因、影响、兼容和验证。

## 5. 必须实现

1. release 包含 Stage Contracts / schemas / migrations。
2. JSON Schema 实际验证，不只是 parse。
3. Codex/Claude temp HOME。
4. route consistency / handoff / approval / autopilot / bootstrap smoke。
5. archive/checksum。

## 6. 测试

- Linux CI。
- temp HOME。
- moved repo。
- install/upgrade/rollback。
- invalid contract lock。
- RC pass/block fixtures。

## 7. 成功标准

- Main CI 全绿。
- Release Artifact 可验证。
- 缺任何 required evidence 时 RC blocked。

## 8. 依赖与并发

依赖 C1-C3。

## 9. Agent 交付报告

必须输出：修改文件、Schema 变化、迁移影响、测试命令与真实结果、未完成项、风险、建议评审重点。

---

<!-- SOURCE: tasks/C5-dogfood-final-acceptance.md -->

# C5 — Dogfood & Final Acceptance

## 1. 目标

用真实可脱敏的项目流程证明 Skill OS 解决了交接和确认问题。

## 2. In Scope

- 新 Run。
- Legacy Run bootstrap。
- Quality repair loop。
- user confirmation usability。
- evidence pack。

## 3. Out of Scope

不提交私有客户原文。

## 4. 允许修改路径

- `docs/qa/skill-os/`
- local-only run evidence
- sanitized acceptance summaries

超出路径必须先写入 `docs/specs/skill-os/implementation/spec-deviation-log.md`，说明原因、影响、兼容和验证。

## 5. 必须实现

1. 新 Run 走完整 9 Stage。
2. 至少 3 个高影响 approval。
3. final export approval 绑定 artifact hash。
4. legacy bootstrap。
5. repair return path。
6. Review Desk 使用记录。

## 6. 测试

- acceptance matrix。
- stage consistency。
- stale mutation。
- approval invalidation。
- export blocking。

## 7. 成功标准

- 所有 Master Spec 量化指标达到。
- 无未登记 P0。

## 8. 依赖与并发

最终任务，依赖 C4。

## 9. Agent 交付报告

必须输出：修改文件、Schema 变化、迁移影响、测试命令与真实结果、未完成项、风险、建议评审重点。

---

<!-- SOURCE: acceptance/acceptance-matrix.md -->

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

---

<!-- SOURCE: acceptance/qa-test-plan.md -->

# QA Test Plan

## 1. Unit

- Manifest / Stage Contract loader。
- Entry / Exit validator。
- Fingerprint / stale propagation。
- Handoff lifecycle / idempotency / locking。
- Approval / preauthorization / expiry / revoke。
- Question resolver / Decision Log。
- Sourcing Plan v2 validation。
- Page Package customer/internal boundary。
- Build Manifest v2 projection。
- Legacy bootstrap。

## 2. Integration

- Manifest → Router。
- Stage Contract → Workflow State。
- Exit validation → Handoff → Approval → downstream entry。
- Sourcing → Producer → Builder。
- Builder → Quality → Review。
- Review finding → Repair Handoff。
- Review approval → Export。

## 3. E2E

### E2E-1 New Production Run

```text
init
→ brief
→ approval
→ planner
→ approval
→ sourcing
→ approval
→ producer
→ builder
→ quality
→ review
→ final approval
→ export
```

### E2E-2 Legacy Run

```text
legacy artifacts
→ workflow bootstrap
→ inferred state
→ required confirmation
→ page package migration
→ review
```

### E2E-3 Repair

```text
quality P1/P0
→ repair owner stage
→ repair handoff
→ revalidation
→ new final approval
```

## 4. Mutation Tests

- 修改 brief 后 planner/downstream stale。
- 修改 sourcing plan 后 page packages/downstream stale。
- 修改 page package 后 final approval stale。
- 修改 final PPTX 后 export blocked。
- 删除 approval log line 后 transition blocked。

## 5. Security / Safety

- path traversal。
- absolute path 主界面泄漏。
- internal_only leakage。
- private source excerpt leakage。
- forged approval / wrong hash。
- expired preauthorization。
- client export preauthorization attempt。

## 6. Platform

- Ubuntu CI。
- macOS local smoke。
- temp HOME Codex。
- temp HOME Claude Code。
- moved release tree。
- upgrade / rollback。

## 7. Browser

最少场景：

- early stage no preview；
- awaiting brief approval；
- sourcing blocked；
- agent execution waiting；
- builder backend missing；
- quality blocked；
- repair handoff；
- final approval pending；
- ready to export；
- stale after artifact mutation。

---

<!-- SOURCE: acceptance/rc-checklist.md -->

# Skill OS RC Checklist

## Runtime

- [ ] Manifest 1.1.0 与 Stage Contracts 一致。
- [ ] 9 个 Stage Contract 通过 schema + semantic validation。
- [ ] Workflow State 可重建。
- [ ] Handoff append-only、幂等、可 stale。
- [ ] Approval 与 Fingerprint 绑定。
- [ ] Final export 不可预授权。

## Production Boundary

- [ ] Sourcing Plan v2 全页覆盖。
- [ ] Page Packages 全 required pages 覆盖。
- [ ] Builder 只消费 whitelist projection。
- [ ] Legacy Preview Adapter 只显式使用。
- [ ] PPT Deck Pro Max / PPT Master contract versions 固定。

## Autopilot

- [ ] interactive / preauthorized / quick / repair / review-only 全覆盖。
- [ ] 高影响 Gate 正确停止。
- [ ] 自动 Gate 正确推进。
- [ ] final export 必停。
- [ ] Evidence report 完整。

## Review Desk

- [ ] Stage Rail。
- [ ] Handoff summary。
- [ ] Approval actions。
- [ ] Stale reason。
- [ ] Next Skill。
- [ ] 主界面无命令和绝对路径。

## Compatibility

- [ ] Legacy Run bootstrap。
- [ ] `ppt-*` wrappers。
- [ ] external full real directory。
- [ ] external full symlink。
- [ ] adapter-only blocked for production。
- [ ] rollback。

## Release

- [ ] Full unit tests。
- [ ] Integration tests。
- [ ] 3 E2E。
- [ ] Codex temp HOME。
- [ ] Claude temp HOME。
- [ ] release archive + SHA256SUMS。
- [ ] RC report 无 required failure。
- [ ] docs / release notes / migration guide 更新。

---

<!-- SOURCE: agents/agent-execution-protocol.md -->

# Agent Execution Protocol

## 1. 开工前

1. 读取 `00-master-spec.md`。
2. 读取当前 Task Spec。
3. 读取依赖 Task 的 implementation evidence。
4. 核验 main SHA 和工作区干净状态。
5. 创建独立分支。

## 2. 开发约束

- 只修改允许路径；超出先写 deviation。
- 不以文档声明替代 Runtime 行为。
- 新 JSON 必须带 schema_version。
- Mutation 使用原子写、锁和 typed event。
- 不删除旧命令和 `ppt-*` wrapper。
- 不把 fixture / legacy inference 宣称为 production completion。
- 不提交客户原文、绝对路径、token 或本机私密配置。

## 3. 每个 Task 的提交要求

- 单 Task 至少一个独立 commit。
- Commit message 包含 Task ID。
- 测试失败必须如实记录。
- Schema 变化必须附兼容说明。

## 4. 完成报告

```text
Task:
Branch / SHA:
Modified files:
Contract changes:
Migration impact:
Tests executed:
Tests passed / failed:
Known limitations:
Spec deviations:
Review focus:
```

## 5. 禁止

- 未完成依赖就并行实现下游。
- 手工编辑 workflow_state 伪造完成。
- 在测试里跳过 Approval 以获得绿色结果。
- 用只检查文件存在的测试替代语义验证。
- 把 final export Approval 设为 optional。

---

<!-- SOURCE: agents/codex-prompts.md -->

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

---

<!-- SOURCE: agents/review-protocol.md -->

# Review Protocol

## 1. 评审顺序

1. Spec / deviation。
2. Contract 真源。
3. Runtime 行为。
4. Migration / compatibility。
5. Test quality。
6. UI / docs。
7. 成熟度提升。

## 2. P0 判定

- Stage 可无 Handoff 进入下游。
- 必需 Approval 可绕过。
- Final export 可预授权或自动执行。
- Builder 读取 internal-only。
- Workflow State 可被直接编辑而成为事实。
- Legacy migration 伪造 Approval。
- external full package 被覆盖。
- CI / RC 用 metadata 或文件存在代替行为证据。

## 3. 评审输出

```text
结论：Approve / Request Changes
P0：
P1：
P2：
Spec coverage：
Compatibility：
Tests：
Maturity impact：
Required fixes before merge：
```

## 4. 完成度口径

不得把以下内容算作已完成：

- 只有 SKILL.md 文案。
- 只有 CLI skeleton。
- 只有 schema 文件，无 Runtime validation。
- 只有 UI mock，没有 API truth。
- 只有 happy-path test。
- 只有 fixture，没有 production policy negative test。
