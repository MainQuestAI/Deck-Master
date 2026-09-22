# Deck Master Real Production Closure A0 Implementation Spec

## 1. A0 目标

A0 的目标是把下一轮 `v0.9.14 -> v0.9.16` 的开发基线锁住，避免后续任务按不同命令名、状态语义和 contract 真源并行推进。

本任务只交付开发基线文档，不实现运行时代码。

## 2. 当前事实

| 项目 | 事实 |
|---|---|
| Deck Master 分支 | `codex/real-production-closure` |
| Deck Master 基线 | `14fc43dc6e955928100f02f0e82af5b833c29177` |
| `origin/main` | `14fc43dc6e955928100f02f0e82af5b833c29177` |
| Spec 包 | `docs/deck-master-real-production-closure-spec-pack/`，41 个文件 |
| Suite version | `0.9.13` |
| Setup status | `ready` |
| Suite status | `degraded_ready` |
| Product capability manifest | valid |

关联仓库基线：

| 仓库 | 分支 | HEAD | 状态 |
|---|---|---|---|
| `PPT-Deck-Pro-Max` | `main` | `d6287172313e9b2c1fb04f8f2082dde3786f2ac4` | 有 1 个未跟踪 docs 文件 |
| `PPT-Library` | `main` | `0e48b7fa2f62de1c750118f275e5fe0a52709e1e` | 干净 |

## 3. CLI 冻结

本轮保留当前 CLI 作为兼容基础。后续任务可以新增目标命令或别名，但新增前必须写入 `spec-deviation-log.md` 或对应任务 spec。

| 目标能力 | 当前入口 | A0 决策 | 首次实现任务 |
|---|---|---|---|
| Contract validation | `validate-generation-result`、`validate-render-result`、`validate-product-capability-manifest` | 暂不新增总命令；A1/B1 后再评估 `contract-validate` 聚合入口 | A1 / B1 |
| Release build | `suite-build-release-tree` | 保留现名；C1 可增加 `release-build` alias | C1 |
| Release smoke | 无统一入口 | C2/C4 引入 release smoke 时再新增 | C2 / C4 |
| Final readiness | 无统一入口 | B3 新增 `final-readiness` | B3 |
| Build prepare/run/status | 当前只有 `render`、`render-status` | A4 新增 `build` 子命令组 | A4 |
| Artifact status | `render-status` 和后续 validation report | B1 后增加 `artifact-status` | B1 |
| Generation session | `generation-session create/status/import-results`、`run-generation` | A3 增加 prepare/dispatch 语义，保持 import-results | A3 |

## 4. 状态语义冻结

本轮使用以下状态迁移原则：

| 新语义 | 当前相关状态 | A0 决策 | 实现任务 |
|---|---|---|---|
| `awaiting_agent_execution` | `created`、`dispatched` | 作为 production generation 的新等待状态；`dispatched` 作为 legacy 输入兼容 | A3 |
| `needs_generation_execution` | `needs_generation_session`、`generation_running` | run-state 可在 A5 暴露新语义；旧状态保留兼容 | A5 |
| `needs_build` | 当前缺少独立 build stage | A4 先写 build manifest 和 build result；A5 再进入 run-state | A4 / A5 |
| `needs_render` | `needs_render` | 保留；A4 后表示 build 已就绪但 render 缺失或失败 | A4 / A5 |
| `ready_for_client_export` | `ready_for_client_export` | B3 前保持；B3 后读取 `final_readiness.json` | B3 / B4 |

任何 consumer 读取状态时必须兼容旧 run artifact。生产模式不得再把 placeholder artifact 标记为完成。

## 5. Contract 真源冻结

| 目录 | 职责 |
|---|---|
| `docs/contracts/` | Deck Master runtime contract 真源 |
| `product_capabilities/*/contracts/` | 能力包发布副本，只在 runtime contract 接受后同步 |
| `skills/deck-master/schemas/` | Agent 任务 schema，用于 Codex / Claude handoff |
| `docs/deck-master-real-production-closure-spec-pack/schemas/` | 规划包附带 schema 草案，不作为 runtime 真源 |

新增 v2/v1 contract 时，先放入 `docs/contracts/`。如果 task 需要让 skill 或 capability 读取相同 schema，再同步到对应发布副本，并在测试里校验版本一致。

## 6. 后续任务入口

### A1 — Generation Result v2

入口文件：

- `scripts/generation/handback.py`
- `scripts/generation/session.py`
- `scripts/runtime/run_state_resolver.py`
- `docs/contracts/`

最小交付：

- 接受 `deck_generation_result.v2`。
- 校验 run/session/path/checksum/source fingerprint。
- 安全兼容 v1。
- production profile 下拒绝 placeholder handback。

### A3 — Agent Execution & Handback

入口文件：

- `scripts/generation/session.py`
- `scripts/capabilities/ppt_deck_pro_max.py`
- `skills/deck-master/playbooks/`

最小交付：

- production generation 无执行器时进入 `awaiting_agent_execution`。
- 生成 Agent 可执行的 dispatch package。
- fixture adapter 只在 fixture/dev profile 下可用。

### A4 — Build / Render

入口文件：

- `scripts/runtime/render.py`
- `scripts/runtime/build.py`
- `product_capabilities/ppt-master/`
- `docs/contracts/`

最小交付：

- 输出 `deck_build_manifest.v1`。
- 输出 HTML、PDF、逐页 PNG、有效 PPTX。
- 输出 artifact metadata、checksum、media type、editability。

### A5 — Runtime / Workspace Integration

入口文件：

- `scripts/runtime/run_state_resolver.py`
- `scripts/runtime/next_step.py`
- `scripts/preview/workspace_api.py`
- `scripts/preview/static/*`

最小交付：

- 工作台能区分 Agent、Build、Render、Quality 卡点。
- API 保持旧字段兼容。
- 页面预览优先读取真实 page PNG/HTML。

## 7. A0 验收

A0 必须完成：

- `baseline-lock.json` 可解析。
- `implementation-spec.json` 可解析。
- `spec-deviation-log.md` 记录本轮规划包和实现基线的初始偏差。
- `test-evidence.md` 记录真实命令和结果。
- `git diff --check` 通过。
- 当前全量测试结果被记录，失败项不掩盖。

## 8. 已知约束

- 当前 suite 处于 `degraded_ready`，后续真实生产链路需要先修 skill 链接或在任务内明确降级边界。
- 当前系统 Python 缺 `python-pptx` 与 `jsonschema`，Node 缺 `playwright` 与 `pptxgenjs`。A4/B1 前需要补依赖或调整实现策略。
- `PPT-Deck-Pro-Max` 当前主工作区有未跟踪 docs 文件，A2 开分支前需要再次核验，避免误带入无关文档。
