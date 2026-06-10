# Deck Master Spec Pack

## 8. Spec 03：Context Intelligence 与 Guided Conversation

### 8.1 目标

把本地或已导出的客户上下文变成可追踪、可引用、可摘要的 run 输入。

首版只接 text-like 文件：`.md`、`.txt`、`.json`、`.csv`、`.tsv`。

### 8.2 CLI

```bash
python3 scripts/deck_master.py start-conversation \
  --workspace /path/to/deck-workspace \
  --context-file examples/context/retail_meeting_transcript.txt \
  --context-file examples/context/client_material_summary.md \
  --industry retail \
  --run-id retail-conversation
```

### 8.3 `context_manifest.json` schema

```json
{
  "schema_version": "deck_context_manifest.v1",
  "run_id": "retail-conversation",
  "workspace": "/path/to/deck-workspace",
  "strategy": "runtime_reference",
  "sources": [
    {
      "source_id": "a1b2c3d4e5f6g7h8",
      "path": "/abs/path/to/transcript.txt",
      "name": "transcript.txt",
      "kind": "meeting_transcript",
      "mime_type": "text/plain",
      "size_bytes": 12345,
      "sha256": "...",
      "summary": "...",
      "excerpt": "...",
      "created_at": "",
      "modified_at": ""
    }
  ],
  "summary": "combined summary",
  "constraints": [
    "Deck Master references local/exported context only.",
    "No realtime Feishu pull or long-term note storage is performed."
  ]
}
```

### 8.4 source kind

必须支持：

- `meeting_transcript`
- `client_material`
- `historical_solution`
- `product_material`
- `knowledge_export`
- `user_judgment`
- `local_document`

### 8.5 `conversation_session.json` schema

```json
{
  "schema_version": "deck_conversation_session.v1",
  "run_id": "retail-conversation",
  "mode": "guided_deck_conversation",
  "status": "draft",
  "context_refs": ["source_001"],
  "locked_decisions": {
    "audience": "client",
    "industry": "retail",
    "business_goal": "...",
    "context_strategy": "runtime_reference",
    "first_output": "reviewable_deck_draft"
  },
  "questions": [
    {
      "question_id": "audience_goal",
      "prompt": "这份 Deck 面向谁？他们看完后需要做什么决定？",
      "purpose": "锁定受众、决策场景和表达深度。"
    }
  ],
  "answers": [],
  "notes": []
}
```

### 8.6 首版引导问题

至少包含：

1. 这份 Deck 面向谁？他们看完后需要做什么决定？
2. 如果只能让对方记住一个判断，这个判断是什么？
3. 哪些案例、截图、数据或客户原话可以证明这个判断？
4. 哪些历史方案页、业务模型或框架值得复用？
5. 哪些内容应该删掉或放进附录？

### 8.7 验收

- 多个 context file 可生成 manifest。
- source_id 基于内容 hash 稳定生成。
- 不支持文件类型必须明确报错。
- conversation session 记录 context refs。
- 不写入长期知识库。

---
