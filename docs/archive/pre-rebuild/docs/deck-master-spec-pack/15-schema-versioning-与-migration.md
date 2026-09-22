# Deck Master Spec Pack

## 20. Spec 15：Schema Versioning 与 Migration

### 20.1 目标

所有重要 artifact 必须有 `schema_version`，支持后续迁移。

### 20.2 版本命名

```text
deck_workspace.v1
deck_request.v1
deck_event.v1
deck_context_manifest.v1
deck_conversation_session.v1
deck_brief.v1
deck_claim_map.v1
deck_claim_evidence_graph.v1
deck_narrative_plan.v1
deck_page_tasks.v1
deck_sourcing_plan.v1
deck_generation_task.v1
deck_preview_manifest.v1
deck_quality_report.v1
deck_approved_queue.v1
deck_delivery_outcome.v1
```

### 20.3 Migration module

```text
scripts/runtime/migrations.py
```

必须支持：

- preview manifest 旧 decision 字段迁移。
- sourcing decision `source_decision` / `decision` 双写兼容。
- events 旧 action/status 模型升级。
- page_tasks 缺少 review/quality 分层时补默认值。

### 20.4 验收

- 旧 run 可被 `validate-run` 检测并给出 migration suggestion。
- 迁移写备份：`<file>.bak.<timestamp>`。
- migration 写 event。
- 不自动破坏用户审批状态。

---
