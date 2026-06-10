# Deck Master Spec Pack

## 9. Spec 04：Deck Brief 与 Consulting Judgment Layer

### 9.1 目标

把上下文和引导式对话整理为稳定的 Deck 目标、受众、业务目标、核心观点和边界，并把关键专业判断结构化。

### 9.2 CLI

```bash
python3 scripts/deck_master.py build-brief --run-id <run_id>
python3 scripts/deck_master.py build-judgments --run-id <run_id>
```

### 9.3 `deck_brief.json` schema

```json
{
  "schema_version": "deck_brief.v1",
  "run_id": "retail-conversation",
  "project_name": "Retail Digital Transformation Deck",
  "audience": "client",
  "industry": "retail",
  "business_goal": "让客户认可全渠道库存可视化和履约闭环建设的必要性。",
  "decision_goal": "推动客户同意进入方案深化和 PoC 评估。",
  "core_points": [
    "库存可视化直接服务履约效率和客户体验，避免被理解为报表项目。"
  ],
  "must_cover_topics": ["全渠道", "库存可视化", "最后一公里配送"],
  "source_refs": ["source_001"],
  "style_preference": "consulting-style, evidence-backed",
  "target_pages": "auto",
  "boundaries": [
    "输出第一版可审查客户方案 Deck 草案。",
    "优先做论点、论证、论据和证据链。",
    "上下文只做运行时引用。"
  ],
  "language": "zh-CN"
}
```

### 9.4 `consulting_judgments.json` schema

```json
{
  "schema_version": "deck_consulting_judgments.v1",
  "run_id": "retail-conversation",
  "judgments": [
    {
      "judgment_id": "judgment_001",
      "judgment": "客户当前的核心问题是跨渠道履约状态闭环薄弱，库存看板只是表层呈现。",
      "why_it_matters": "这决定方案主线应从业务履约效率切入，避免从单点报表能力切入。",
      "supporting_evidence": ["source_001#quote_003"],
      "confidence": 0.72,
      "assumptions": ["客户愿意开放门店、仓、渠道订单数据"],
      "risks": ["缺少当前库存准确率数据"],
      "deck_implication": "前 5 页优先建立业务闭环和现状痛点，再讲系统能力。"
    }
  ]
}
```

### 9.5 实现要求

- `deck_brief` 只能写相对稳定的 Deck 级目标。
- 临时判断、假设、推断写入 `consulting_judgments`，不得混在 brief 文本中。
- 每个 judgment 必须有 `deck_implication`，否则不能被 Planner 使用。

### 9.6 验收

- brief 中必须有 business_goal。
- 至少能从 context summary 或用户 brief 中生成 core_points。
- judgment 缺证据时写 risk，不得伪造 evidence。
- Planner 能读取 judgment 影响章节或页面策略。

---
