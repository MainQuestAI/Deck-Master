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
