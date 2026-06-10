# Deck Master Spec Pack

## 12. Spec 07：PPT Library 集成与 Asset Intelligence 起点

### 12.1 目标

从历史方案资产中检索候选页，并为每个 beat 提供可解释候选集合。

首版 Deck Master 不负责深度索引 PPT，但负责调用 PPT Library、解析结果、降级处理和保存候选。

### 12.2 CLI 调用

主调用：

```bash
ppt-lib select-slides \
  --plan <run>/narrative_plan.json \
  --brief <run>/request.json \
  --ranking business \
  --max-per-role 5 \
  --output <run>/library_results/selection.json
```

备用调用：

```bash
ppt-lib search "<reuse_query>" \
  --top-k 8 \
  --ranking business \
  --output json
```

### 12.3 `library_results/selection.json` schema

```json
{
  "schema_version": "deck_library_selection.v1",
  "run_id": "retail-conversation",
  "source": "ppt_library",
  "tool_status": "ok",
  "by_beat": {
    "beat_004_architecture": [
      {
        "candidate_id": "slide_123",
        "slide_id": "slide_123",
        "canonical_slide_id": "canonical_abc",
        "beat_id": "beat_004_architecture",
        "title": "历史页：库存目标架构",
        "text_summary": "...",
        "source_file": "/path/to/history.pptx",
        "page_number": 12,
        "screenshot_path": "/path/to/screenshot.png",
        "confidence": 0.82,
        "score": 0.82,
        "win_rate": 0.67,
        "reuse_count": 3,
        "narrative_role": "architecture",
        "page_role": "architecture",
        "archetype_id": "architecture",
        "evidence_tags": ["architecture", "system_flow"],
        "visual_tags": ["layered_architecture"],
        "risk_flags": []
      }
    ]
  }
}
```

### 12.4 失败行为

| 情况 | 行为 |
|---|---|
| CLI 缺失 | 写 warning event，使用 fixture 或空结果 |
| CLI 返回非 0 | real mode 抛错，auto mode fallback |
| JSON 错误 | 写 parse error，继续 generate/manual fallback |
| 无结果 | 写空列表，不跳过 beat |
| 截图缺失 | 保留候选，增加 `missing_screenshot` |
| embedding 不可用 | 写 dependency failure，继续 |

### 12.5 Asset Intelligence 后续字段

候选页后续应支持：

- `claim_supported`
- `evidence_type`
- `customer_context`
- `visual_pattern`
- `approval_history`
- `delivery_outcome`
- `last_used_at`
- `source_confidentiality`

### 12.6 验收

- 每个 beat 都有 by_beat key。
- 无结果也写空数组。
- fixture 可稳定生成候选。
- screenshot 缺失不导致中断。
- 解析字段写入 canonical candidate。

---
