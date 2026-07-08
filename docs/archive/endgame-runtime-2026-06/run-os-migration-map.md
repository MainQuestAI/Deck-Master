# Deck Master Run OS 迁移保护清单

> 历史分支归档说明：本文来自 `origin/codex/deck-master-endgame-runtime`，仅用于追溯 2026-06 Run OS 迁移期间的保护边界。当前生产基线以 `main` 在 v0.9.13 之后的 suite runtime、product capabilities、setup/readiness 和 UC story review 结构为准。

日期：2026-06-11
分支：`codex/deck-master-endgame-runtime`
工作区：`<deck-master-endgame-runtime-worktree>`
基线提交：`9e57e48`
状态：P0-0 主控清单

## 1. 目的

这份清单用于保护当前 main 上已经可运行的 Deck Master MVP 能力。

终局实现会引入 Workspace、Runtime Contract、Claim-Evidence Graph、Review Cockpit、Quality-aware Export 等新能力。迁移过程中不能误删已有可用链路，也不能把已有 spike 当成最终架构直接叠功能。

本轮实现优先顺序：

1. 保留当前能跑通的 brief / conversation / autoplan / preview / quality / export 能力。
2. 先统一 runtime、events、`next_step` 和坏 JSON 处理。
3. 再让 Workspace、Planner、Sourcing、Quality Gate 和 Web UI 逐步读取同一套 run artifact。

## 2. 当前可保留能力

以下能力属于当前产品基线，迁移时必须保留并补强。

| 能力 | 当前入口 | 保留方式 |
|---|---|---|
| CLI 主入口 | `scripts/deck_master.py` | 保留命令形态，内部逐步变成 runtime 薄封装 |
| Brief 入口 | `plan`、`autoplan --brief/--brief-file` | 保留，用新 `next_step` 支持续跑 |
| Context 入口 | `start-conversation` | 保留，后续补 source hash、敏感标记和 workspace refs |
| Brief 编译 | `build-brief` | 保留，后续接 Consulting Judgment Layer |
| Claim Map | `build-claim-map` | 保留，后续升级为 Claim-Evidence Graph |
| Narrative Planner | `scripts/planning/narrative_planner.py` | 保留，后续读取 Workspace archetypes 和 density |
| 分层 Page Tasks | `scripts/planning/page_tasks.py` | 保留分层结构，补 `decision_intent`、`argument_chain`、`evidence_policy` |
| PPT Library fallback | `scripts/tools/ppt_library_client.py` | 保留 fixture / fake 回退，真实 CLI 失败不能阻断 run |
| Sourcing 决策 | `scripts/planning/sourcing_decider.py` | 保留四类决策，补 `decision` canonical 字段和 `score_breakdown` |
| Generation task package | `scripts/generation/task_builder.py` | 保留，P0 不强制自动执行 Build Skill |
| Preview manifest | `scripts/orchestrate/preview_builder.py`、`scripts/preview/manifest.py` | 保留，后续接 review_status / action_intent 分层 |
| Web preview server | `scripts/preview/server.py` | 保留 API 能力，后续按 Review Cockpit 设计重构信息架构 |
| Draft / Render / Delivery Gate | `scripts/quality/gate_runner.py` | 保留，Draft Gate 先接入硬链路 |
| Export queue | `scripts/orchestrate/export_queue.py` | 保留，必须补 Quality-aware export |
| Feedback MVP | `scripts/feedback/record_deal.py` | 保留，后续从 approved/rejected 扩展到 delivery outcome |

## 3. 必须优先重构的模块

| 优先级 | 模块 | 当前问题 | P0 目标 |
|---:|---|---|---|
| 1 | `scripts/runtime/events.py` | 仅有 `actor/action/status` 旧事件字段 | 兼容旧字段并新增 canonical typed events |
| 2 | `scripts/runtime/run_state.py` | `run_status` 只能判断 request / plan / sourcing / preview | 新增 canonical `next_step` resolver |
| 3 | `scripts/deck_master.py` | CLI 各命令直接串步骤，状态解释分散 | 增加 `status`、`next-step`、`validate-run`，逐步复用 runtime |
| 4 | `scripts/planning/page_tasks.py` | planning 层字段不足，workspace refs 为空 | 补核心叙事字段和 workspace 引用 |
| 5 | `scripts/planning/sourcing_decider.py` | 评分简化，`source_decision` 和 `decision` 未统一 | 补 canonical decision、score_breakdown、evidence_policy 判断 |
| 6 | `scripts/orchestrate/export_queue.py` | 只按 approved 过滤 | 读取 Draft Gate P0/P1 和 manual_placeholder 阻断 |
| 7 | `scripts/preview/server.py` | UI/API 仍偏 spike，审批状态和动作意图混合 | 接入 review_status、notes、quality findings 和 next_step |

## 4. 可以延后的能力

以下能力属于 P1/P2，不应阻塞 P0 可审查闭环。

| 能力 | 延后原因 |
|---|---|
| Build Skill 自动执行 | P0 先固定 task package 和 handback contract，避免长任务和失败恢复拖垮底座 |
| 多 Build Skill registry | 需要 task contract 稳定后再扩展 |
| Web UI 替换来源 / 转生成 / 锁定历史页 | 会改写 sourcing / generation / preview 多份状态，P0 先做只读审查和审批 |
| reference PPT 自动视觉提取 | 当前只登记路径和元数据 |
| OpenViking / 飞书实时接入 | 当前先使用本地或已导出资料 |
| 团队权限和协同 | 属于 Team Workspace 阶段 |
| 全量反馈学习 | P0 只记录 approved / rejected / delivered 基础信号 |

## 5. 兼容字段策略

### 5.1 Events

旧字段保留：

- `actor`
- `action`
- `target`
- `status`
- `payload_ref`
- `error`
- `data`

新增 canonical 字段：

- `schema_version`
- `event_id`
- `event_type`
- `run_id`
- `step`
- `message`
- `refs`
- `severity`

写入新事件时必须同时带旧字段和新字段。读取旧事件时不能报错。

### 5.2 Sourcing

旧字段：

- `source_decision`

canonical 字段：

- `decision`

P0 期间允许双写。对外 schema 和新代码优先读 `decision`，旧 preview / export 可兼容 `source_decision`。

### 5.3 Review

审批状态统一为：

- `needs_review`
- `approved`
- `rejected`

页面动作意图单独保存：

- `none`
- `replace_source`
- `convert_to_generate`
- `lock_history`
- `request_evidence`

P0 UI 只要求 approve / reject / note。

## 6. 回归命令

基础回归：

```bash
python3 -m unittest discover -s tests -v
```

fixture autoplan：

```bash
python3 scripts/deck_master.py autoplan \
  --brief-file examples/briefs/retail_digital_transformation.txt \
  --industry retail \
  --library-mode fixture \
  --runs-dir /tmp/deck-master-runs \
  --run-id retail-migration-smoke
```

conversation 到 claim map：

```bash
python3 scripts/deck_master.py start-conversation \
  --context-file examples/context/retail_meeting_transcript.txt \
  --industry retail \
  --runs-dir /tmp/deck-master-runs \
  --run-id retail-conversation-smoke

python3 scripts/deck_master.py build-brief \
  --runs-dir /tmp/deck-master-runs \
  --run-id retail-conversation-smoke

python3 scripts/deck_master.py build-claim-map \
  --runs-dir /tmp/deck-master-runs \
  --run-id retail-conversation-smoke
```

quality gate：

```bash
python3 scripts/deck_master.py quality-gate draft \
  --runs-dir /tmp/deck-master-runs \
  --run-id retail-migration-smoke
```

## 7. P0 完成判定

P0 不以“功能看起来多”为完成标准。

P0 完成需要同时满足：

1. 新 worktree 分支存在并承载实现。
2. `events.jsonl` 新写入事件包含 canonical typed fields。
3. `next_step` 能解释缺文件、坏 JSON、quality blocked、review pending、export ready。
4. CLI 能输出 run 状态、下一步和验证结果。
5. 旧 autoplan fixture 仍能跑到 preview。
6. Draft Gate P0/P1 能阻断 export。
7. Web UI 能展示 run/page/quality/review 基础状态。
8. 测试覆盖新增 runtime contract。

## 8. 当前并行分工

| 角色 | 范围 | 写入边界 |
|---|---|---|
| 主控 agent | 迁移清单、验收、后续集成和代码审查 | `docs/migration/`，必要时补验收文档 |
| Worker Godel | Runtime Contract Hardening | `scripts/runtime/`、`scripts/deck_master.py` runtime CLI、runtime tests |

worker 完成后，主控侧必须审查改动、运行回归，再决定是否继续拆 P0-2 Workspace Foundation。
