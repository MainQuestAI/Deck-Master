# Deck Master Spec Pack

## 13. Spec 08：Sourcing Decision Engine

### 13.1 目标

为每个页面选择唯一主来源策略：`reuse`、`adapt`、`generate`、`manual_placeholder`。

### 13.2 输入

- `narrative_plan.json`
- `page_tasks.json`
- `library_results/selection.json`
- `claim_evidence_graph.json`
- Workspace visual and quality standards

### 13.3 输出 `sourcing_plan.json`

```json
{
  "schema_version": "deck_sourcing_plan.v1",
  "run_id": "retail-conversation",
  "title": "Retail Digital Transformation Deck",
  "source": "ppt_library",
  "decisions": [
    {
      "beat_id": "beat_004_architecture",
      "order": 4,
      "page_title": "库存可视化目标架构",
      "role": "architecture",
      "decision": "adapt",
      "source_decision": "adapt",
      "decision_reason": "历史页结构匹配架构表达，但客户语境和证据需调整。",
      "selected_candidate": {},
      "alternatives": [],
      "score": 0.66,
      "score_breakdown": {
        "semantic_match": 0.72,
        "narrative_role_match": 0.80,
        "archetype_match": 0.74,
        "screenshot_availability": 1.0,
        "source_credibility": 0.6,
        "win_rate": 0.67,
        "reuse_count": 0.6,
        "customer_context_conflict": 0.2,
        "visual_continuity": 0.5,
        "evidence_sufficiency": 0.4
      },
      "risk_flags": ["needs_customer_context_rewrite"],
      "confidence": 0.66,
      "tool_refs": {
        "library_results": "library_results/by_beat/beat_004_architecture.json"
      }
    }
  ]
}
```

### 13.4 决策类型

| 决策 | 定义 |
|---|---|
| `reuse` | 历史页高匹配，可直接进入审批 |
| `adapt` | 历史页结构或素材可复用，但需调整客户语境、标题、论据或视觉 |
| `generate` | 历史候选不足，且无必需证据缺口，可新生成 |
| `manual_placeholder` | 缺必需客户事实、截图、数据、案例或证据，必须人工补充 |

### 13.5 初始权重

| 维度 | 权重 |
|---|---:|
| semantic_match | 0.30 |
| narrative_role_match | 0.18 |
| archetype_match | 0.10 |
| screenshot_availability | 0.10 |
| source_credibility | 0.08 |
| win_rate | 0.10 |
| reuse_count | 0.04 |
| customer_context_conflict | -0.12 |
| visual_continuity | 0.06 |
| evidence_sufficiency | 0.06 |

### 13.6 初始阈值

| 决策 | 条件 |
|---|---|
| `reuse` | score >= 0.78，截图可用，无高客户语境冲突 |
| `adapt` | score >= 0.58，且 archetype_match 或 narrative_role_match >= 0.70 |
| `generate` | score < 0.58，且没有必需证据缺口 |
| `manual_placeholder` | 缺必需客户事实、截图、数据或案例证据 |

### 13.7 tie-break

- 分差小于 0.05 时优先 narrative_role_match。
- 分差小于 0.05 时 win_rate 高者优先。
- 分差小于 0.08 时有 screenshot 者优先。
- 存在高客户语境冲突时，`reuse` 降级为 `adapt`。

### 13.8 写回 page_tasks

Sourcing 完成后必须同步写入 page_tasks 中的 `sourcing` 分层：

```json
{
  "sourcing": {
    "decision": "adapt",
    "selected_candidate": {},
    "alternatives": [],
    "score_breakdown": {},
    "risk_flags": [],
    "confidence": 0.66
  }
}
```

### 13.9 验收

- 每页唯一主决策。
- 每个决策都有 reason。
- 手工证据缺口不允许变成 generate。
- 高匹配但缺截图不得直接 reuse。
- Context conflict 会 downgrade。
- 同一输入 deterministic。

---
