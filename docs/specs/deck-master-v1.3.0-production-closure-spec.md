# Deck Master v1.3.0 Production Closure Spec

日期：2026-07-03
状态：Current Implementation Sync
用途：记录 v1.3.0 已如何把外部生产依赖、真实 benchmark 和 RC gate 收成可验证闭环，并明确后续发布固化边界
前置文档：

- `docs/planning/2026-07-03-deck-master-v1.3.0-production-closure-execution-plan.md`
- `docs/specs/production-closure-v1.3.0/00-development-package.md`
- `docs/specs/real-production-closure/implementation/implementation-spec.md`
- `docs/specs/skill-os-runtime-v1.1/00-master-spec.md`

## 1. 背景与目标

Deck Master 已经完成了：

1. Skill OS v1.1 运行态；
2. generation / build / render / quality / review / export 基础闭环；
3. release build、release smoke、benchmark metadata、RC gate 基础框架。

v1.3.0 的目标聚焦三件事：

1. 当前绑定的 production backend 到底是谁；
2. 当前外部 generation / build 依赖是否真的通过认证；
3. 当前 release 是否具备真实 client delivery 与 RC 放行条件。

## 2. 当前实现状态

### 2.1 `ppt-master` 已进入可认证 production backend 状态

当前 Deck Master 已能通过外部依赖真相识别 `ppt-master`：

1. binding status：`bound_verified`
2. git SHA：`23de38ce5fa8c39003b0643def710afb2a36c892`
3. verified：`true`
4. validated capabilities：`render`、`smoke`、`writeback`
5. `production_backend_ready=true`

因此，`production_backend_ready` 已有正式来源。后续重点是发布时继续保留 SHA、验证时间和 lock 证据。

### 2.2 `ppt-deck-pro-max` bridge 已进入 release truth

当前 bridge 已经具备 release truth：

1. 来源仓库：`MainQuestAI/PPT-Deck-Pro-Max`
2. 分支：`codex/deck-master-bridge`
3. 固定 SHA：`9444d88f573c3afa567bfb1763041325ef765313`
4. binding status：`bound_verified`
5. validated capabilities：`dispatch_import`、`generation_result_export`、`result_import_contract`

### 2.3 benchmark 已进入真实报告层

当前仓库已有 3 个完整 real benchmark case report pair：

1. `real_retail_growth`
2. `real_manufacturing_geo`
3. `real_healthcare_enablement`

`benchmarks/results/aggregate/benchmark_aggregate_report.json` 当前为：

1. `status=report_ready`
2. `benchmark_report=3`
3. `benchmark_rc_report=3`
4. `complete_real_case_pairs=3`

### 2.4 RC gate 已通过

当前 `rc_reports/rc_gate_report.json` 为：

1. `status=pass`
2. `checks=7`
3. `required_failures=0`
4. `external_dependency_closure=pass`
5. `benchmark_aggregate=pass`

`suite-status` 当前给出 `full_suite_ready=true`、`production_backend_ready=true`、`client_delivery_ready=true`。`setup-status` 同步透传这两个 readiness，但 active workspace 仍可能因为材料缺失提示 repair，这属于工作区材料边界，需要在发布说明中单独解释。

### 2.5 当前闭环属于系统级 readiness，不等于每个 run 已最终成片

当前实现已经证明 Deck Master 在系统级、发布级口径上具备生产闭环：

1. 外部 backend 已认证；
2. bridge 已固定 SHA；
3. benchmark report / RC report / aggregate 已生成；
4. RC gate 已 pass；
5. `client_delivery_ready=true`。

但这不意味着每个真实 run 已自动进入最终客户交付状态。当前 benchmark 报告仍显示：

1. `readiness.final_ready=false`
2. `export_ready=false`
3. `quality_blocked=true`
4. aggregate `metrics.final_ready_count=0`

同时，生产 build 当前进入 `awaiting_external_render` handoff，具体 run 仍需等待外部 renderer 产出并回写真实 `render_result`。因此，v1.3.0 当前证明的是“系统已具备真实生产交付链路与发布真相”，每个 run 的最终成片 readiness 仍需按 run 单独判断。

## 3. 范围

v1.3.0 Spec 包含四个子范围。

### 3.1 外部 backend 绑定与认证

目标：

1. 让 Deck Master 正式绑定 `ppt-master` 仓；
2. 读取固定 SHA；
3. 基于 manifest + smoke + operation 做认证；
4. 对外输出 production backend 真相。

### 3.2 外部 generation bridge 固定化

目标：

1. 让 `ppt-deck-pro-max` bridge 进入 capability lock；
2. 形成正式 cross-repo smoke；
3. 让 release truth 能追踪 generation bridge 版本。

### 3.3 真实 benchmark 闭环

目标：

1. 用 3 个私有 real case 跑出真实 report；
2. 让 aggregate 从 `metadata_ready` 变成 `report_ready`。

### 3.4 RC 放行收口

目标：

1. 让 RC report 能检查外部依赖闭环；
2. 让 RC report 真正反映系统级生产可交付状态；
3. 明确它与 run 级最终成片判断的边界。

## 4. 非目标

本轮不做以下工作：

1. 不引入新的知识连接器；
2. 不做新的 UI 大改；
3. 不把完整 `ppt-master` vendoring 进 release tree；
4. 不扩展新的 build/render 技术栈；
5. 不新增 benchmark case 类型。

## 5. 设计决策

### 5.1 `ppt-master` 以外部 Git 仓为真源

`hugohe3/ppt-master` 是 v1.3.0 的唯一 production backend 真源。
安装态目录保留用于运行，但不再作为 release 追溯真源。

### 5.2 本轮采用“外部依赖固定 SHA”模式

v1.3.0 不引入 vendored backend snapshot。
所有 production 依赖统一按：

1. 仓库路径；
2. 当前 SHA；
3. 认证结果；
4. 验证时间

四项来管理。

### 5.3 私有 benchmark raw source 继续本地化

真实 benchmark 的 raw source 继续放在：

- `~/deck-master-local-benchmarks/<case_id>/raw`

仓库内只保留 metadata、路径引用和最终 benchmark report。

## 6. 外部 backend 绑定模型

## 6.1 新增绑定概念

Deck Master 增加“外部 backend 绑定”概念。
绑定对象至少覆盖：

1. `ppt-master`
2. 后续可扩展的其他 production backend

## 6.2 建议命令

新增以下命令：

```text
deck-master backend bind ppt-master --repo <repo_path>
deck-master backend status
deck-master backend verify ppt-master
deck-master backend unbind ppt-master
```

说明：

1. `bind` 负责登记 repo 和 skill path；
2. `status` 负责展示当前绑定与认证状态；
3. `verify` 负责读取 manifest、operation、smoke 结果；
4. `unbind` 只清绑定记录，不删除外部仓。

## 6.3 绑定记录

建议新增本地记录文件：

```text
~/.deck-master/backend_bindings.json
```

建议字段：

```json
{
  "schema_version": "deck_backend_bindings.v1",
  "bindings": [
    {
      "name": "ppt-master",
      "repo_path": "/abs/path/to/ppt-master",
      "skill_path": "/abs/path/to/ppt-master/skills/ppt-master",
      "git_sha": "abcdef...",
      "git_branch": "main",
      "worktree_dirty": false,
      "verified": true,
      "verified_at": "2026-07-03T12:00:00+08:00",
      "validated_capabilities": ["render", "smoke", "writeback"]
    }
  ]
}
```

## 6.4 认证规则

`backend verify` 至少执行以下检查：

1. `repo_path` 是 git worktree；
2. `skill_path` 存在；
3. `SKILL.md` frontmatter 合法；
4. `references/`、`scripts/`、`templates/` 非空；
5. `deck-master-backend.json` 或 `capability.json` 存在；
6. operation 至少包含：
   - `render`
   - `smoke`
   - `writeback`
7. smoke 命令通过。

输出结果建议分三层：

1. `ready`
2. `blocked`
3. `warning`

其中：

- `ready`：全部 required checks 通过
- `blocked`：manifest / operation / smoke 任一 required 失败
- `warning`：绑定有效，但 worktree dirty 或 branch 非推荐值

## 7. capability lock 扩展

## 7.1 当前问题

当前 `deck_capability_lock.json` 只记录：

1. suite 基本信息；
2. skills；
3. capabilities；
4. contracts。

它还不能回答“这次 release 依赖了哪一个外部 backend/bridge”。

## 7.2 新字段

`deck_capability_lock.json` 增加：

```json
{
  "external_dependencies": [
    {
      "name": "ppt-master",
      "repo": "https://github.com/hugohe3/ppt-master",
      "repo_path": "/abs/path/to/ppt-master",
      "git_sha": "abcdef...",
      "git_branch": "main",
      "validated_capabilities": ["render", "smoke", "writeback"],
      "verified": true,
      "verified_at": "2026-07-03T12:00:00+08:00"
    },
    {
      "name": "ppt-deck-pro-max",
      "repo": "MainQuestAI/PPT-Deck-Pro-Max",
      "repo_path": "/abs/path/to/PPT-Deck-Pro-Max",
      "git_sha": "9444d88f573c3afa567bfb1763041325ef765313",
      "git_branch": "codex/deck-master-bridge",
      "validated_capabilities": ["dispatch_import", "generation_result_v2_export"],
      "verified": true,
      "verified_at": "2026-07-03T12:00:00+08:00"
    }
  ]
}
```

## 7.3 release build 行为

release build 在写 capability lock 时：

1. 读取当前绑定记录；
2. 读取当前 verify 结果；
3. 将已认证外部依赖写入 `external_dependencies[]`；
4. 未绑定或未认证的 required dependency 不写入 ready release。

## 8. `suite-status` / `setup-status` / Review Desk 扩展

## 8.1 `suite-status`

新增顶层：

```json
{
  "external_dependency_status": [
    {
      "name": "ppt-master",
      "status": "ready",
      "git_sha": "abcdef...",
      "blocking_summary": []
    }
  ]
}
```

### 语义要求

1. `production_backend_ready` 只由已绑定且已认证的 `ppt-master` 决定。
2. `client_delivery_ready` 需要：
   - full suite ready
   - production backend ready
   - required external dependency verified

## 8.2 `setup-status`

新增输出：

1. 当前绑定 backend
2. 当前 backend verify 状态
3. `repair_owner=backend` 的结构化阻断摘要

## 8.3 Review Desk

首页和 run 详情增加：

1. 当前 `ppt-master` 来源
2. 当前 SHA
3. `ppt-deck-pro-max` bridge SHA
4. benchmark aggregate 是否为 `report_ready`
5. RC 当前是否已通过，若未通过则给出缺失证据类型

## 9. `ppt-deck-pro-max` bridge 固定化

## 9.1 目标

让 Deck Master 对 `ppt-deck-pro-max` 的依赖满足四个条件：

1. 有明确来源；
2. 有固定 SHA；
3. 有 smoke；
4. 能写入 capability lock。

## 9.2 交叉仓库 smoke

建议形成固定 smoke 流程：

1. Deck Master：`run-generation --no-execute`
2. bridge：import dispatch package
3. bridge：export canonical `deck_generation_result.v2`
4. Deck Master：import generation results
5. Deck Master：检查 run-state 是否从 `awaiting_agent_execution` 前进

smoke 通过后，verify 结果写入 `validated_capabilities`：

- `dispatch_import`
- `generation_result_v2_export`

## 10. benchmark 闭环要求

## 10.1 私有目录结构

每个 real case 使用：

```text
~/deck-master-local-benchmarks/<case_id>/
  context_pack.json
  raw/
  workspace/
```

约束：

1. `raw/` 不入 git；
2. `workspace/` 不入 git；
3. `context_pack.json` 可为本地文件；
4. 仓库中的 `benchmark_case.json` 只保留 metadata 和路径引用。

## 10.2 报告闭环

每个 real case 至少产出：

1. `benchmark_report.json`
2. `benchmark_rc_report.json`

aggregate 的放行条件：

1. `real_metadata >= 3`
2. 至少 3 个真实 report 被发现
3. 状态为 `report_ready`

## 11. RC gate 收口

## 11.1 已落地 required check

当前 RC gate 已包含 required check：

```text
external_dependency_closure
```

该检查验证：

1. `ppt-master` 已绑定；
2. `ppt-master` verify 通过；
3. `ppt-master` 已写入 capability lock；
4. `ppt-deck-pro-max` bridge 已固定 SHA；
5. bridge 已写入 capability lock；
6. `benchmark_aggregate=report_ready`

## 11.2 与现有检查关系

当前 RC gate 的 required check 至少包括：

1. schema json parse
2. artifact validator
3. release smoke
4. fixture e2e
5. benchmark aggregate
6. external dependency closure

当前证据文件 `rc_reports/rc_gate_report.json` 显示：

1. `external_dependency_closure=pass`
2. `benchmark_aggregate=pass`
3. `required_failures=0`
4. 这组 evidence 支撑的是 suite/release 级 readiness，不替代单个 run 的最终成片判断。

## 12. 测试与验收

## 12.1 Deck Master 主仓测试

当前实现已经覆盖以下测试方向，后续变更需要继续保持：

1. backend bind / verify / unbind
2. capability lock 写入 external dependencies
3. suite-status external dependency output
4. setup-status backend blocking summary
5. Review Desk external dependency projection
6. RC gate 新增 external dependency closure check

## 12.2 外部仓验证

至少验证：

1. `ppt-master` backend manifest 可解析
2. `ppt-master` smoke 可运行
3. `PPT-Deck-Pro-Max` bridge cross-repo smoke 可运行

## 12.3 benchmark 验收

至少验证：

1. 三个 real case 的本地路径可解析
2. 三个 real case 都有真实 report
3. aggregate 状态为 `report_ready`

## 13. 实施顺序与当前状态

原建议顺序：

1. `ppt-master` 外部仓补 manifest + smoke
2. Deck Master 增 backend bind + verify
3. Deck Master 扩 capability lock + suite status
4. `ppt-deck-pro-max` bridge 固定 SHA + cross-repo smoke
5. 建立三个私有 benchmark 目录
6. 跑真实 benchmark report
7. 扩 RC gate 并重跑

当前仓状态已经完成上述主线闭环。后续工作应围绕证据固化、发布说明、Review Desk 展示口径和 clean install / browser smoke 的正式门禁选择推进。

## 14. 交付标准

按当前仓状态，v1.3.0 核心交付标准已经满足：

1. `ppt-master` 通过 production backend 认证；
2. `ppt-master` 与 `ppt-deck-pro-max` 均进入 capability lock；
3. `suite-status`、`setup-status`、Review Desk 对外部依赖口径一致；
4. 3 个 real benchmark 全部生成真实 report；
5. aggregate 状态为 `report_ready`；
6. `rc-gate` required failures = 0。

仍需发布前人工确认：

1. Review Desk 是否已按同一套安全摘要展示；
2. 当前 active workspace repair 是否影响本次 release 对外口径；
3. browser smoke 是否作为正式发布门禁；
4. `awaiting_external_render` handoff 是否已在 release note 中讲清，避免把 backend smoke 的 `contract_smoke` 误解为客户产物来源；
5. run 级最终成片 readiness 是否要在后续版本单列为独立状态与证据。

## 15. 开放问题

以下问题已按当前实现收敛：

1. `ppt-master` 已通过当前 backend manifest / smoke / operation 认证；
2. `ppt-deck-pro-max` 已按固定 SHA 进入外部依赖真相；
3. `external_dependency_closure` 已进入 RC gate 并通过；
4. 3 个 real benchmark case 已进入 aggregate `report_ready`。

仍建议主线程人工确认：

1. `worktree_dirty` 在后续发布中继续作为 warning 还是提升为阻断；
2. browser smoke 是否要强制纳入 v1.3.0 放行；
3. Review Desk 是否已经完成无绝对路径泄露的产品级展示；
4. active workspace repair 是否需要在本次发布材料中单列说明。
