# P2：Solution Narrative Engine

主版本：[`../../deck-master-p2-p5-development-guide.md`](../../deck-master-p2-p5-development-guide.md)

P2 目标：让 Deck Master 形成专业方案主线，覆盖判断、论点、证据、页面职责和主线审查。

## 前置

- Sprint 0 全部完成。
- `next-step` 可解释当前 run 状态。
- `review_status/action_intent` 已进入 preview manifest。

## 任务

| 任务 | 名称 | 产物 |
|---|---|---|
| P2-A | Consulting Judgment Layer | `consulting_judgments.json` |
| P2-B | Claim-Evidence Graph | `claim_evidence_graph.json` |
| P2-C | Narrative Planner v2 与 Page Tasks | 增强 `narrative_plan.json`、`page_tasks.json` |
| P2-D | Draft Gate 2.0 | `quality_reports/draft_gate.json` |
| P2-E | Narrative Review Cockpit | 主线审查 UI |

## Claude Code 指令

```text
请阅读 docs/deck-master-p2-p5-development-guide.md 的第 4 节。
本次只执行 <P2 任务编号>。
严格遵守该任务允许修改范围和测试要求。
```

