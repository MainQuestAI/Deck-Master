# Deck Master P2-P5 拆包入口

主版本：[`../deck-master-p2-p5-development-guide.md`](../deck-master-p2-p5-development-guide.md)

本目录只作为 Claude Code 分任务入口。所有范围、字段、阈值、验收标准以主文档为准。

## 执行顺序

1. `Sprint 0`：P1.1 Hardening，进入 P2 前必须完成。
2. `P2`：Solution Narrative Engine。
3. `P3`：Asset Intelligence。
4. `P4`：Quality & Delivery Governance。
5. `P5A`：Local Team Solution Deck Factory。
6. `P5B`：Connector Import Contract，只做离线导入契约。

## 文件索引

| 文件 | 用途 |
|---|---|
| [`agent-task-index.md`](agent-task-index.md) | Claude Code 下发任务索引 |
| [`phases/P2-solution-narrative-engine.md`](phases/P2-solution-narrative-engine.md) | P2 任务摘要 |
| [`phases/P3-asset-intelligence.md`](phases/P3-asset-intelligence.md) | P3 任务摘要 |
| [`phases/P4-quality-delivery-governance.md`](phases/P4-quality-delivery-governance.md) | P4 任务摘要 |
| [`phases/P5-team-enterprise-solution-deck-factory.md`](phases/P5-team-enterprise-solution-deck-factory.md) | P5A/P5B 任务摘要 |

## Claude Code 固定指令

```text
你正在开发 MainQuestAI/Deck-Master。
请先阅读 docs/deck-master-p2-p5-development-guide.md。
本次只执行 <任务编号>：<任务名称>。
严格遵守该任务的允许修改范围、产物、测试和验收标准。
```

