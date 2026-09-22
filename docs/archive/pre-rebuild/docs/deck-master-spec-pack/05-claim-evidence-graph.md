# Deck Master Spec Pack

## 10. Spec 05：Claim-Evidence Graph

### 10.1 目标

将 `claim_map.json` 升级为可持续演进的 Claim-Evidence Graph，使每页都能回答“证明哪个主张、使用哪些证据、缺什么证据”。

首版可以同时生成：

- `claim_map.json`：兼容当前代码。
- `claim_evidence_graph.json`：新增终局模型。

### 10.2 CLI

```bash
python3 scripts/deck_master.py build-claim-map --run-id <run_id>
python3 scripts/deck_master.py build-claim-graph --run-id <run_id>
```

### 10.3 `claim_map.json` schema

```json
{
  "schema_version": "deck_claim_map.v1",
  "run_id": "retail-conversation",
  "title": "Retail Digital Transformation Deck",
  "claims": [
    {
      "claim_id": "claim_001",
      "claim": "库存可视化需要打通门店、仓、渠道和配送履约状态。",
      "why_it_matters": "该判断支撑客户从单点库存看板升级到履约闭环。",
      "supporting_arguments": [
        "库存状态分散导致用户承诺不稳定。",
        "履约状态缺失会影响到店、自提、配送体验。"
      ],
      "evidence_needed": ["客户现有库存链路", "系统截图", "履约指标"],
      "evidence_refs": ["evidence_001"],
      "risk_flags": []
    }
  ],
  "source_refs": ["source_001"],
  "risk_flags": []
}
```

### 10.4 `claim_evidence_graph.json` schema

```json
{
  "schema_version": "deck_claim_evidence_graph.v1",
  "run_id": "retail-conversation",
  "claims": [],
  "evidence": [
    {
      "evidence_id": "evidence_001",
      "kind": "meeting_quote",
      "summary": "客户提到门店库存和线上库存不一致。",
      "source_ref": "source_001",
      "quote": "",
      "confidence": 0.8,
      "client_visible": true,
      "risk_flags": []
    }
  ],
  "assumptions": [
    {
      "assumption_id": "assumption_001",
      "text": "客户具备门店库存数据导出能力。",
      "needs_confirmation": true,
      "risk_flags": ["needs_client_confirmation"]
    }
  ],
  "risks": [
    {
      "risk_id": "risk_001",
      "severity": "P2",
      "kind": "evidence_gap",
      "message": "缺少当前库存准确率数据。",
      "refs": ["claim_001"]
    }
  ],
  "page_claim_links": [],
  "evidence_page_links": [],
  "source_refs": []
}
```

### 10.5 Evidence kinds

必须支持：

- `meeting_quote`
- `client_document`
- `product_screenshot`
- `case_study`
- `metric`
- `historical_slide`
- `external_reference`
- `user_judgment`
- `ai_inference`

`ai_inference` 不得默认 client-visible。

### 10.6 风险规则

如果 claim 没有 evidence：

- 写 `evidence_gap`。
- Draft Gate 至少输出 P1 或 P2 finding，取决于页面重要性。

如果 evidence 来自 AI 推断：

- 写 `needs_confirmation`。
- 不得作为强证据支撑最终交付。

### 10.7 验收

- 每个 core point 至少生成一个 claim。
- 每个 claim 有 evidence_needed。
- context 中识别出的证据成为 evidence object。
- page_tasks 生成后补 page_claim_links。
- Draft Gate 能引用 claim/evidence 风险。

---
