# Deck Master Spec Pack

## 7. Spec 02：Runtime Core、Typed Events 与 Next Step

### 7.1 目标

建立 Deck Master 的 canonical runtime contract，使 CLI、Web UI、Agent 都基于同一状态解释。

### 7.2 核心模块

建议新增或重构：

```text
scripts/runtime/
  run_state.py
  events.py
  next_step.py
  schema.py
  migrations.py
  artifact_lock.py
```

### 7.3 Event schema

当前事件可兼容 `actor/action/status/target/payload_ref/error/data`，但 canonical event 必须新增：

```json
{
  "schema_version": "deck_event.v1",
  "timestamp": "2026-06-11T00:00:00Z",
  "event_id": "evt_20260611000000_0001",
  "event_type": "step_completed",
  "run_id": "retail-conversation",
  "step": "sourcing",
  "message": "Sourcing decision completed for 14 pages.",
  "refs": ["sourcing_plan.json"],
  "severity": "info",
  "actor": "deck_master",
  "action": "sourcing.plan.created",
  "status": "ok",
  "target": "sourcing_plan.json",
  "payload_ref": "sourcing_plan.json",
  "error": "",
  "data": {}
}
```

### 7.4 Event types

| event_type | 用途 |
|---|---|
| `run_created` | 创建 run |
| `step_started` | 步骤开始 |
| `step_completed` | 步骤完成 |
| `tool_call` | 外部工具调用 |
| `tool_result` | 外部工具结果 |
| `decision` | planner、sourcing、quality、export 决策 |
| `manual_action` | 用户审批、拒绝、备注、替换、锁定、override |
| `warning` | 可恢复问题 |
| `error` | 阻断问题 |

### 7.5 `next_step.json` schema

```json
{
  "schema_version": "deck_next_step.v1",
  "run_id": "retail-conversation",
  "status": "draft_gate_blocked",
  "current_step": "draft_gate",
  "next_step": "review_draft_gate_findings",
  "can_continue": true,
  "blocking": true,
  "blocking_reasons": [
    {
      "severity": "P1",
      "message": "3 pages missing evidence.",
      "refs": ["quality_reports/draft_gate.json"]
    }
  ],
  "available_actions": [
    "open_web_ui",
    "repair_page_tasks",
    "rerun_draft_gate"
  ],
  "artifact_status": {
    "request.json": "ok",
    "deck_brief.json": "ok",
    "claim_map.json": "ok",
    "narrative_plan.json": "ok",
    "page_tasks.json": "ok",
    "preview_manifest.json": "ok"
  },
  "updated_at": "2026-06-11T00:00:00Z"
}
```

### 7.6 Next-step resolution rules

| 条件 | next_step |
|---|---|
| `request.json` 缺失 | `create_request` |
| `context_manifest.json` 缺失且 run 来自 context | `build_context_manifest` |
| `conversation_session.json` 缺失且 context 存在 | `start_conversation` |
| `deck_brief.json` 缺失 | `build_brief` |
| `claim_map.json` 缺失 | `build_claim_map` |
| `narrative_plan.json` 缺失 | `plan_narrative` |
| `page_tasks.json` 缺失 | `build_page_tasks` |
| `library_results/selection.json` 缺失 | `search_library` |
| `sourcing_plan.json` 缺失 | `decide_sourcing` |
| `generation_tasks/index.json` 缺失 | `create_generation_tasks` |
| `preview_manifest.json` 缺失 | `build_preview` |
| `quality_reports/draft_gate.json` 缺失 | `run_draft_gate` |
| Draft Gate 有 P0/P1 或 `rework_required` | `review_draft_gate_findings` |
| 有待审页面 | `open_review_cockpit` |
| 有 approved 页面 | `export_approved_queue` |
| 已导出但无 delivery outcome | `record_delivery_outcome` |

### 7.7 CLI

```bash
python3 scripts/deck_master.py status --run-id <run_id>
python3 scripts/deck_master.py next-step --run-id <run_id>
python3 scripts/deck_master.py resume --run-id <run_id> --through preview
python3 scripts/deck_master.py validate-run --run-id <run_id>
```

### 7.8 验收

- CLI 和 Web UI 读取同一个 `next_step`。
- 坏 JSON 生成 error event，不覆盖源文件。
- 缺文件时给出明确下一步。
- 失败步骤可以重跑。
- 旧 events 仍可读取，新 events 使用 canonical fields。

---
