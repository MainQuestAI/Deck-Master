# P3：Asset Intelligence

主版本：[`../../deck-master-p2-p5-development-guide.md`](../../deck-master-p2-p5-development-guide.md)

P3 目标：让历史方案页在 workspace 层形成资产网络，并影响 sourcing 决策。

## 前置

- P2-D 至少完成。
- Asset 写入必须使用 workspace-relative path 或 source fingerprint。
- Sourcing scoring 必须按主文档权重和阈值实现。

## 任务

| 任务 | 名称 | 产物 |
|---|---|---|
| P3-A | Asset Schema 与 Canonical ID | `assets/asset_graph.json`、`assets/slide_assets/*.json` |
| P3-B | Library Result Ingestion | `asset_refs.json` |
| P3-C | Feedback Collector | `assets/asset_feedback.jsonl` |
| P3-D | Asset Health 与 Archetype Tagging | `assets/asset_health_report.json` |
| P3-E | Sourcing Scoring v2 | 增强 `sourcing_plan.json` |
| P3-F | Asset Signals UI | 候选页信号展示 |

## Claude Code 指令

```text
请阅读 docs/deck-master-p2-p5-development-guide.md 的第 5 节。
本次只执行 <P3 任务编号>。
必须保留相同输入的稳定 sourcing decision。
```

