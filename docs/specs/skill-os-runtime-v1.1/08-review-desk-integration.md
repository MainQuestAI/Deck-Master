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
