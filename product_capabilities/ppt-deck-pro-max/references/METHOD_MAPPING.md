# ppt-deck-pro-max 方法/代码/参考资料映射（SC-1 修订五）

| 类别 | 资产 | 位置 | 用途 |
|---|---|---|---|
| 代码 | 高密度 Builder | `scripts/high_density/`（Deck Master 内置实现） | 唯一保留的高密度呈现路径（D05） |
| 契约 | generation result v1/v2 | `docs/contracts/generation-result.v2.schema.json` | handback 强制 v2；v1 仅旧读取 |
| 方法 | 高密度内容方法（已提取公共） | `skills/deck-master/references/methods/storyline-and-pages.md`、`solution-design.md` | 公共 narrative，MBB 为兼容投影 |

退役约束（SC-1 A1）：`DECK_MASTER_PPT_DECK_PRO_MAX_BRIDGE` 第三方分支 SHA 桥接已退役
（`generation_bridge_status()` 返回 retired）；生产生成只走 Agent 派发任务协议，不依赖该
仓库分支存在。
