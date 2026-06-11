# P4：Quality & Delivery Governance

主版本：[`../../deck-master-p2-p5-development-guide.md`](../../deck-master-p2-p5-development-guide.md)

P4 目标：把质量门禁接入最终交付链路，确保高风险页面不会静默进入客户交付。

## 前置

- S0-E Export Quality Blocking 完成。
- P2-D Draft Gate 2.0 完成。
- P3-E Sourcing Scoring v2 完成。

## 任务

| 任务 | 名称 | 产物 |
|---|---|---|
| P4-A | Evidence Gate | `quality_reports/evidence_gate.json` |
| P4-B | Context Conflict Gate | `quality_reports/context_conflict_gate.json` |
| P4-C | Confidentiality Gate | `quality_reports/confidentiality_gate.json` |
| P4-D | Brand Gate 轻量版 | `quality_reports/brand_gate.json` |
| P4-E | Override Governance | `overrides/override_records.jsonl` |
| P4-F | Delivery Validation 与 Outcome | `delivery/final_version_lineage.json`、`delivery/delivery_outcome.json` |
| P4-G | Quality Governance UI | 质量治理审查面板 |

## Claude Code 指令

```text
请阅读 docs/deck-master-p2-p5-development-guide.md 的第 6 节。
本次只执行 <P4 任务编号>。
必须遵守 P0/P1 阻断和 override 政策。
```

