# Deck Master Spec Pack

## 14. Spec 09：Build Skill Runtime

### 14.1 目标

将 `adapt` 和 `generate` 页面任务交给生成能力，并把 artifact 状态回写 run。

首版可以支持 fake executor，但 contract 必须真实。

### 14.2 Registry

Workspace 默认配置：

```json
{
  "schema_version": "deck_build_skill_registry.v1",
  "default_skill": "ppt_deck_pro_max",
  "skills": [
    {
      "skill_id": "ppt_deck_pro_max",
      "name": "PPT Deck Pro Max",
      "kind": "slide_builder",
      "command": "ppt-deck-pro-max",
      "enabled": true,
      "supports": ["adapt", "generate"],
      "artifact_types": ["pptx", "svg", "html", "png"]
    }
  ]
}
```

### 14.3 Generation task schema

```json
{
  "schema_version": "deck_generation_task.v1",
  "task_id": "generation_004_beat_004_architecture",
  "beat_id": "beat_004_architecture",
  "page_title": "库存可视化目标架构",
  "role": "architecture",
  "core_claim": "...",
  "decision_intent": "...",
  "source_decision": "adapt",
  "generation_brief": "...",
  "reference_slide": {},
  "preferred_archetype": "architecture",
  "visual_need": "分层架构图",
  "evidence_need": ["系统截图"],
  "style_constraints": ["visual-system/spec_lock.md"],
  "workspace_refs": ["structure-assets/page_archetypes.md#architecture"],
  "quality_requirements": [],
  "status": "pending",
  "created_at": "2026-06-11T00:00:00Z",
  "updated_at": "2026-06-11T00:00:00Z"
}
```

### 14.4 Artifact handback schema

```json
{
  "schema_version": "deck_build_artifact.v1",
  "task_id": "generation_004_beat_004_architecture",
  "beat_id": "beat_004_architecture",
  "artifact_type": "svg",
  "artifact_path": "build_artifacts/beat_004/page.svg",
  "preview_path": "build_artifacts/beat_004/page.svg",
  "source_decision": "adapt",
  "build_tool": "ppt_deck_pro_max",
  "status": "completed",
  "created_at": "2026-06-11T00:00:00Z",
  "errors": []
}
```

### 14.5 CLI

```bash
python3 scripts/deck_master.py create-generation-tasks --run-id <run_id>
python3 scripts/deck_master.py run-build-skill --run-id <run_id> --task-id <task_id>
python3 scripts/deck_master.py ingest-build-artifact --run-id <run_id> --artifact /path/to/artifact.json
```

### 14.6 状态值

- `pending`
- `running`
- `completed`
- `failed`
- `skipped`
- `cancelled`

### 14.7 失败规则

- 单页失败不得中断其他页面 preview。
- 失败必须写 event。
- preview_manifest 中对应页显示 failed 状态。
- failed 页不得进入最终 export，除非手工 override。

### 14.8 验收

- `adapt` 和 `generate` 页面生成 task。
- `reuse` 页面不生成 task。
- `manual_placeholder` 页面生成内部提醒，不生成 client-facing artifact。
- fake executor 可生成 placeholder artifact。
- artifact handback 可刷新 preview manifest。

---
