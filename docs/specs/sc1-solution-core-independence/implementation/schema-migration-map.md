# SC-1 Q0｜Schema 迁移映射（schema-migration-map）

## 1. 现状盘点（基线 bcb5b37 实测）

| 位置 | 内容 | 状态 |
|---|---|---|
| `docs/contracts/`（58 个 schema） | 运行时权威契约。含 `generation-result.v1` 与 `generation-result.v2`（v2 于 commit `979adec` 已入库） | 权威层 |
| `skills/deck-master/schemas/`（7 个） | 随 skill 分发的任务/结果 schema。`generation_result.schema.json` **仍为 v1**（`$id: deck_generation_result.v1`） | 滞后层 |
| `product_capabilities/*/contracts/`（4 包） | ppt-* 能力包自带契约；`ppt-deck-pro-max` 含 generation-result.v1 | 能力包层 |
| 本包 `contracts/`（7 个目标 schema） | SC-1 目标契约草案，未安装 | 目标层 |
| `docs/deck-master-real-production-closure-spec-pack/schemas/deck_generation_result.v2.schema.json` | 历史迭代包内副本 | 历史层，不引用 |

## 2. 版本冻结对照表（Q0 冻结）

| 对象 | 运行时当前强制版本 | 权威 schema | 分发侧 schema | 差异/动作 |
|---|---|---|---|---|
| generation result | `deck_generation_result.v2`（`scripts/generation/handback.py:32`；旧版仅接受 legacy/ppt-deck-pro-max v1 改写，handback.py:317） | `docs/contracts/generation-result.v2.schema.json` | `skills/deck-master/schemas/generation_result.schema.json`=v1 | A1：skill 侧升级 v2（保留 v1 语义读取路径），消除四处散布 |
| render result | `deck_render_result.v2`（`scripts/runtime/build.py:22`） | `docs/contracts/render-result.v2.schema.json` | — | 无动作，登记 |
| render request | `deck_render_request.v1`（`runtime/render_handoff.py:14`） | `docs/contracts/render-request.v1.schema.json` | — | A2 托管化时核对 tool 字段来源（F07） |
| sourcing plan | `deck_sourcing_plan.v2`（`runtime/rc_gate.py:621-632`） | `docs/contracts/sourcing-plan.v2.schema.json` | — | 无动作 |
| library status / selection | v2（`runtime/rc_gate.py:569,647`） | docs/contracts | — | 无动作 |
| setup status | `deck_master_setup_status.v2`（`runtime/rc_gate.py:267`） | docs/contracts | — | A4 扩展时递增 |
| workflow state / approval | v1（docs/contracts） | 同左 | — | D08：不建第二状态机；新对象走扩展字段（`EXTENSION_DELTAS.md`） |
| content lock | v2 要求 `page_package_ref`+`page_package_sha256`+`lineage` | docs/contracts/content-lock.v2.schema.json | — | B5/B6 复用 |
| **悬空引用** | `skills/deck-master/playbooks/ppt-library-handoff.md:24` 引用 `schemas/ppt_library_candidate.schema.json` —— **全仓库不存在** | — | — | A1：改为引用真实 schema 或内联字段说明 |
| **本包目标对象** | solution-model v1、context-pack v2、research-task v1、capability-execution-plan v1、diagram-view v1、external-quality-review v2、narrative-plan v3 | 本包 `contracts/` | 未分发 | PR-02 起按任务卡安装进 `docs/contracts/` + `skills/deck-master/schemas/` |

## 3. 旧读写差异（升级时的兼容边界）

1. **generation result v1→v2**：handback 接受 `LEGACY_RESULT_SCHEMA_VERSION` 与 `DECK_PRO_MAX_RESULT_SCHEMA_VERSION`（handback.py:317-320）并改写为 v2（:380-381 `source_schema_version` 记录原版本）。A1 统一后必须保留该读取路径（旧 Run 未迁移可读）。
2. **外部质量审查**：本包 v2 目标契约升级后，旧 v1 报告仅按 v1 语义读取（修订二），不做静默字段映射。
3. **build manifest v1/v2**：标准构建仍写 v1（`runtime/build.py:20`）；v2 与 legacy 投影在 `scripts/build/manifest.py`。B5 切换标准构建消费 Page Package 时，v2 成为标准路径产物，v1 保留读取。
4. **schema 分发位置**：宿主 skill 目录只有 symlink，schema 只在中心 release 树 `contracts/`（`installer.py:1848-1852`）。A1 安装 v2 skill schema 时同步确认 release 树再生。

## 4. 迁移规则

- 每个新 schema 进入 `docs/contracts/` 时：命名沿用现有 `<object>.vN.schema.json` 连字符风格（非下划线），`$id` 沿用 `deck_<object>.vN` 运行时字符串。
- `skills/deck-master/schemas/` 与 `docs/contracts/` 同版本同步，禁止再出现 generation_result 式断代。
- 破坏性版本递增必须保留旧版本读取路径 + `migrated_from`/`source_schema_version` 记录（现有惯例，rc_gate.py:621、handback.py:381）。
