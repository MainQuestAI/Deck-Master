# Deck Master Spec Pack

## 11. Spec 06：Solution Narrative Engine 与 Page Tasks

### 11.1 目标

生成 Deck 级叙事结构和页面级任务，使每页都有明确页面职责、核心主张、证据需求、视觉意图、页型和客户决策推进作用。

### 11.2 CLI

```bash
python3 scripts/deck_master.py plan --run-id <run_id>
python3 scripts/deck_master.py build-page-tasks --run-id <run_id>
```

`autoplan` 内部必须调用同一 planner pipeline，不得另写逻辑。

### 11.3 `narrative_plan.json` schema

```json
{
  "schema_version": "deck_narrative_plan.v1",
  "run_id": "retail-conversation",
  "title": "Retail Digital Transformation Deck",
  "target_pages": 15,
  "density": "medium_high",
  "industry": "retail",
  "audience": "client",
  "deck_strategy": {
    "core_thesis": "库存可视化应服务全渠道履约闭环。",
    "decision_goal": "推动客户进入方案深化。",
    "section_strategy": [
      {
        "section_id": "section_01",
        "title": "为什么现在需要升级",
        "role": "context_and_problem",
        "page_range": [1, 4]
      }
    ]
  },
  "beats": [
    {
      "beat_id": "beat_004_architecture",
      "order": 4,
      "section_id": "section_02",
      "page_title": "库存可视化目标架构",
      "role": "architecture",
      "core_claim": "库存可视化需要打通门店、仓、渠道和配送履约状态。",
      "content_goal": "说明目标架构和关键数据流。",
      "decision_intent": "让客户认可这是履约闭环项目，避免被理解为单点看板项目。",
      "argument_chain": {
        "why_now": "客户全渠道订单和履约方式复杂度上升。",
        "business_tension": "门店、仓、渠道、配送状态割裂。",
        "solution_logic": "通过统一库存状态和履约状态建模实现可视化和决策闭环。",
        "proof_needed": "客户现有链路、库存状态样例、履约指标。"
      },
      "evidence_need": ["系统截图", "库存状态样例", "履约指标"],
      "evidence_policy": {
        "required": true,
        "evidence_types": ["client_document", "product_screenshot", "metric"],
        "allow_ai_generated_without_evidence": false
      },
      "visual_need": "分层架构图",
      "density": "high",
      "preferred_archetype": "architecture",
      "customer_specificity_level": "customer_specific",
      "reuse_query": "retail inventory visibility architecture omnichannel fulfillment",
      "generation_brief": "生成一页库存可视化目标架构页...",
      "approval_required": true,
      "gaps": []
    }
  ]
}
```

### 11.4 `page_tasks.json` schema

```json
{
  "schema_version": "deck_page_tasks.v1",
  "run_id": "retail-conversation",
  "title": "Retail Digital Transformation Deck",
  "tasks": [
    {
      "beat_id": "beat_004_architecture",
      "order": 4,
      "planning": {
        "page_title": "库存可视化目标架构",
        "role": "architecture",
        "core_claim": "库存可视化需要打通门店、仓、渠道和配送履约状态。",
        "decision_intent": "让客户认可这是履约闭环项目。",
        "content_goal": "说明目标架构和关键数据流。",
        "argument_chain": {},
        "evidence_need": ["系统截图", "库存状态样例", "履约指标"],
        "evidence_policy": {},
        "visual_need": "分层架构图",
        "density": "high",
        "preferred_archetype": "architecture",
        "customer_specificity_level": "customer_specific",
        "workspace_refs": ["structure-assets/page_archetypes.md#architecture"],
        "style_constraints": ["visual-system/spec_lock.md"],
        "quality_requirements": ["必须有主观点", "必须说明数据如何服务决策"],
        "gaps": []
      },
      "retrieval": {
        "reuse_query": "retail inventory visibility architecture omnichannel fulfillment",
        "constraints": ["avoid generic platform overview"]
      },
      "sourcing": {
        "decision": null,
        "selected_candidate": null,
        "alternatives": [],
        "score_breakdown": null,
        "risk_flags": [],
        "confidence": null
      },
      "generation": {
        "generation_brief": "生成一页库存可视化目标架构页...",
        "reference_slide": null,
        "task_path": null,
        "status": "pending"
      },
      "review": {
        "review_status": "needs_review",
        "review_note": "",
        "action_intent": "none",
        "locked": false
      },
      "quality": {
        "status": "not_run",
        "findings": []
      }
    }
  ]
}
```

### 11.5 页数策略

| target_pages | 策略 |
|---|---|
| `auto` | 12–18 页 |
| `15` | 高管摘要和紧凑方案 |
| `30` | 完整 Solution Deck |
| `60+` | 章节化长 deck，强化 section handoff |

### 11.6 页面角色

首版至少支持：

- cover
- agenda
- executive_summary
- business_context
- problem
- insight
- solution_overview
- architecture
- capability_matrix
- process_flow
- case_study
- roadmap
- roi
- risk_control
- closing
- appendix

### 11.7 验收

- 每页必须有 `core_claim`。
- 每页必须有 `decision_intent`。
- Evidence-heavy 页面必须有 `evidence_policy.required = true`。
- 缺客户事实必须写入 `gaps`。
- 长 Deck 必须有 section handoff。
- page_tasks 必须分层，不得写回平铺 sourcing 字段。

---
