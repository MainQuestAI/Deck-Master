# Deck Master Spec Pack

## 15. Spec 10：Preview Manifest 与 Review Cockpit API

### 15.1 目标

形成 Web UI 可读取、可审查、可回写的页面状态源。

### 15.2 Preview manifest schema

```json
{
  "schema_version": "deck_preview_manifest.v1",
  "run_id": "retail-conversation",
  "title": "Retail Digital Transformation Deck",
  "status": "draft",
  "updated_at": "2026-06-11T00:00:00Z",
  "pages": [
    {
      "page_id": "beat_004_architecture",
      "beat_id": "beat_004_architecture",
      "order": 4,
      "title": "库存可视化目标架构",
      "source_type": "library_slide",
      "source_decision": "adapt",
      "preview_path": "links/beat_004_architecture.svg",
      "source_preview_asset": "/abs/path/to/original.svg",
      "narrative_role": "architecture",
      "core_claim": "...",
      "decision_intent": "...",
      "decision_reason": "...",
      "confidence": 0.66,
      "selected_candidate": {},
      "alternatives": [],
      "risk_flags": [],
      "quality_status": "conditional_pass",
      "quality_findings": [],
      "generation_task": {},
      "review_status": "needs_review",
      "review_note": "",
      "action_intent": "none",
      "locked": false,
      "reviewed_at": ""
    }
  ]
}
```

### 15.3 兼容规则

旧字段：

```json
"decision": "needs_review"
```

应迁移为：

```json
"review_status": "needs_review"
```

旧值兼容：

| 旧 decision | 新 review_status | 新 action_intent |
|---|---|---|
| `needs_review` | `needs_review` | `none` |
| `approved` | `approved` | `none` |
| `keep` | `approved` | `none` |
| `replace` | `needs_review` | `replace_source` |

### 15.4 Review API

首版 API：

```http
GET /api/runs
POST /api/runs
GET /api/deck?run_id=<run_id>
GET /api/page/<page_id>?run_id=<run_id>
POST /api/page/<page_id>/review?run_id=<run_id>
POST /api/page/<page_id>/replace-source?run_id=<run_id>
POST /api/page/<page_id>/convert-to-generate?run_id=<run_id>
POST /api/page/<page_id>/lock-source?run_id=<run_id>
GET /api/quality?run_id=<run_id>
POST /api/export?run_id=<run_id>
```

### 15.5 Review request

```json
{
  "review_status": "approved",
  "review_note": "这页结构可用，后续补客户截图。"
}
```

### 15.6 Replace source request

```json
{
  "candidate_id": "slide_456",
  "reason": "候选页更贴近客户行业。"
}
```

### 15.7 Convert to generate request

```json
{
  "reason": "历史页语境不适合，改为新生成。",
  "generation_brief_patch": "强调门店、仓、渠道三类库存状态。"
}
```

### 15.8 Lock source request

```json
{
  "locked": true,
  "reason": "用户明确要求使用该历史页结构。"
}
```

### 15.9 验收

- 页面列表按 order 排序。
- 每页显示 source decision、quality findings、risk flags、generation status。
- 审批、拒绝、备注写回 manifest。
- 替换来源、转生成、锁定历史页写 event。
- 页面操作不能绕过 Draft Gate 阻断。

---
