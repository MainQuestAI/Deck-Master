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
