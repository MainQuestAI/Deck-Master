# P5：Team / Enterprise Solution Deck Factory

主版本：[`../../deck-master-p2-p5-development-guide.md`](../../deck-master-p2-p5-development-guide.md)

P5A 目标：在本地文件系统和 Git 语境下支持轻量团队协作。P5B 只定义离线连接器导入契约。

## 前置

- P4-E Override Governance 完成。
- Delivery validation 与 approval 状态可以被 export 读取。

## P5A 任务

| 任务 | 名称 | 产物 |
|---|---|---|
| P5A-A | Team Identity | `team/users.json`、`team/roles.json`、`team/audit_log.jsonl` |
| P5A-B | Opportunity Model | `opportunities/<opp_id>/opportunity.json` |
| P5A-C | Approval Flow | `team/approval_flows.json`、`team/approval_requests.jsonl` |
| P5A-D | Team Dashboards | `dashboards/*.json` |
| P5A-E | Solution Package | `packages/solution_packages/*.json` |

## P5B 任务

| 任务 | 名称 | 产物 |
|---|---|---|
| P5B | Connector Import Contract | `docs/schemas/connector_import.schema.json` |

## Claude Code 指令

```text
请阅读 docs/deck-master-p2-p5-development-guide.md 的第 7 节。
本次只执行 <P5 任务编号>。
P5B 只做离线导入契约，不接实时外部 API。
```

