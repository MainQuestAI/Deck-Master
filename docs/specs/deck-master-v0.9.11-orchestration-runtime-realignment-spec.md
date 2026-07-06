# Deck Master v0.9.11 Orchestration Runtime Realignment Spec v0.2

日期：2026-06-15
状态：Spec v0.2，已吸收评审意见，进入实现前基线

## 1. 背景

v0.9.10 已经补齐首次 Setup、真实 run 门禁、人工规划回写和外部结果登记，但真实会话仍暴露出更深的主链路问题：

- 用户点名 Deck Master 后，Agent 仍可能先调用 Canva 或在外部手写 plan / sourcing。
- Setup 可以在没有 active workspace 的情况下进入 ready。
- active workspace 影响 runs dir，但没有稳定写入 request、planner、page tasks 和质量标准读取链路。
- 自动规划仍可能回退到硬编码模板，生成与客户行业无关的页型。
- `next-step`、`orchestration-check`、Review Cockpit 和 Benchmark 对 run 状态的判断口径分散。
- PPT Deck Pro Max 只通过文件契约参与，Deck Master 缺少受控 production session。
- 医药客户样本真实 run 出现 `needs_page_review` 与外部生产放行并存的状态分裂。

本轮定位为一次主控运行时重对齐：让 Deck Master 先拥有唯一可信的生产状态、工作区绑定、生产会话和外部工具回写治理，再进入 v1.0 RC benchmark。

## 2. 目标

v0.9.11 的目标是让真实 Deck run 必须沿 Deck Master 的 workspace-bound production chain 推进。

标准链路：

```text
setup / workspace guard
→ workspace-bound run
→ context / guided conversation
→ brief / claim / narrative advice
→ workspace-aware planner
→ sourcing
→ production session
→ quality gate
→ review cockpit
→ export / benchmark
```

所有外部 Agent、PPT Master、PPT Deck Pro Max 和人工校准结果，都只能通过 Deck Master 的 task、state、handoff、review、quality 和 import contract 进入生产链路。

## 3. 非目标

本轮暂缓以下范围：

- 不内置 LLM provider。
- 不把 PPT Deck Pro Max 全量代码并入 Deck Master。
- 不重写 Review Cockpit 前端。
- 不做多团队商业版 workspace。
- 不重做 PPT Library 解析能力。
- 不重写 v0.9.7 Benchmark Harness。

短期产品选择：Deck Master 继续采用 Companion Tool 模式，但 Deck Master 必须拥有 production session、命令状态、结果导入和质量放行的主控权。PPT Deck Pro Max 是否深度内化，放到 v0.9.11 真实 UAT 后基于证据再定。

## 4. 核心运行合同

### 4.1 Run Mode

所有 run 必须显式写入：

```text
run_mode = production | fixture | dev | benchmark
```

`request.json` 示例：

```json
{
  "schema_version": "deck_request.v2",
  "run_id": "example-run",
  "run_mode": "production",
  "workspace": "/absolute/path/to/workspace",
  "workspace_id": "workspace_abc123",
  "workspace_manifest_ref": "workspace_manifest.json",
  "workspace_resolved_from": "cli",
  "runs_dir": "/absolute/path/to/workspace/runs",
  "runs_dir_resolved_from": "workspace_default"
}
```

运行规则：

| run_mode | workspace 是否必需 | 允许 fixture template | 允许跳过 setup | 可进入 v1.0 RC 判断 |
|---|---:|---:|---:|---:|
| production | 必需 | 否 | 否 | 可以 |
| fixture | 可选 | 可以 | 可以 | 否 |
| dev | 可选 | 可以 | 可以 | 否 |
| benchmark | 必需，fixture benchmark 除外 | 由 case 指定 | 否，fixture benchmark 除外 | 仅 RC 模式可以 |

`--dev-allow-unsetup` 和 `DECK_MASTER_DEV_SKIP_SETUP=1` 只能在 `run_mode=dev` 或 `run_mode=fixture` 下生效。production run 不接受这些绕过开关。

### 4.2 Setup Readiness

Setup 状态拆成四层：

```text
install_ready
workspace_ready
run_ready
production_ready
```

`install_ready=true` 代表本机已安装 Deck Master 与 Agent skill 入口。

`workspace_ready=true` 代表 active workspace 存在，并且标准目录、质量规则、runs dir、exports dir 已通过校验或修复。

`run_ready=true` 代表指定 run 可以被读取和继续推进。

`production_ready=true` 代表真实客户项目可以启动或继续生产。

`setup-status` 输出示例：

```json
{
  "schema_version": "deck_master_setup_status.v2",
  "status": "needs_workspace",
  "install_ready": true,
  "workspace_ready": false,
  "run_ready": false,
  "production_ready": false,
  "dev_mode_allowed": false,
  "fixture_mode_allowed": true,
  "install_root": "~/.deck-master/current",
  "active_workspace": "",
  "default_runs_dir": "~/.deck-master/runs",
  "active_workspace_required_for_production": true,
  "next_command": "deck-master setup --workspace <path> --target codex --repair-workspace"
}
```

验收标准：

- `setup --runs-dir <path>` 且无 workspace 时，`production_ready=false`。
- `install-skill` 返回清晰的 next setup command。
- `setup-status` 展示 install / workspace / run / production 四层状态。
- production command 只接受 `production_ready=true`。
- dev 和 fixture 绕过必须写入 run mode 和事件日志。

### 4.3 Workspace Resolver

所有真实生产命令必须统一调用 workspace resolver。

解析优先级：

```text
1. CLI --workspace
2. request.json.workspace
3. ~/.deck-master/config.json active_workspace
4. blocked with next_command
```

冲突策略：

| 场景 | 行为 |
|---|---|
| 创建新 run | `--workspace` 优先；没有则使用 setup active workspace；都没有则 blocked |
| 已有 run | `request.json.workspace` 是 source of truth |
| 已有 run + CLI workspace 与 request 不一致 | blocked |
| setup active workspace 与 request 不一致 | warning，不覆盖 request |
| 允许重新绑定 workspace | 必须显式执行 `bind-workspace` |

新增迁移命令：

```bash
deck-master bind-workspace --run-dir <path> --workspace <path> --reason <text>
```

`bind-workspace` 行为：

- 备份旧 `request.json` 到 `overrides/workspace_binding_<timestamp>/`。
- 写入 `request.json.workspace`、`workspace_id`、`workspace_resolved_from`。
- 写入 `workspace_binding.json`。
- 追加事件 `workspace.bound`。
- 重新运行 `run-state`。

runs dir 默认规则：

- production run 默认写入 `<workspace>/runs`。
- runs dir 可以在 workspace 外，但必须显式传 `--runs-dir`，并在 request 里记录 `runs_dir_resolved_from=cli`。

### 4.4 Source of Truth

Canonical resolver 必须使用固定状态源。不得从展示层或派生字段反推生产状态。

| 维度 | Source of Truth | 禁止来源 |
|---|---|---|
| workspace | `request.json.workspace` + `workspace_manifest.json` | 不直接用 runs dir 推断 |
| planning | `narrative_plan.json` + `page_tasks.json` | 不用 preview title 反推 |
| sourcing | `sourcing_plan.json` | 不用 page tasks 顶层 source decision 当最终值 |
| review | `preview_manifest.json.pages[].review_status` / `decision` | 不用 page tasks review status |
| generation | `generation_session.json` + `generation_results/` | 不只看 generation_tasks 是否存在 |
| render | `render_result.json` + `preview_manifest.json` final artifact refs | 不只看导出目录是否存在 |
| quality | `quality_reports/*_gate.json` | 不只看 quality_reports 目录存在 |
| export | `approved_queue.json` 或实时 `export_queue()` | 不只看 approved 页面数量 |
| benchmark | `benchmark_checkpoints.json` + `run-state` | 不只看 report 是否存在 |

### 4.5 Canonical Run State Resolver

新增：

```text
scripts/runtime/run_state_resolver.py
```

输出 schema：

```json
{
  "schema_version": "deck_run_state.v1",
  "run_id": "example-run",
  "run_mode": "production",
  "stage": "needs_review",
  "policy_mode": "production",
  "readiness": {
    "setup": {},
    "workspace": {},
    "artifacts": {},
    "planning": {},
    "sourcing": {},
    "generation": {},
    "render": {},
    "review": {},
    "quality": {},
    "export": {},
    "benchmark": {}
  },
  "allowed_actions": [
    "open_review_cockpit",
    "import_quality_review"
  ],
  "blocked_actions": [
    {
      "action": "run_generation",
      "reason": "Generation session already has pending tasks."
    },
    {
      "action": "client_export",
      "reason": "22 pages still need review."
    }
  ],
  "next_command": "deck-master review-cockpit --run-dir <path>"
}
```

状态阶段：

```text
blocked_setup
blocked_workspace
needs_context
needs_guided_answers
needs_brief
needs_claim_map
needs_planning
needs_sourcing
needs_generation_session
generation_blocked
generation_running
generation_failed
needs_generation_import
needs_preview
needs_review
needs_quality_gate
needs_quality_review
ready_for_generation_session
ready_for_render
ready_for_client_export
ready_for_benchmark
```

入口分工：

| 入口 | 职责 |
|---|---|
| `run-state` | 返回全量状态 |
| `next-step` | 返回简化下一步 |
| `orchestration-check` | 返回外部生成、外部审查、导出、benchmark policy view |
| Review Cockpit readiness | 展示 resolver 状态 |
| Benchmark runner | 记录 resolver 状态，并按模式判断是否可用于 RC |

`orchestration-check` 输出示例：

```json
{
  "status": "blocked",
  "policy": {
    "external_generation_allowed": false,
    "external_review_allowed": true,
    "client_export_allowed": false,
    "benchmark_rc_allowed": false
  },
  "reasons": [
    "22 pages still need review."
  ]
}
```

### 4.6 Benchmark Gate

Benchmark 分为四类：

| 类型 | 目的 | 是否必须 ready_for_benchmark |
|---|---|---:|
| `benchmark-run` | 创建或推进 benchmark run，允许 pending 状态 | 否 |
| `benchmark-report` | 对已有 run 生成阶段性报告 | 否 |
| `benchmark-rc-report` | 用于 v1.0 RC 判断 | 必需 |
| `benchmark-compare` | 对多次 run 做对比 | 建议必需 |

规则：

- `benchmark-run` 和 `benchmark-report` 可以记录 pending 状态。
- `benchmark-rc-report` 和 `--rc-readiness` 必须要求 `ready_for_benchmark`。
- fixture benchmark 不得作为 v1.0 RC 判断依据。

### 4.7 Tool Registry

Deck Master 不得硬编码本机 PPT Deck Pro Max 路径。

新增工具注册：

```text
~/.deck-master/tools.json
<workspace>/tool_registry.json
```

schema 示例：

```json
{
  "schema_version": "deck_tool_registry.v1",
  "tools": {
    "ppt-deck-pro-max": {
      "type": "cli",
      "command": "ppt-deck-pro-max",
      "args_template": [
        "generate",
        "--task-dir",
        "{run_dir}/generation_tasks",
        "--output-dir",
        "{run_dir}/generation_results"
      ],
      "availability_check": [
        "ppt-deck-pro-max",
        "--version"
      ]
    },
    "ppt-master": {
      "type": "cli",
      "command": "ppt-master",
      "availability_check": [
        "ppt-master",
        "--version"
      ]
    }
  }
}
```

解析优先级：

```text
1. CLI --tool-command
2. workspace/tool_registry.json
3. ~/.deck-master/tools.json
4. blocked
```

工具不可用时，production session 必须进入 `blocked`，并写出可执行修复提示。

### 4.8 Production Session

本轮以 generation session 为主，同时在 resolver 中保留 render 维度。

generation session 状态机：

```text
created
blocked
dispatched
running
completed
partial
failed
results_imported
preview_refreshed
quality_required
```

新增文件：

```text
generation_session.json
generation_sessions/<session_id>.json
```

schema 示例：

```json
{
  "schema_version": "deck_generation_session.v1",
  "run_id": "example-run",
  "session_id": "gen-20260615-001",
  "tool": "ppt-deck-pro-max",
  "status": "created",
  "tasks_total": 10,
  "tasks_completed": 0,
  "tasks_failed": 0,
  "command": [],
  "started_at": "",
  "completed_at": "",
  "errors": []
}
```

render 维度最小状态：

```json
{
  "render": {
    "required": true,
    "status": "missing",
    "artifact_path": "",
    "preview_paths": []
  }
}
```

## 5. P0 / P1 开发包

### Package A：Admission & State Core

目标：封住真实 run 的入口，建立唯一运行状态。

包含：

- Setup / Workspace Readiness Split。
- Workspace Resolver + Workspace-bound Request。
- `deck-master start` / `deck-master doctor`。
- Canonical Run State Resolver。
- `next-step` / `orchestration-check` / Review Cockpit readiness 接入 resolver。
- Studio Setup Guard。

影响文件：

```text
scripts/runtime/setup_status.py
scripts/runtime/workspace_resolver.py
scripts/runtime/run_state_resolver.py
scripts/runtime/next_step.py
scripts/runtime/orchestration.py
scripts/deck_master.py
scripts/preview/server.py
scripts/preview/static/index.html
scripts/preview/static/app.js
scripts/preview/static/style.css
```

新增/修订命令：

```bash
deck-master setup-status [--workspace <path>] [--run-dir <path>]
deck-master doctor [--workspace <path>] [--run-dir <path>]
deck-master start [--workspace <path>] [--run-dir <path>]
deck-master run-state --run-dir <path>
deck-master orchestration-check --run-dir <path>
```

验收标准：

- 无 active workspace 时，production command blocked。
- `request.json` 必须写入 `run_mode` 和 workspace 结构。
- 已有 run 的 request workspace 与 CLI workspace 冲突时 blocked。
- `next-step`、`orchestration-check`、Review Cockpit readiness 使用同一个 resolver。
- Studio setup 未完成时 `POST /api/runs` 返回 409。
- classic demo mode 必须写入 `run_mode=fixture`。

### Package B：Planner & Sourcing Control

目标：解决真实客户方案规划污染、人工校准回写和旧 run 迁移。

包含：

- Production Planner Guard。
- Guided Question minimal runtime。
- `import-sourcing` / `validate-sourcing`。
- `bind-workspace` 旧 run migration。

影响文件：

```text
scripts/planning/page_budget.py
scripts/planning/narrative_planner.py
scripts/planning/brief_intake.py
scripts/conversation/session_builder.py
scripts/deck_master.py
scripts/runtime/run_state_resolver.py
```

Planner mode：

```text
fixture_template
workspace_fallback
production_narrative
```

规则：

- `fixture_template` 只能在 `request.run_mode=fixture` 或 fixture benchmark case 中启用。
- `production_narrative` 必须读取 deck brief、claim map、workspace、context 或 narrative advice。
- production mode 缺 claim map 时，不生成 production plan。
- production mode 下，医药、DAM、AI 内容底座等样本不得出现“库存可视化”“最后一公里配送”等无关页型。

Planner 输出必须包含：

```json
{
  "planner_mode": "production_narrative",
  "input_sources": [
    "deck_brief",
    "claim_map",
    "workspace_archetypes"
  ],
  "fallback_reason": ""
}
```

Guided Question minimal runtime：

```bash
deck-master answer-question --run-dir <path> --question-id <id> --answer <text>
deck-master skip-question --run-dir <path> --question-id <id> --reason <text>
deck-master lock-decision --run-dir <path> --key <key> --value <value>
```

question source：

```text
<workspace>/structure-assets/guided_questions.json
skills/deck-master/default_guided_questions.json
```

production workspace 可以覆盖默认问题。

Sourcing P0 只支持 JSON：

```bash
deck-master import-sourcing --run-dir <path> --input <sourcing-plan.json> --source human|agent
deck-master validate-sourcing --run-dir <path>
```

Markdown sourcing 放到 P1。P0 可以把 Markdown 原文作为附件保存，但 canonical source 必须是 JSON。

sourcing schema：

```json
{
  "schema_version": "deck_sourcing_plan.v1",
  "run_id": "example-run",
  "source": "human",
  "decisions": [
    {
      "beat_id": "beat_001",
      "source_decision": "adapt",
      "decision_reason": "Use historical DAM intro page.",
      "selected_candidate": {},
      "generation_brief": ""
    }
  ]
}
```

验收标准：

- sourcing plan 不完整时导入失败，并列出缺失页面。
- 旧 `sourcing_plan.json` 备份到 `overrides/sourcing_<timestamp>/`。
- 导入成功后刷新 preview manifest 的 sourcing summary。
- 事件日志包含 `sourcing.override.imported`。
- 医药客户样本旧 run 能通过 `bind-workspace` 迁移。

### Package C：Production Session Bridge

目标：让 Deck Master 受控调用或登记 PPT Deck Pro Max / PPT Master 的生产结果。

包含：

- Adapt / Generate task semantics。
- Tool registry。
- Generation session bridge。
- `run-generation` dry-run / no-execute / command log。
- result import + preview refresh + quality required。

影响文件：

```text
scripts/generation/task_builder.py
scripts/generation/handback.py
scripts/tools/deck_pro_max_client.py
scripts/deck_master.py
scripts/runtime/run_state_resolver.py
```

Adapt / Generate schema：

```json
{
  "task_type": "adapt",
  "source_decision": "adapt",
  "reference_slide_required": true,
  "expected_operation": "rewrite_existing_slide"
}
```

```json
{
  "task_type": "generate",
  "source_decision": "generate",
  "reference_slide_required": false,
  "expected_operation": "create_new_slide"
}
```

新增命令：

```bash
deck-master generation-session create --run-dir <path> --tool ppt-deck-pro-max
deck-master generation-session validate --run-dir <path>
deck-master generation-session status --run-dir <path>
deck-master run-generation --run-dir <path> --tool ppt-deck-pro-max [--dry-run] [--no-execute] [--tool-command <path>]
deck-master generation-session import-results --run-dir <path> --input <result.json>
```

验收标准：

- tool unavailable 时 session status 为 `blocked`。
- `--dry-run` 只输出 command plan，不写执行完成状态。
- `--no-execute` 允许 Agentic handoff，不启动外部工具。
- 成功调用时写 command log。
- result run id 不匹配时拒绝导入。
- result 导入成功后刷新 preview manifest。
- result 导入后 resolver 返回 `needs_quality_gate`。
- Review Cockpit 显示 session 状态。

### Package D：Regression & Real Case Smoke

目标：用真实 case 验证主链路已经收束。

包含：

- 医药客户样本真实 run migration。
- workspace-bound run smoke。
- benchmark harness re-run。
- docs / skill playbook update。

验收标准：

- 医药客户样本 run 绑定 workspace 后，`request.json.workspace` 非空。
- `run-state` 不再出现待审与外部生产放行并存。
- benchmark-report 可以记录 pending。
- benchmark-rc-report 在未 ready 时 blocked。
- Skill 文档要求先进入 `deck-master start` 或 `deck-master doctor`。

## 6. Public Interfaces

### CLI

```bash
deck-master setup-status [--workspace <path>] [--run-dir <path>]
deck-master doctor [--workspace <path>] [--run-dir <path>]
deck-master start [--workspace <path>] [--run-dir <path>]
deck-master run-state --run-dir <path>
deck-master bind-workspace --run-dir <path> --workspace <path> --reason <text>
deck-master plan --workspace <path> --run-mode production ...
deck-master autoplan --workspace <path> --run-mode production ...
deck-master import-sourcing --run-dir <path> --input <sourcing-plan.json> --source human|agent
deck-master validate-sourcing --run-dir <path>
deck-master generation-session create --run-dir <path> --tool ppt-deck-pro-max
deck-master generation-session validate --run-dir <path>
deck-master generation-session status --run-dir <path>
deck-master run-generation --run-dir <path> --tool ppt-deck-pro-max [--dry-run] [--no-execute] [--tool-command <path>]
deck-master generation-session import-results --run-dir <path> --input <result.json>
deck-master answer-question --run-dir <path> --question-id <id> --answer <text>
deck-master skip-question --run-dir <path> --question-id <id> --reason <text>
deck-master lock-decision --run-dir <path> --key <key> --value <value>
```

### API

```text
GET /api/setup-status
GET /api/run-state/<run_id>
POST /api/runs
POST /api/generation-session
POST /api/import-sourcing
```

UI 仍可保留 `run_dir` query 作为调试参数，但主路径应优先使用 run id。

### 新配置

```text
~/.deck-master/config.json
~/.deck-master/tools.json
<workspace>/tool_registry.json
```

### 新事件

```text
setup.status.checked
workspace.resolved
workspace.bound
run.state.resolved
run.mode.assigned
sourcing.override.imported
generation.session.created
generation.session.validated
generation.session.started
generation.session.blocked
generation.session.completed
generation.session.results_imported
generation.preview_refreshed
generation.quality_required
question.answered
question.skipped
decision.locked
```

## 7. 测试计划

### 7.1 Setup / Workspace

- setup 无 workspace 时 `workspace_ready=false` 且 `production_ready=false`。
- setup 有 workspace 时，active workspace 写入 config。
- workspace 缺标准目录时返回 `needs_repair` 或 `blocked_workspace`。
- `setup --repair-workspace` 只创建缺失项，不覆盖已有文件。
- install-skill 后输出 next setup command。

### 7.2 Run Mode

- `run_mode=production` + no workspace -> blocked。
- `run_mode=fixture` + no workspace -> allowed。
- `run_mode=dev` + `DECK_MASTER_DEV_SKIP_SETUP=1` -> allowed。
- `run_mode=benchmark` 在 RC 模式下必须满足 benchmark readiness。

### 7.3 Workspace Resolver

- `request.workspace=A`，CLI `--workspace=B` -> blocked。
- `request.workspace=A`，setup active workspace=B -> warning，但不覆盖 request。
- new run 无 CLI workspace 但 setup active workspace=A -> request.workspace=A。
- `bind-workspace` 备份旧 request 并写入新 workspace。

### 7.4 Source of Truth

- `preview_manifest.review_status=needs_review` 且 `page_tasks.review_status=approved` 时，resolver 必须返回 `needs_review`。
- 只有 `generation_tasks/` 存在但没有 `generation_session.json` 时，resolver 返回 `needs_generation_session`。
- 只有 quality_reports 目录存在但没有 gate 文件时，resolver 返回 `needs_quality_gate`。

### 7.5 Planner Guard

- `production_narrative` + missing claim map -> blocked。
- `fixture_template` + retail fixture -> retail beats allowed。
- `production_narrative` + 医药客户样本样本 -> 不出现库存、配送类页型。
- planner 输出 `planner_mode`、`input_sources` 和 `fallback_reason`。

### 7.6 Studio Guard

- setup not ready -> `POST /api/runs` returns 409。
- setup ready + active workspace -> request.workspace written。
- classic demo mode must set `run_mode=fixture`。
- `/api/setup-status` 和 CLI `setup-status` 口径一致。
- `/api/run-state/<run_id>` 和 CLI `run-state` 口径一致。

### 7.7 Sourcing Override

- missing beat decision -> import fails。
- all beat decisions covered -> import succeeds。
- old sourcing_plan backed up。
- preview_manifest source summary refreshed。
- event log contains `sourcing.override.imported`。

### 7.8 Generation Session

- tool unavailable -> session.status=blocked。
- dry-run -> command prepared but not executed。
- no-execute -> handoff command logged, no external process launched。
- result import -> run id mismatch rejected。
- result import -> preview refreshed。
- result import -> resolver returns `needs_quality_gate`。

### 7.9 Benchmark Gate

- benchmark-report allowed with pending state。
- benchmark-rc-report blocked unless ready_for_benchmark。
- fixture benchmark not eligible for v1.0 RC。

### 7.10 Guided Questions

- answer 写入 conversation answers。
- skip 写入 reason。
- critical question 缺失时 resolver 返回 `needs_guided_answers`。
- workspace guided questions 覆盖默认问题。

## 8. 真实场景 Smoke

以医药客户样本工作坊为 smoke case：

```bash
deck-master setup-status --workspace <local-private-workspace>/healthcare-client-dam
deck-master setup --workspace <local-private-workspace>/healthcare-client-dam --repair-workspace --target codex
deck-master bind-workspace --run-dir <yunnan-run> --workspace <local-private-workspace>/healthcare-client-dam --reason "Migrate pre-v0.9.11 run into workspace-bound chain."
deck-master run-state --run-dir <yunnan-run>
deck-master import-plan --run-dir <yunnan-run> --input <human-plan.md> --source human
deck-master import-sourcing --run-dir <yunnan-run> --input <human-sourcing.json> --source human
deck-master generation-session create --run-dir <yunnan-run> --tool ppt-deck-pro-max
deck-master run-generation --run-dir <yunnan-run> --tool ppt-deck-pro-max --dry-run
deck-master run-state --run-dir <yunnan-run>
```

通过标准：

- run 绑定医药客户样本 workspace。
- `request.json.workspace` 非空。
- `conversation_session.json` 能记录 answers / skips。
- `narrative_plan.json` 与 `page_tasks.json` 来自已导入人工校准版。
- `sourcing_plan.json` 来自已导入 JSON。
- `run-state` 不再同时出现待审和外部生产放行。
- Review Cockpit 显示 workspace、production session、review status 和 quality status。
- benchmark-report 能记录当前 pending 状态。
- benchmark-rc-report 在未 ready 时 blocked。

## 9. 实施顺序

推荐拆成 4 个 PR：

```text
PR 1：Admission & State Core
1. Setup / Workspace Readiness Split
2. Workspace Resolver + Workspace-bound Request
3. deck-master start / doctor
4. Canonical Run State Resolver
5. next-step / orchestration-check / Review Cockpit readiness 接入 resolver
6. Studio Setup Guard

PR 2：Planner & Sourcing Control
7. Production Planner Guard
8. Guided Question minimal runtime
9. import-sourcing / validate-sourcing
10. bind-workspace migration

PR 3：Production Session Bridge
11. Adapt / Generate task semantics
12. Tool registry
13. Generation Session Bridge
14. run-generation dry-run / no-execute / command log
15. import results + preview refresh + quality required

PR 4：Regression & Real Case Smoke
16. 医药客户样本真实 run migration
17. workspace-bound run smoke
18. benchmark harness re-run
19. docs / skill playbook update
```

排序理由：

- 先锁住 setup、workspace 和 run mode，避免后续新能力挂在错误 run 上。
- 再统一 run state，避免 CLI、Cockpit 和 Benchmark 各自判断。
- 然后封住 Studio 绕行入口。
- Planner、sourcing 和 production session 再接入统一状态机。

## 10. 完成定义

v0.9.11 完成时必须满足：

- 本机无 active workspace 时，任何 production run 都无法启动。
- active workspace 会稳定进入 request、planner、page task、sourcing、quality 和 cockpit。
- `next-step`、`orchestration-check`、`run-state` 和 Review Cockpit 展示同一状态。
- 硬编码 retail 模板不会污染 production planner。
- 人工 plan 与 JSON sourcing 校准都能导回 run，并成为唯一可信输入。
- 旧 run 可以通过 `bind-workspace` 迁移到 workspace-bound chain。
- PPT Deck Pro Max 通过 generation session 和 tool registry 受 Deck Master 主控。
- Benchmark 区分 pending report 与 RC readiness。
- 全量测试通过：

```bash
python3 -m unittest discover -s tests
```
