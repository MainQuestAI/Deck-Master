# Deck Master Spec Pack

## 6. Spec 01：Workspace Foundation

### 6.1 目标

创建或注册一个 Deck Workspace，使其成为长期方案资产容器。

首版必须做到：Workspace 是能被 Planner、Quality Gate、Sourcing 和 Build Skill 读取的资产容器。

### 6.2 CLI

```bash
python3 scripts/deck_master.py init-workspace \
  --workspace /path/to/deck-workspace \
  --name "MarketingForce PPT Workshop" \
  --reference-ppt /path/to/reference.pptx
```

```bash
python3 scripts/deck_master.py register-workspace \
  --workspace /path/to/existing-workshop \
  --name "MarketingForce PPT Workshop"
```

```bash
python3 scripts/deck_master.py validate-workspace \
  --workspace /path/to/deck-workspace
```

### 6.3 `workspace_manifest.json` schema

```json
{
  "schema_version": "deck_workspace.v1",
  "workspace_id": "marketingforce-ppt-workshop",
  "name": "MarketingForce PPT Workshop",
  "description": "",
  "created_at": "2026-06-11T00:00:00Z",
  "updated_at": "2026-06-11T00:00:00Z",
  "version": 1,
  "paths": {
    "visual_system": "visual-system/",
    "structure_assets": "structure-assets/",
    "quality": "quality/",
    "sources": "sources/",
    "runs": "runs/",
    "exports": "exports/",
    "feedback": "feedback/"
  },
  "visual_system": {
    "design_spec": "visual-system/design_spec.md",
    "spec_lock": "visual-system/spec_lock.md",
    "layout_blueprint": "visual-system/layout_blueprint.md"
  },
  "structure_assets": {
    "page_archetypes": "structure-assets/page_archetypes.md"
  },
  "quality": {
    "policy": "quality/quality_policy.md",
    "scoring_rubric": "quality/scoring_rubric.md",
    "failure_modes": "quality/failure_modes.md",
    "repair_playbooks": "quality/repair_playbooks.md"
  },
  "references": [
    {
      "reference_id": "ref_001",
      "kind": "reference_ppt",
      "path": "/path/to/reference.pptx",
      "filename": "reference.pptx",
      "size_bytes": 123456,
      "modified_at": "2026-06-11T00:00:00Z",
      "note": "metadata only in v1"
    }
  ],
  "include_rules": [],
  "exclude_rules": ["exports/**", "runs/**", ".git/**"],
  "default_output": "exports/"
}
```

### 6.4 Starter 文件

`visual-system/design_spec.md` 必须包含：

- canvas size。
- safe area。
- font policy。
- color palette。
- component style。
- density guidance。
- screenshot policy。
- chart policy。
- pending_manual_review 字段。

`structure-assets/page_archetypes.md` 必须包含初始页型：

- cover
- agenda
- executive_summary
- problem
- business_context
- solution_overview
- architecture
- capability_matrix
- process_flow
- case_study
- roadmap
- roi
- risk_control
- closing

每个 archetype 至少包含：

```yaml
archetype_id: architecture
name: 目标架构页
best_for:
  - 系统建设方案
  - 数字化转型方案
page_role: architecture
required_modules:
  - 业务域
  - 能力层
  - 数据流
  - 集成关系
evidence_pattern:
  - 客户现状
  - 目标能力
  - 数据流或接口关系
visual_pattern: layered_architecture
density_target: high
avoid:
  - 只画平台层，不说明业务价值
example_refs: []
```

### 6.5 Planner 接入要求

Planner 必须读取 workspace：

- page archetypes。
- density standard。
- quality policy。
- visual constraints。

并写入 page task：

```json
{
  "planning": {
    "preferred_archetype": "architecture",
    "workspace_refs": ["structure-assets/page_archetypes.md#architecture"],
    "style_constraints": ["visual-system/spec_lock.md"],
    "quality_requirements": ["页面必须有主观点", "证据必须和主观点对应"]
  }
}
```

### 6.6 验收

- 新 workspace 可创建。
- 旧文件夹可注册。
- 缺少标准文件时 `validate-workspace` 输出 pending/manual review，不崩溃。
- 同一 brief 在有 workspace 时，`page_tasks.json` 写入 `workspace_refs`。
- 无 workspace 时使用默认 archetypes。

---
