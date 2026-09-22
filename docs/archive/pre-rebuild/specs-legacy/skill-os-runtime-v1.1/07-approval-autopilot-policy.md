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
