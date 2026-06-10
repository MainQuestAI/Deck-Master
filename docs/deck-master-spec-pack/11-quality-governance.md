# Deck Master Spec Pack

## 16. Spec 11：Quality & Governance

### 16.1 目标

把质量控制作为 Deck Master 内建子系统，纳入主运行链路。

### 16.2 Gate 类型

| Gate | 触发点 | 首版策略 |
|---|---|---|
| Draft Gate | `narrative_plan.json` 与 `page_tasks.json` 存在后 | 默认硬链路 |
| Render Gate | HTML/SVG/PPTX 预览资产存在后 | 显式 artifact check |
| Delivery Gate | export queue 或最终 PPTX 存在后 | 显式 artifact check |
| Evidence Gate | Claim-Evidence Graph 完成后 | 阶段 2 |
| Brand Gate | 视觉系统稳定后 | 阶段 4 |
| Confidentiality Gate | 交付前 | 阶段 4 |

### 16.3 Quality report schema

```json
{
  "schema_version": "deck_quality_report.v1",
  "run_id": "retail-conversation",
  "gate": "draft",
  "status": "rework_required",
  "artifact": "",
  "scorecard": {
    "narrative_integrity": 4,
    "page_job_clarity": 2,
    "information_density": 3,
    "evidence_and_specificity": 2,
    "screenshot_and_asset_integration": 4,
    "layout_variety": 4,
    "consulting_style_expression": 4,
    "visual_readiness": 4,
    "delivery_readiness": 4
  },
  "score_summary": {
    "average": 3.44,
    "minimum": 2,
    "dimensions": 9
  },
  "summary": {
    "findings": 3,
    "page_findings": 2
  },
  "findings": [
    {
      "finding_id": "beat_004_evidence_gap",
      "severity": "P1",
      "dimension": "evidence_and_specificity",
      "message": "页面缺少支撑主张的客户证据。",
      "refs": ["page_tasks.json", "claim_evidence_graph.json"],
      "repair_instruction": "补充客户原话、截图、指标或历史案例。",
      "page_id": "beat_004_architecture",
      "risk_flags": ["evidence_gap"],
      "blocking_scope": "page"
    }
  ],
  "page_findings": [],
  "repair_plan": [],
  "blocks_delivery": true,
  "created_at": "2026-06-11T00:00:00Z"
}
```

### 16.4 Scorecard 维度

- Narrative Integrity。
- Page Job Clarity。
- Information Density。
- Evidence And Specificity。
- Screenshot And Asset Integration。
- Layout Variety。
- Consulting-Style Expression。
- Visual Readiness。
- Delivery Readiness。

### 16.5 Severity

| Severity | 含义 | 默认阻断 |
|---|---|---|
| P0 | 绝对交付阻断 | 是 |
| P1 | 客户可见前必须修复 | 是 |
| P2 | 应修复，可条件通过 | 否 |
| P3 | 建议优化 | 否 |

### 16.6 Draft Gate checks

- Deck 有清晰受众。
- Deck 有业务目标。
- 每页有页面职责。
- 每页有核心主张。
- 每页有 decision intent。
- Evidence-heavy 页面有 evidence policy。
- 缺客户事实写入 gaps。
- 页面顺序有叙事推进。
- 长 Deck 有章节交接。
- 页面密度匹配角色。
- claim/evidence 风险映射到页面。

### 16.7 Export 阻断规则

- 任意 P0/P1 finding 阻断 client-facing export。
- `rework_required` 阻断 client-facing export。
- `manual_placeholder` 页面不得进入最终交付页。
- override 必须显式记录。

### 16.8 Override schema

```json
{
  "schema_version": "deck_quality_override.v1",
  "override_id": "override_001",
  "run_id": "retail-conversation",
  "target": "beat_004_architecture",
  "finding_id": "beat_004_evidence_gap",
  "reason": "客户口头确认，下一版补截图。",
  "actor": "user",
  "created_at": "2026-06-11T00:00:00Z"
}
```

### 16.9 验收

- Draft Gate 可在没有 rendered artifact 时运行。
- Render/Delivery Gate 没有 artifact 时不自动运行。
- Web UI 展示 run-level 和 page-level quality。
- P0/P1 阻断 export。
- Markdown 报告可读。

---
