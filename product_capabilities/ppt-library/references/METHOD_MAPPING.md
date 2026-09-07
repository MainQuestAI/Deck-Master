# ppt-library 方法/代码/参考资料映射（SC-1 A3）

| 类别 | 资产 | 位置 | 用途 |
|---|---|---|---|
| 代码 | 检索客户端 | `scripts/tools/ppt_library_client.py` | selection v2、strict 生产门禁、托管命令解析 |
| 状态 | 库状态检查器 | `scripts/runtime/library_status.py` | CLI/状态缺失即 blocked；来源 managed/path 分档 |
| 方法 | 历史资产复用判断 | `skills/deck-master/references/methods/brief-and-research.md`（来源优先级节） | 检索命中后的适用性/来源判断 |
| 契约 | sourcing plan | `docs/contracts/sourcing-plan.v2.schema.json` | none/real 决策统一落盘 |

托管约束（SC-1 A3）：CLI 由 `deck-master backend install-managed ppt-library --source <dir>`
装入 `~/.deck-master/backends/ppt-library/<sha>/`；asset database 与 release 分离，旧库
不重建不删除；`library_mode=none` 是一等生产路径，不调用 Library、不做 fixture selection。
