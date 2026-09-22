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
