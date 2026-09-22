# Deck Master Spec Pack

## 17. Spec 12：Export、Delivery Outcome 与 Feedback

### 17.1 目标

确保导出队列只包含人工批准且质量允许的页面，并记录最终交付结果。

### 17.2 `approved_queue.json` schema

```json
{
  "schema_version": "deck_approved_queue.v1",
  "run_id": "retail-conversation",
  "title": "Retail Digital Transformation Deck",
  "source_manifest": "runs/retail-conversation/preview_manifest.json",
  "export_policy": {
    "include_review_status": ["approved"],
    "block_p0_p1": true,
    "exclude_manual_placeholder": true,
    "allow_override": true
  },
  "pages": [
    {
      "page_id": "beat_004_architecture",
      "order": 4,
      "title": "库存可视化目标架构",
      "source_type": "library_slide",
      "source_decision": "adapt",
      "review_status": "approved",
      "preview_path": "links/beat_004_architecture.svg",
      "source_preview_asset": "",
      "source_pptx": "",
      "source_slide_index": 12,
      "narrative_role": "architecture",
      "notes": ""
    }
  ],
  "excluded_pages": [
    {
      "page_id": "beat_008_case",
      "reason": "manual_placeholder cannot enter final handback"
    }
  ],
  "created_at": "2026-06-11T00:00:00Z"
}
```

### 17.3 CLI

```bash
python3 scripts/deck_master.py export --run-id <run_id>
python3 scripts/deck_master.py export --run-id <run_id> --allow-quality-override
```

### 17.4 `delivery_outcome.json` schema

```json
{
  "schema_version": "deck_delivery_outcome.v1",
  "run_id": "retail-conversation",
  "delivered": true,
  "final_artifact": "exports/retail_solution_v1.pptx",
  "delivered_pages": ["beat_001", "beat_002"],
  "removed_pages": ["beat_008_case"],
  "pages_rewritten_after_export": [],
  "customer_reaction": {
    "status": "positive",
    "notes": "客户认可库存闭环主线。"
  },
  "business_signal": {
    "advanced_to_next_stage": true,
    "quote_requested": false,
    "sow_requested": true,
    "contract_signed": false
  },
  "claim_feedback": [
    {
      "claim_id": "claim_001",
      "outcome": "accepted",
      "notes": "客户认可，但要求补充数据。"
    }
  ],
  "created_at": "2026-06-11T00:00:00Z"
}
```

### 17.5 Feedback event schema

```json
{
  "schema_version": "deck_feedback_event.v1",
  "timestamp": "2026-06-11T00:00:00Z",
  "run_id": "retail-conversation",
  "beat_id": "beat_004_architecture",
  "decision": "adapt",
  "candidate_id": "slide_123",
  "outcome": "approved",
  "source": "review_cockpit"
}
```

### 17.6 Feedback 文件

```text
feedback/
  sourcing_outcomes.jsonl
  slide_outcomes.jsonl
  quality_outcomes.jsonl
  delivery_outcomes.jsonl
```

首版只要求写：

- approved。
- rejected。
- delivered。
- excluded_by_quality。

### 17.7 验收

- rejected 页面不进入 approved queue。
- P0/P1 页面不进入 export，除非 override。
- manual_placeholder 不作为 client-facing page。
- export 写 event。
- delivery outcome 可选填写，但 schema 固定。

---
