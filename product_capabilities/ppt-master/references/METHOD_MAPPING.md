# ppt-master 方法/代码/参考资料映射（SC-1 A1）

| 类别 | 资产 | 位置 | 用途 |
|---|---|---|---|
| 代码 | 标准 build/render 运行时 | `scripts/runtime/build.py`、`scripts/runtime/render.py`（Deck Master 侧） | 消费 Page Package/preview，产出 render_request，回收 deck_render_result.v2 |
| 契约 | render request/result、backend manifest | `docs/contracts/render-request.v1.schema.json`、`render-result.v2.schema.json` | 生产输出唯一契约 |
| 方法 | 架构视图方法（标准构建消费） | `skills/deck-master/references/methods/architecture-views.md` | 图形表达的业务/应用/数据一致性 |
| 参考 | capability 包 | `product_capabilities/ppt-master/`（release 树 `capabilities/ppt-master/`） | 版本、操作、状态策略 |

托管约束（SC-1 A2）：后端包由 `deck-master backend install-managed ppt-master --source <dir>`
装入 `~/.deck-master/backends/ppt-master/<sha>/`；`current` 指针解析运行路径；runtime_ready
只由真实 smoke 证据驱动；`DECK_MASTER_PPT_DECK_PRO_MAX_BRIDGE` 桥接已退役。
