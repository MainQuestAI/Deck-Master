# Deck Master 完整开发 Spec：专业方案叙事生产系统

版本：v0.1  
日期：2026-06-11  
适用仓库：`MainQuestAI/Deck-Master`  
适用范围：从当前 Run OS 实现继续开发到 Deck Master 终局蓝图的连续开发规范  
状态：可作为后续 Codex / Claude Code / OpenCode / Agent 连续开发主控 spec

---

## 0. 文档目的

本 spec 用于把 Deck Master 的终局蓝图、Run OS MVP 确认版方案和当前仓库实现统一成一份可连续开发的工程规范。

它覆盖后续所有开发任务的边界、数据契约、模块职责、CLI/API、状态流、质量门禁、测试矩阵和阶段验收标准。

后续任何开发任务都应遵循以下优先级：

1. 终局蓝图：Deck Master 是专业 Solution Deck 的叙事生产系统。
2. Run OS 契约：每一次 Deck 生产都必须形成可恢复、可审查、可追踪的 run。
3. 数据资产契约：Claim、Evidence、Page Task、Sourcing、Quality、Feedback 必须可沉淀、可迁移、可复用。
4. 人机协作边界：AI 负责整理、规划、检索、生成和质检；用户负责关键判断、审批和最终交付。
5. 工程稳定性：任何坏 JSON、缺文件、工具失败、人工冲突都不得静默覆盖已有产物。

---

## 1. 终局产品定义

### 1.1 一句话定位

Deck Master 是面向售前解决方案架构师、咨询顾问、行业方案团队和专业服务团队的 **专业 Solution Deck 叙事生产系统**。

它把客户上下文、历史方案资产、专家判断、证据材料、页面生产工具、质量门禁和人工审查连接成一个可运行、可追踪、可复用、可持续学习的生产系统。

### 1.2 终局成功状态

用户可以从一次客户上下文出发，在一个可审查生产闭环内，生成证据充分、来源可追踪、视觉一致、质量可控、可继续打磨的客户 Solution Deck。同时，每一次交付都会沉淀为未来可复用的方案资产。

### 1.3 北极星指标

近期指标：

- 从“方案思路基本确认”到“第一版可审查草案”，从约 12 小时压缩到约 2 小时。
- 第一用户是售前解决方案架构师。
- 第一场景是会后客户 Solution Deck 草案。
- 第一批真实样本来自当前用户自己的客户方案工作流。

长期指标：

| 指标 | 定义 | 目标方向 |
|---|---|---|
| 草案产出时间 | 从上下文输入到可审查 draft 的耗时 | 持续降低 |
| 页面通过率 | 人工审查后 approved 页面占比 | 持续提升 |
| 历史页有效复用率 | reuse / adapt 页面进入最终交付的比例 | 持续提升 |
| 证据缺口发现率 | Draft 阶段发现证据缺口的数量和准确性 | 提前发现 |
| 质量问题复发率 | 同类 P0/P1/P2 finding 在后续 run 中的复发率 | 持续降低 |
| 资产沉淀率 | 每次交付新增可复用 claim、evidence、archetype、slide 的数量 | 持续提升 |
| 业务推进信号 | 客户认可、进入下一阶段、报价、SOW、合同等结果信号 | 可追踪 |

### 1.4 产品边界

Deck Master 专注专业客户方案 Deck 的论点、证据、历史资产复用、质量门禁和交付审查。

不做：

- 通用 AI Presentation 生成器。
- 通用 PPT 编辑器。
- 模板市场。
- CRM。
- 通用知识库。
- 长期笔记系统。
- 全功能项目管理系统。
- 单纯 Agent 编排平台。
- 本地桌面 App。
- 移动端主路径。
- 实时飞书拉取首版强依赖。
- reference PPT 自动视觉抽取首版强依赖。
- 多 Build Skill 并行调度首版强依赖。

---

## 2. 系统总架构

Deck Master 终局由 8 个系统域组成。

```text
Deck Workspace
  ├── Context Intelligence
  ├── Solution Narrative Engine
  ├── Claim-Evidence Graph
  ├── Asset Intelligence
  ├── Deck Run OS
  ├── Build Skill Runtime
  ├── Quality & Governance
  └── Review & Decision Cockpit
```

### 2.1 Context Intelligence

把会议转写、客户材料、产品资料、历史方案和用户判断变成结构化项目上下文。

首版边界：只引用本地或已导出的文本型资料。

### 2.2 Solution Narrative Engine

构建 Deck 目标、核心主张、证明路径、章节策略、页面职责和客户决策推进逻辑。

它负责把客户上下文转成“论点—论证—论据—页面职责”的叙事结构。

### 2.3 Claim-Evidence Graph

关联核心论点、支撑逻辑、证据、假设、风险、页面和来源。

`claim_map.json` 是首版起点，后续升级为 `claim_evidence_graph.json`。

### 2.4 Asset Intelligence

管理历史页面、案例、页型、视觉模式、复用记录和交付结果。

首版依赖 PPT Library 或 fixture 返回候选页；后续形成 workspace-level asset graph。

### 2.5 Deck Run OS

管理一次 run 的状态、事件、恢复、工具调用、审批点和中间产物。

这是当前工程底座。所有 CLI、Web UI、Agent 调度都必须基于同一 runtime contract。

### 2.6 Build Skill Runtime

把页面任务交给页面生成、图表生成、架构图生成等生产能力，并回收 artifact。

首版支持一个默认 Build Skill 的状态化执行或 fake executor；不做多工具复杂调度。

### 2.7 Quality & Governance

内建 Draft、Render、Delivery、Evidence、Brand、Confidentiality 等质量门禁。

首版 Draft Gate 是硬链路，Render/Delivery Gate 在有 artifact 时显式运行。

### 2.8 Review & Decision Cockpit

通过 localhost Web UI 支持页面预览、来源审查、质量风险、人工审批和交付判断。

首版是任务唤起式审查面板，不做完整 Web 工作台。

---

## 3. 工程总原则

### 3.1 Run 目录是单次生产的唯一状态源

一次 Deck 生产必须形成 `runs/<run_id>/`。任何中间结果都必须持久化为 run artifact，不允许只存在内存或日志里。

### 3.2 Workspace 是长期资产容器

Workspace 保存视觉规范、页型、历史页面、论点、证据、质量规则、历史 run、导出物和反馈。

Run 属于 workspace，但 run 内部必须可独立审计。

### 3.3 所有阶段必须可恢复

系统必须能根据已有 artifact 判断下一步。

不得要求用户重新跑完整链路才能恢复。

### 3.4 坏 JSON 不得覆盖

如果已有 JSON 无法解析，应写入 error event 并停止相关步骤，不得覆盖坏文件。

### 3.5 字段写入权必须清楚

`page_tasks.json` 必须分层：

- `planning` 由 Planner 写。
- `retrieval` 由 Planner 或 Retrieval 写。
- `sourcing` 由 Sourcing Decision Engine 写。
- `generation` 由 Build Skill Runtime 写。
- `review` 由 Web UI 或人工操作写。
- `quality` 由 Quality Gate 写。

### 3.6 人工操作必须写事件

审批、拒绝、备注、替换来源、转生成页、锁定历史页、override 都必须写入 typed events。

### 3.7 所有输出必须可解释

核心决策都必须有 reason：

- Planner 为什么选这个页面职责。
- Sourcing 为什么 reuse/adapt/generate/manual_placeholder。
- Quality Gate 为什么阻断。
- Export 为什么排除某页。

### 3.8 用户可见文案不得散落硬编码

Web UI 必须有 i18n 资源文件。CLI 错误可以先中文为主，但核心错误码必须结构化。

---

## 4. 标准目录结构

### 4.1 Workspace 目录

```text
deck-workspace/
  workspace_manifest.json
  AGENTS.md
  visual-system/
    design_spec.md
    spec_lock.md
    layout_blueprint.md
    template/
      page_archetypes.md
  structure-assets/
    page_archetypes.md
  quality/
    quality_policy.md
    scoring_rubric.md
    failure_modes.md
    repair_playbooks.md
  sources/
    source_registry.json
  assets/
    slides/
    cases/
    evidence/
    visuals/
  projects/
  runs/
  exports/
  feedback/
    sourcing_outcomes.jsonl
    slide_outcomes.jsonl
    quality_outcomes.jsonl
    delivery_outcomes.jsonl
  reference-analysis/
```

### 4.2 Run 目录

```text
runs/<run_id>/
  request.json
  events.jsonl
  run_state.json
  next_step.json
  context_manifest.json
  conversation_session.json
  deck_brief.json
  consulting_judgments.json
  claim_map.json
  claim_evidence_graph.json
  narrative_plan.json
  page_tasks.json
  library_results/
    selection.json
    selection.raw.json
    by_beat/
  sourcing_plan.json
  generation_tasks/
    index.json
    <task_id>.json
  build_artifacts/
    index.json
  orchestration_plan.json
  preview_manifest.json
  quality_reports/
    draft_gate.json
    draft_gate.md
    render_gate.json
    render_gate.md
    delivery_gate.json
    delivery_gate.md
  approved_queue.json
  delivery_outcome.json
  links/
  notes/
  placeholders/
```

首版可缺少部分未来文件，但 runtime 必须知道它们的 intended lifecycle。

---

## 5. Spec 00：迁移保护与仓库对齐

### 5.1 目标

在新增终局能力之前，先保护当前 main 上已有可运行能力，形成迁移清单，避免误删或破坏已有 autoplan、guided conversation、quality gate、preview、export 能力。

### 5.2 当前能力分类

必须保留并硬化：

- `scripts/deck_master.py` CLI 主入口。
- `start-conversation` / `build-brief` / `build-claim-map`。
- `autoplan` 从 brief 或已有 run 续跑到 preview。
- 分层 `page_tasks.json`。
- PPT Library fixture fallback。
- `reuse / adapt / generate / manual_placeholder` 来源决策。
- generation task package。
- `preview_manifest.json`。
- Web UI 预览和审批回写。
- `quality-gate draft/render/delivery`。
- approved queue export。

需要重构：

- events schema 与 typed events 对齐。
- `run_status` 升级为 canonical `next_step` resolver。
- `source_decision` 与 `decision` 字段统一。
- Preview manifest 中审批状态和页面动作分离。
- Export 接入 Quality Gate 阻断。
- Workspace 被 Planner / Quality Gate 真实读取。

可以延后：

- 多 Build Skill 调度。
- 长期知识库。
- reference PPT 自动视觉分析。
- 真实多用户权限。
- 企业级集成。

### 5.3 产出

新增：

```text
docs/migration/2026-06-run-os-migration-map.md
```

内容：

- 保留模块。
- 重构模块。
- 删除候选。
- 兼容字段。
- 迁移风险。
- 回归命令。

### 5.4 验收

- 迁移前后 `autoplan --library-mode fixture` 仍能生成 preview。
- `start-conversation → build-brief → build-claim-map → autoplan → quality-gate draft` smoke test 通过。
- 旧 preview manifest 至少能被读取或被迁移器转换。

---

## 6. Spec 01：Workspace Foundation

### 6.1 目标

创建或注册一个 Deck Workspace，使其成为长期方案资产容器。

首版必须做到：Workspace 是能被 Planner、Quality Gate、Sourcing 和 Build Skill 读取的资产容器。

### 6.2 CLI

```bash
python3 scripts/deck_master.py init-workspace \
  --workspace /path/to/deck-workspace \
  --name "MarketingForce PPT Workshop" \
  --reference-ppt /path/to/reference.pptx
```

```bash
python3 scripts/deck_master.py register-workspace \
  --workspace /path/to/existing-workshop \
  --name "MarketingForce PPT Workshop"
```

```bash
python3 scripts/deck_master.py validate-workspace \
  --workspace /path/to/deck-workspace
```

### 6.3 `workspace_manifest.json` schema

```json
{
  "schema_version": "deck_workspace.v1",
  "workspace_id": "marketingforce-ppt-workshop",
  "name": "MarketingForce PPT Workshop",
  "description": "",
  "created_at": "2026-06-11T00:00:00Z",
  "updated_at": "2026-06-11T00:00:00Z",
  "version": 1,
  "paths": {
    "visual_system": "visual-system/",
    "structure_assets": "structure-assets/",
    "quality": "quality/",
    "sources": "sources/",
    "runs": "runs/",
    "exports": "exports/",
    "feedback": "feedback/"
  },
  "visual_system": {
    "design_spec": "visual-system/design_spec.md",
    "spec_lock": "visual-system/spec_lock.md",
    "layout_blueprint": "visual-system/layout_blueprint.md"
  },
  "structure_assets": {
    "page_archetypes": "structure-assets/page_archetypes.md"
  },
  "quality": {
    "policy": "quality/quality_policy.md",
    "scoring_rubric": "quality/scoring_rubric.md",
    "failure_modes": "quality/failure_modes.md",
    "repair_playbooks": "quality/repair_playbooks.md"
  },
  "references": [
    {
      "reference_id": "ref_001",
      "kind": "reference_ppt",
      "path": "/path/to/reference.pptx",
      "filename": "reference.pptx",
      "size_bytes": 123456,
      "modified_at": "2026-06-11T00:00:00Z",
      "note": "metadata only in v1"
    }
  ],
  "include_rules": [],
  "exclude_rules": ["exports/**", "runs/**", ".git/**"],
  "default_output": "exports/"
}
```

### 6.4 Starter 文件

`visual-system/design_spec.md` 必须包含：

- canvas size。
- safe area。
- font policy。
- color palette。
- component style。
- density guidance。
- screenshot policy。
- chart policy。
- pending_manual_review 字段。

`structure-assets/page_archetypes.md` 必须包含初始页型：

- cover
- agenda
- executive_summary
- problem
- business_context
- solution_overview
- architecture
- capability_matrix
- process_flow
- case_study
- roadmap
- roi
- risk_control
- closing

每个 archetype 至少包含：

```yaml
archetype_id: architecture
name: 目标架构页
best_for:
  - 系统建设方案
  - 数字化转型方案
page_role: architecture
required_modules:
  - 业务域
  - 能力层
  - 数据流
  - 集成关系
evidence_pattern:
  - 客户现状
  - 目标能力
  - 数据流或接口关系
visual_pattern: layered_architecture
density_target: high
avoid:
  - 只画平台层，不说明业务价值
example_refs: []
```

### 6.5 Planner 接入要求

Planner 必须读取 workspace：

- page archetypes。
- density standard。
- quality policy。
- visual constraints。

并写入 page task：

```json
{
  "planning": {
    "preferred_archetype": "architecture",
    "workspace_refs": ["structure-assets/page_archetypes.md#architecture"],
    "style_constraints": ["visual-system/spec_lock.md"],
    "quality_requirements": ["页面必须有主观点", "证据必须和主观点对应"]
  }
}
```

### 6.6 验收

- 新 workspace 可创建。
- 旧文件夹可注册。
- 缺少标准文件时 `validate-workspace` 输出 pending/manual review，不崩溃。
- 同一 brief 在有 workspace 时，`page_tasks.json` 写入 `workspace_refs`。
- 无 workspace 时使用默认 archetypes。

---

## 7. Spec 02：Runtime Core、Typed Events 与 Next Step

### 7.1 目标

建立 Deck Master 的 canonical runtime contract，使 CLI、Web UI、Agent 都基于同一状态解释。

### 7.2 核心模块

建议新增或重构：

```text
scripts/runtime/
  run_state.py
  events.py
  next_step.py
  schema.py
  migrations.py
  artifact_lock.py
```

### 7.3 Event schema

当前事件可兼容 `actor/action/status/target/payload_ref/error/data`，但 canonical event 必须新增：

```json
{
  "schema_version": "deck_event.v1",
  "timestamp": "2026-06-11T00:00:00Z",
  "event_id": "evt_20260611000000_0001",
  "event_type": "step_completed",
  "run_id": "retail-conversation",
  "step": "sourcing",
  "message": "Sourcing decision completed for 14 pages.",
  "refs": ["sourcing_plan.json"],
  "severity": "info",
  "actor": "deck_master",
  "action": "sourcing.plan.created",
  "status": "ok",
  "target": "sourcing_plan.json",
  "payload_ref": "sourcing_plan.json",
  "error": "",
  "data": {}
}
```

### 7.4 Event types

| event_type | 用途 |
|---|---|
| `run_created` | 创建 run |
| `step_started` | 步骤开始 |
| `step_completed` | 步骤完成 |
| `tool_call` | 外部工具调用 |
| `tool_result` | 外部工具结果 |
| `decision` | planner、sourcing、quality、export 决策 |
| `manual_action` | 用户审批、拒绝、备注、替换、锁定、override |
| `warning` | 可恢复问题 |
| `error` | 阻断问题 |

### 7.5 `next_step.json` schema

```json
{
  "schema_version": "deck_next_step.v1",
  "run_id": "retail-conversation",
  "status": "draft_gate_blocked",
  "current_step": "draft_gate",
  "next_step": "review_draft_gate_findings",
  "can_continue": true,
  "blocking": true,
  "blocking_reasons": [
    {
      "severity": "P1",
      "message": "3 pages missing evidence.",
      "refs": ["quality_reports/draft_gate.json"]
    }
  ],
  "available_actions": [
    "open_web_ui",
    "repair_page_tasks",
    "rerun_draft_gate"
  ],
  "artifact_status": {
    "request.json": "ok",
    "deck_brief.json": "ok",
    "claim_map.json": "ok",
    "narrative_plan.json": "ok",
    "page_tasks.json": "ok",
    "preview_manifest.json": "ok"
  },
  "updated_at": "2026-06-11T00:00:00Z"
}
```

### 7.6 Next-step resolution rules

| 条件 | next_step |
|---|---|
| `request.json` 缺失 | `create_request` |
| `context_manifest.json` 缺失且 run 来自 context | `build_context_manifest` |
| `conversation_session.json` 缺失且 context 存在 | `start_conversation` |
| `deck_brief.json` 缺失 | `build_brief` |
| `claim_map.json` 缺失 | `build_claim_map` |
| `narrative_plan.json` 缺失 | `plan_narrative` |
| `page_tasks.json` 缺失 | `build_page_tasks` |
| `library_results/selection.json` 缺失 | `search_library` |
| `sourcing_plan.json` 缺失 | `decide_sourcing` |
| `generation_tasks/index.json` 缺失 | `create_generation_tasks` |
| `preview_manifest.json` 缺失 | `build_preview` |
| `quality_reports/draft_gate.json` 缺失 | `run_draft_gate` |
| Draft Gate 有 P0/P1 或 `rework_required` | `review_draft_gate_findings` |
| 有待审页面 | `open_review_cockpit` |
| 有 approved 页面 | `export_approved_queue` |
| 已导出但无 delivery outcome | `record_delivery_outcome` |

### 7.7 CLI

```bash
python3 scripts/deck_master.py status --run-id <run_id>
python3 scripts/deck_master.py next-step --run-id <run_id>
python3 scripts/deck_master.py resume --run-id <run_id> --through preview
python3 scripts/deck_master.py validate-run --run-id <run_id>
```

### 7.8 验收

- CLI 和 Web UI 读取同一个 `next_step`。
- 坏 JSON 生成 error event，不覆盖源文件。
- 缺文件时给出明确下一步。
- 失败步骤可以重跑。
- 旧 events 仍可读取，新 events 使用 canonical fields。

---

## 8. Spec 03：Context Intelligence 与 Guided Conversation

### 8.1 目标

把本地或已导出的客户上下文变成可追踪、可引用、可摘要的 run 输入。

首版只接 text-like 文件：`.md`、`.txt`、`.json`、`.csv`、`.tsv`。

### 8.2 CLI

```bash
python3 scripts/deck_master.py start-conversation \
  --workspace /path/to/deck-workspace \
  --context-file examples/context/retail_meeting_transcript.txt \
  --context-file examples/context/client_material_summary.md \
  --industry retail \
  --run-id retail-conversation
```

### 8.3 `context_manifest.json` schema

```json
{
  "schema_version": "deck_context_manifest.v1",
  "run_id": "retail-conversation",
  "workspace": "/path/to/deck-workspace",
  "strategy": "runtime_reference",
  "sources": [
    {
      "source_id": "a1b2c3d4e5f6g7h8",
      "path": "/abs/path/to/transcript.txt",
      "name": "transcript.txt",
      "kind": "meeting_transcript",
      "mime_type": "text/plain",
      "size_bytes": 12345,
      "sha256": "...",
      "summary": "...",
      "excerpt": "...",
      "created_at": "",
      "modified_at": ""
    }
  ],
  "summary": "combined summary",
  "constraints": [
    "Deck Master references local/exported context only.",
    "No realtime Feishu pull or long-term note storage is performed."
  ]
}
```

### 8.4 source kind

必须支持：

- `meeting_transcript`
- `client_material`
- `historical_solution`
- `product_material`
- `knowledge_export`
- `user_judgment`
- `local_document`

### 8.5 `conversation_session.json` schema

```json
{
  "schema_version": "deck_conversation_session.v1",
  "run_id": "retail-conversation",
  "mode": "guided_deck_conversation",
  "status": "draft",
  "context_refs": ["source_001"],
  "locked_decisions": {
    "audience": "client",
    "industry": "retail",
    "business_goal": "...",
    "context_strategy": "runtime_reference",
    "first_output": "reviewable_deck_draft"
  },
  "questions": [
    {
      "question_id": "audience_goal",
      "prompt": "这份 Deck 面向谁？他们看完后需要做什么决定？",
      "purpose": "锁定受众、决策场景和表达深度。"
    }
  ],
  "answers": [],
  "notes": []
}
```

### 8.6 首版引导问题

至少包含：

1. 这份 Deck 面向谁？他们看完后需要做什么决定？
2. 如果只能让对方记住一个判断，这个判断是什么？
3. 哪些案例、截图、数据或客户原话可以证明这个判断？
4. 哪些历史方案页、业务模型或框架值得复用？
5. 哪些内容应该删掉或放进附录？

### 8.7 验收

- 多个 context file 可生成 manifest。
- source_id 基于内容 hash 稳定生成。
- 不支持文件类型必须明确报错。
- conversation session 记录 context refs。
- 不写入长期知识库。

---

## 9. Spec 04：Deck Brief 与 Consulting Judgment Layer

### 9.1 目标

把上下文和引导式对话整理为稳定的 Deck 目标、受众、业务目标、核心观点和边界，并把关键专业判断结构化。

### 9.2 CLI

```bash
python3 scripts/deck_master.py build-brief --run-id <run_id>
python3 scripts/deck_master.py build-judgments --run-id <run_id>
```

### 9.3 `deck_brief.json` schema

```json
{
  "schema_version": "deck_brief.v1",
  "run_id": "retail-conversation",
  "project_name": "Retail Digital Transformation Deck",
  "audience": "client",
  "industry": "retail",
  "business_goal": "让客户认可全渠道库存可视化和履约闭环建设的必要性。",
  "decision_goal": "推动客户同意进入方案深化和 PoC 评估。",
  "core_points": [
    "库存可视化直接服务履约效率和客户体验，避免被理解为报表项目。"
  ],
  "must_cover_topics": ["全渠道", "库存可视化", "最后一公里配送"],
  "source_refs": ["source_001"],
  "style_preference": "consulting-style, evidence-backed",
  "target_pages": "auto",
  "boundaries": [
    "输出第一版可审查客户方案 Deck 草案。",
    "优先做论点、论证、论据和证据链。",
    "上下文只做运行时引用。"
  ],
  "language": "zh-CN"
}
```

### 9.4 `consulting_judgments.json` schema

```json
{
  "schema_version": "deck_consulting_judgments.v1",
  "run_id": "retail-conversation",
  "judgments": [
    {
      "judgment_id": "judgment_001",
      "judgment": "客户当前的核心问题是跨渠道履约状态闭环薄弱，库存看板只是表层呈现。",
      "why_it_matters": "这决定方案主线应从业务履约效率切入，避免从单点报表能力切入。",
      "supporting_evidence": ["source_001#quote_003"],
      "confidence": 0.72,
      "assumptions": ["客户愿意开放门店、仓、渠道订单数据"],
      "risks": ["缺少当前库存准确率数据"],
      "deck_implication": "前 5 页优先建立业务闭环和现状痛点，再讲系统能力。"
    }
  ]
}
```

### 9.5 实现要求

- `deck_brief` 只能写相对稳定的 Deck 级目标。
- 临时判断、假设、推断写入 `consulting_judgments`，不得混在 brief 文本中。
- 每个 judgment 必须有 `deck_implication`，否则不能被 Planner 使用。

### 9.6 验收

- brief 中必须有 business_goal。
- 至少能从 context summary 或用户 brief 中生成 core_points。
- judgment 缺证据时写 risk，不得伪造 evidence。
- Planner 能读取 judgment 影响章节或页面策略。

---

## 10. Spec 05：Claim-Evidence Graph

### 10.1 目标

将 `claim_map.json` 升级为可持续演进的 Claim-Evidence Graph，使每页都能回答“证明哪个主张、使用哪些证据、缺什么证据”。

首版可以同时生成：

- `claim_map.json`：兼容当前代码。
- `claim_evidence_graph.json`：新增终局模型。

### 10.2 CLI

```bash
python3 scripts/deck_master.py build-claim-map --run-id <run_id>
python3 scripts/deck_master.py build-claim-graph --run-id <run_id>
```

### 10.3 `claim_map.json` schema

```json
{
  "schema_version": "deck_claim_map.v1",
  "run_id": "retail-conversation",
  "title": "Retail Digital Transformation Deck",
  "claims": [
    {
      "claim_id": "claim_001",
      "claim": "库存可视化需要打通门店、仓、渠道和配送履约状态。",
      "why_it_matters": "该判断支撑客户从单点库存看板升级到履约闭环。",
      "supporting_arguments": [
        "库存状态分散导致用户承诺不稳定。",
        "履约状态缺失会影响到店、自提、配送体验。"
      ],
      "evidence_needed": ["客户现有库存链路", "系统截图", "履约指标"],
      "evidence_refs": ["evidence_001"],
      "risk_flags": []
    }
  ],
  "source_refs": ["source_001"],
  "risk_flags": []
}
```

### 10.4 `claim_evidence_graph.json` schema

```json
{
  "schema_version": "deck_claim_evidence_graph.v1",
  "run_id": "retail-conversation",
  "claims": [],
  "evidence": [
    {
      "evidence_id": "evidence_001",
      "kind": "meeting_quote",
      "summary": "客户提到门店库存和线上库存不一致。",
      "source_ref": "source_001",
      "quote": "",
      "confidence": 0.8,
      "client_visible": true,
      "risk_flags": []
    }
  ],
  "assumptions": [
    {
      "assumption_id": "assumption_001",
      "text": "客户具备门店库存数据导出能力。",
      "needs_confirmation": true,
      "risk_flags": ["needs_client_confirmation"]
    }
  ],
  "risks": [
    {
      "risk_id": "risk_001",
      "severity": "P2",
      "kind": "evidence_gap",
      "message": "缺少当前库存准确率数据。",
      "refs": ["claim_001"]
    }
  ],
  "page_claim_links": [],
  "evidence_page_links": [],
  "source_refs": []
}
```

### 10.5 Evidence kinds

必须支持：

- `meeting_quote`
- `client_document`
- `product_screenshot`
- `case_study`
- `metric`
- `historical_slide`
- `external_reference`
- `user_judgment`
- `ai_inference`

`ai_inference` 不得默认 client-visible。

### 10.6 风险规则

如果 claim 没有 evidence：

- 写 `evidence_gap`。
- Draft Gate 至少输出 P1 或 P2 finding，取决于页面重要性。

如果 evidence 来自 AI 推断：

- 写 `needs_confirmation`。
- 不得作为强证据支撑最终交付。

### 10.7 验收

- 每个 core point 至少生成一个 claim。
- 每个 claim 有 evidence_needed。
- context 中识别出的证据成为 evidence object。
- page_tasks 生成后补 page_claim_links。
- Draft Gate 能引用 claim/evidence 风险。

---

## 11. Spec 06：Solution Narrative Engine 与 Page Tasks

### 11.1 目标

生成 Deck 级叙事结构和页面级任务，使每页都有明确页面职责、核心主张、证据需求、视觉意图、页型和客户决策推进作用。

### 11.2 CLI

```bash
python3 scripts/deck_master.py plan --run-id <run_id>
python3 scripts/deck_master.py build-page-tasks --run-id <run_id>
```

`autoplan` 内部必须调用同一 planner pipeline，不得另写逻辑。

### 11.3 `narrative_plan.json` schema

```json
{
  "schema_version": "deck_narrative_plan.v1",
  "run_id": "retail-conversation",
  "title": "Retail Digital Transformation Deck",
  "target_pages": 15,
  "density": "medium_high",
  "industry": "retail",
  "audience": "client",
  "deck_strategy": {
    "core_thesis": "库存可视化应服务全渠道履约闭环。",
    "decision_goal": "推动客户进入方案深化。",
    "section_strategy": [
      {
        "section_id": "section_01",
        "title": "为什么现在需要升级",
        "role": "context_and_problem",
        "page_range": [1, 4]
      }
    ]
  },
  "beats": [
    {
      "beat_id": "beat_004_architecture",
      "order": 4,
      "section_id": "section_02",
      "page_title": "库存可视化目标架构",
      "role": "architecture",
      "core_claim": "库存可视化需要打通门店、仓、渠道和配送履约状态。",
      "content_goal": "说明目标架构和关键数据流。",
      "decision_intent": "让客户认可这是履约闭环项目，避免被理解为单点看板项目。",
      "argument_chain": {
        "why_now": "客户全渠道订单和履约方式复杂度上升。",
        "business_tension": "门店、仓、渠道、配送状态割裂。",
        "solution_logic": "通过统一库存状态和履约状态建模实现可视化和决策闭环。",
        "proof_needed": "客户现有链路、库存状态样例、履约指标。"
      },
      "evidence_need": ["系统截图", "库存状态样例", "履约指标"],
      "evidence_policy": {
        "required": true,
        "evidence_types": ["client_document", "product_screenshot", "metric"],
        "allow_ai_generated_without_evidence": false
      },
      "visual_need": "分层架构图",
      "density": "high",
      "preferred_archetype": "architecture",
      "customer_specificity_level": "customer_specific",
      "reuse_query": "retail inventory visibility architecture omnichannel fulfillment",
      "generation_brief": "生成一页库存可视化目标架构页...",
      "approval_required": true,
      "gaps": []
    }
  ]
}
```

### 11.4 `page_tasks.json` schema

```json
{
  "schema_version": "deck_page_tasks.v1",
  "run_id": "retail-conversation",
  "title": "Retail Digital Transformation Deck",
  "tasks": [
    {
      "beat_id": "beat_004_architecture",
      "order": 4,
      "planning": {
        "page_title": "库存可视化目标架构",
        "role": "architecture",
        "core_claim": "库存可视化需要打通门店、仓、渠道和配送履约状态。",
        "decision_intent": "让客户认可这是履约闭环项目。",
        "content_goal": "说明目标架构和关键数据流。",
        "argument_chain": {},
        "evidence_need": ["系统截图", "库存状态样例", "履约指标"],
        "evidence_policy": {},
        "visual_need": "分层架构图",
        "density": "high",
        "preferred_archetype": "architecture",
        "customer_specificity_level": "customer_specific",
        "workspace_refs": ["structure-assets/page_archetypes.md#architecture"],
        "style_constraints": ["visual-system/spec_lock.md"],
        "quality_requirements": ["必须有主观点", "必须说明数据如何服务决策"],
        "gaps": []
      },
      "retrieval": {
        "reuse_query": "retail inventory visibility architecture omnichannel fulfillment",
        "constraints": ["avoid generic platform overview"]
      },
      "sourcing": {
        "decision": null,
        "selected_candidate": null,
        "alternatives": [],
        "score_breakdown": null,
        "risk_flags": [],
        "confidence": null
      },
      "generation": {
        "generation_brief": "生成一页库存可视化目标架构页...",
        "reference_slide": null,
        "task_path": null,
        "status": "pending"
      },
      "review": {
        "review_status": "needs_review",
        "review_note": "",
        "action_intent": "none",
        "locked": false
      },
      "quality": {
        "status": "not_run",
        "findings": []
      }
    }
  ]
}
```

### 11.5 页数策略

| target_pages | 策略 |
|---|---|
| `auto` | 12–18 页 |
| `15` | 高管摘要和紧凑方案 |
| `30` | 完整 Solution Deck |
| `60+` | 章节化长 deck，强化 section handoff |

### 11.6 页面角色

首版至少支持：

- cover
- agenda
- executive_summary
- business_context
- problem
- insight
- solution_overview
- architecture
- capability_matrix
- process_flow
- case_study
- roadmap
- roi
- risk_control
- closing
- appendix

### 11.7 验收

- 每页必须有 `core_claim`。
- 每页必须有 `decision_intent`。
- Evidence-heavy 页面必须有 `evidence_policy.required = true`。
- 缺客户事实必须写入 `gaps`。
- 长 Deck 必须有 section handoff。
- page_tasks 必须分层，不得写回平铺 sourcing 字段。

---

## 12. Spec 07：PPT Library 集成与 Asset Intelligence 起点

### 12.1 目标

从历史方案资产中检索候选页，并为每个 beat 提供可解释候选集合。

首版 Deck Master 不负责深度索引 PPT，但负责调用 PPT Library、解析结果、降级处理和保存候选。

### 12.2 CLI 调用

主调用：

```bash
ppt-lib select-slides \
  --plan <run>/narrative_plan.json \
  --brief <run>/request.json \
  --ranking business \
  --max-per-role 5 \
  --output <run>/library_results/selection.json
```

备用调用：

```bash
ppt-lib search "<reuse_query>" \
  --top-k 8 \
  --ranking business \
  --output json
```

### 12.3 `library_results/selection.json` schema

```json
{
  "schema_version": "deck_library_selection.v1",
  "run_id": "retail-conversation",
  "source": "ppt_library",
  "tool_status": "ok",
  "by_beat": {
    "beat_004_architecture": [
      {
        "candidate_id": "slide_123",
        "slide_id": "slide_123",
        "canonical_slide_id": "canonical_abc",
        "beat_id": "beat_004_architecture",
        "title": "历史页：库存目标架构",
        "text_summary": "...",
        "source_file": "/path/to/history.pptx",
        "page_number": 12,
        "screenshot_path": "/path/to/screenshot.png",
        "confidence": 0.82,
        "score": 0.82,
        "win_rate": 0.67,
        "reuse_count": 3,
        "narrative_role": "architecture",
        "page_role": "architecture",
        "archetype_id": "architecture",
        "evidence_tags": ["architecture", "system_flow"],
        "visual_tags": ["layered_architecture"],
        "risk_flags": []
      }
    ]
  }
}
```

### 12.4 失败行为

| 情况 | 行为 |
|---|---|
| CLI 缺失 | 写 warning event，使用 fixture 或空结果 |
| CLI 返回非 0 | real mode 抛错，auto mode fallback |
| JSON 错误 | 写 parse error，继续 generate/manual fallback |
| 无结果 | 写空列表，不跳过 beat |
| 截图缺失 | 保留候选，增加 `missing_screenshot` |
| embedding 不可用 | 写 dependency failure，继续 |

### 12.5 Asset Intelligence 后续字段

候选页后续应支持：

- `claim_supported`
- `evidence_type`
- `customer_context`
- `visual_pattern`
- `approval_history`
- `delivery_outcome`
- `last_used_at`
- `source_confidentiality`

### 12.6 验收

- 每个 beat 都有 by_beat key。
- 无结果也写空数组。
- fixture 可稳定生成候选。
- screenshot 缺失不导致中断。
- 解析字段写入 canonical candidate。

---

## 13. Spec 08：Sourcing Decision Engine

### 13.1 目标

为每个页面选择唯一主来源策略：`reuse`、`adapt`、`generate`、`manual_placeholder`。

### 13.2 输入

- `narrative_plan.json`
- `page_tasks.json`
- `library_results/selection.json`
- `claim_evidence_graph.json`
- Workspace visual and quality standards

### 13.3 输出 `sourcing_plan.json`

```json
{
  "schema_version": "deck_sourcing_plan.v1",
  "run_id": "retail-conversation",
  "title": "Retail Digital Transformation Deck",
  "source": "ppt_library",
  "decisions": [
    {
      "beat_id": "beat_004_architecture",
      "order": 4,
      "page_title": "库存可视化目标架构",
      "role": "architecture",
      "decision": "adapt",
      "source_decision": "adapt",
      "decision_reason": "历史页结构匹配架构表达，但客户语境和证据需调整。",
      "selected_candidate": {},
      "alternatives": [],
      "score": 0.66,
      "score_breakdown": {
        "semantic_match": 0.72,
        "narrative_role_match": 0.80,
        "archetype_match": 0.74,
        "screenshot_availability": 1.0,
        "source_credibility": 0.6,
        "win_rate": 0.67,
        "reuse_count": 0.6,
        "customer_context_conflict": 0.2,
        "visual_continuity": 0.5,
        "evidence_sufficiency": 0.4
      },
      "risk_flags": ["needs_customer_context_rewrite"],
      "confidence": 0.66,
      "tool_refs": {
        "library_results": "library_results/by_beat/beat_004_architecture.json"
      }
    }
  ]
}
```

### 13.4 决策类型

| 决策 | 定义 |
|---|---|
| `reuse` | 历史页高匹配，可直接进入审批 |
| `adapt` | 历史页结构或素材可复用，但需调整客户语境、标题、论据或视觉 |
| `generate` | 历史候选不足，且无必需证据缺口，可新生成 |
| `manual_placeholder` | 缺必需客户事实、截图、数据、案例或证据，必须人工补充 |

### 13.5 初始权重

| 维度 | 权重 |
|---|---:|
| semantic_match | 0.30 |
| narrative_role_match | 0.18 |
| archetype_match | 0.10 |
| screenshot_availability | 0.10 |
| source_credibility | 0.08 |
| win_rate | 0.10 |
| reuse_count | 0.04 |
| customer_context_conflict | -0.12 |
| visual_continuity | 0.06 |
| evidence_sufficiency | 0.06 |

### 13.6 初始阈值

| 决策 | 条件 |
|---|---|
| `reuse` | score >= 0.78，截图可用，无高客户语境冲突 |
| `adapt` | score >= 0.58，且 archetype_match 或 narrative_role_match >= 0.70 |
| `generate` | score < 0.58，且没有必需证据缺口 |
| `manual_placeholder` | 缺必需客户事实、截图、数据或案例证据 |

### 13.7 tie-break

- 分差小于 0.05 时优先 narrative_role_match。
- 分差小于 0.05 时 win_rate 高者优先。
- 分差小于 0.08 时有 screenshot 者优先。
- 存在高客户语境冲突时，`reuse` 降级为 `adapt`。

### 13.8 写回 page_tasks

Sourcing 完成后必须同步写入 page_tasks 中的 `sourcing` 分层：

```json
{
  "sourcing": {
    "decision": "adapt",
    "selected_candidate": {},
    "alternatives": [],
    "score_breakdown": {},
    "risk_flags": [],
    "confidence": 0.66
  }
}
```

### 13.9 验收

- 每页唯一主决策。
- 每个决策都有 reason。
- 手工证据缺口不允许变成 generate。
- 高匹配但缺截图不得直接 reuse。
- Context conflict 会 downgrade。
- 同一输入 deterministic。

---

## 14. Spec 09：Build Skill Runtime

### 14.1 目标

将 `adapt` 和 `generate` 页面任务交给生成能力，并把 artifact 状态回写 run。

首版可以支持 fake executor，但 contract 必须真实。

### 14.2 Registry

Workspace 默认配置：

```json
{
  "schema_version": "deck_build_skill_registry.v1",
  "default_skill": "ppt_deck_pro_max",
  "skills": [
    {
      "skill_id": "ppt_deck_pro_max",
      "name": "PPT Deck Pro Max",
      "kind": "slide_builder",
      "command": "ppt-deck-pro-max",
      "enabled": true,
      "supports": ["adapt", "generate"],
      "artifact_types": ["pptx", "svg", "html", "png"]
    }
  ]
}
```

### 14.3 Generation task schema

```json
{
  "schema_version": "deck_generation_task.v1",
  "task_id": "generation_004_beat_004_architecture",
  "beat_id": "beat_004_architecture",
  "page_title": "库存可视化目标架构",
  "role": "architecture",
  "core_claim": "...",
  "decision_intent": "...",
  "source_decision": "adapt",
  "generation_brief": "...",
  "reference_slide": {},
  "preferred_archetype": "architecture",
  "visual_need": "分层架构图",
  "evidence_need": ["系统截图"],
  "style_constraints": ["visual-system/spec_lock.md"],
  "workspace_refs": ["structure-assets/page_archetypes.md#architecture"],
  "quality_requirements": [],
  "status": "pending",
  "created_at": "2026-06-11T00:00:00Z",
  "updated_at": "2026-06-11T00:00:00Z"
}
```

### 14.4 Artifact handback schema

```json
{
  "schema_version": "deck_build_artifact.v1",
  "task_id": "generation_004_beat_004_architecture",
  "beat_id": "beat_004_architecture",
  "artifact_type": "svg",
  "artifact_path": "build_artifacts/beat_004/page.svg",
  "preview_path": "build_artifacts/beat_004/page.svg",
  "source_decision": "adapt",
  "build_tool": "ppt_deck_pro_max",
  "status": "completed",
  "created_at": "2026-06-11T00:00:00Z",
  "errors": []
}
```

### 14.5 CLI

```bash
python3 scripts/deck_master.py create-generation-tasks --run-id <run_id>
python3 scripts/deck_master.py run-build-skill --run-id <run_id> --task-id <task_id>
python3 scripts/deck_master.py ingest-build-artifact --run-id <run_id> --artifact /path/to/artifact.json
```

### 14.6 状态值

- `pending`
- `running`
- `completed`
- `failed`
- `skipped`
- `cancelled`

### 14.7 失败规则

- 单页失败不得中断其他页面 preview。
- 失败必须写 event。
- preview_manifest 中对应页显示 failed 状态。
- failed 页不得进入最终 export，除非手工 override。

### 14.8 验收

- `adapt` 和 `generate` 页面生成 task。
- `reuse` 页面不生成 task。
- `manual_placeholder` 页面生成内部提醒，不生成 client-facing artifact。
- fake executor 可生成 placeholder artifact。
- artifact handback 可刷新 preview manifest。

---

## 15. Spec 10：Preview Manifest 与 Review Cockpit API

### 15.1 目标

形成 Web UI 可读取、可审查、可回写的页面状态源。

### 15.2 Preview manifest schema

```json
{
  "schema_version": "deck_preview_manifest.v1",
  "run_id": "retail-conversation",
  "title": "Retail Digital Transformation Deck",
  "status": "draft",
  "updated_at": "2026-06-11T00:00:00Z",
  "pages": [
    {
      "page_id": "beat_004_architecture",
      "beat_id": "beat_004_architecture",
      "order": 4,
      "title": "库存可视化目标架构",
      "source_type": "library_slide",
      "source_decision": "adapt",
      "preview_path": "links/beat_004_architecture.svg",
      "source_preview_asset": "/abs/path/to/original.svg",
      "narrative_role": "architecture",
      "core_claim": "...",
      "decision_intent": "...",
      "decision_reason": "...",
      "confidence": 0.66,
      "selected_candidate": {},
      "alternatives": [],
      "risk_flags": [],
      "quality_status": "conditional_pass",
      "quality_findings": [],
      "generation_task": {},
      "review_status": "needs_review",
      "review_note": "",
      "action_intent": "none",
      "locked": false,
      "reviewed_at": ""
    }
  ]
}
```

### 15.3 兼容规则

旧字段：

```json
"decision": "needs_review"
```

应迁移为：

```json
"review_status": "needs_review"
```

旧值兼容：

| 旧 decision | 新 review_status | 新 action_intent |
|---|---|---|
| `needs_review` | `needs_review` | `none` |
| `approved` | `approved` | `none` |
| `keep` | `approved` | `none` |
| `replace` | `needs_review` | `replace_source` |

### 15.4 Review API

首版 API：

```http
GET /api/runs
POST /api/runs
GET /api/deck?run_id=<run_id>
GET /api/page/<page_id>?run_id=<run_id>
POST /api/page/<page_id>/review?run_id=<run_id>
POST /api/page/<page_id>/replace-source?run_id=<run_id>
POST /api/page/<page_id>/convert-to-generate?run_id=<run_id>
POST /api/page/<page_id>/lock-source?run_id=<run_id>
GET /api/quality?run_id=<run_id>
POST /api/export?run_id=<run_id>
```

### 15.5 Review request

```json
{
  "review_status": "approved",
  "review_note": "这页结构可用，后续补客户截图。"
}
```

### 15.6 Replace source request

```json
{
  "candidate_id": "slide_456",
  "reason": "候选页更贴近客户行业。"
}
```

### 15.7 Convert to generate request

```json
{
  "reason": "历史页语境不适合，改为新生成。",
  "generation_brief_patch": "强调门店、仓、渠道三类库存状态。"
}
```

### 15.8 Lock source request

```json
{
  "locked": true,
  "reason": "用户明确要求使用该历史页结构。"
}
```

### 15.9 验收

- 页面列表按 order 排序。
- 每页显示 source decision、quality findings、risk flags、generation status。
- 审批、拒绝、备注写回 manifest。
- 替换来源、转生成、锁定历史页写 event。
- 页面操作不能绕过 Draft Gate 阻断。

---

## 16. Spec 11：Quality & Governance

### 16.1 目标

把质量控制作为 Deck Master 内建子系统，纳入主运行链路。

### 16.2 Gate 类型

| Gate | 触发点 | 首版策略 |
|---|---|---|
| Draft Gate | `narrative_plan.json` 与 `page_tasks.json` 存在后 | 默认硬链路 |
| Render Gate | HTML/SVG/PPTX 预览资产存在后 | 显式 artifact check |
| Delivery Gate | export queue 或最终 PPTX 存在后 | 显式 artifact check |
| Evidence Gate | Claim-Evidence Graph 完成后 | 阶段 2 |
| Brand Gate | 视觉系统稳定后 | 阶段 4 |
| Confidentiality Gate | 交付前 | 阶段 4 |

### 16.3 Quality report schema

```json
{
  "schema_version": "deck_quality_report.v1",
  "run_id": "retail-conversation",
  "gate": "draft",
  "status": "rework_required",
  "artifact": "",
  "scorecard": {
    "narrative_integrity": 4,
    "page_job_clarity": 2,
    "information_density": 3,
    "evidence_and_specificity": 2,
    "screenshot_and_asset_integration": 4,
    "layout_variety": 4,
    "consulting_style_expression": 4,
    "visual_readiness": 4,
    "delivery_readiness": 4
  },
  "score_summary": {
    "average": 3.44,
    "minimum": 2,
    "dimensions": 9
  },
  "summary": {
    "findings": 3,
    "page_findings": 2
  },
  "findings": [
    {
      "finding_id": "beat_004_evidence_gap",
      "severity": "P1",
      "dimension": "evidence_and_specificity",
      "message": "页面缺少支撑主张的客户证据。",
      "refs": ["page_tasks.json", "claim_evidence_graph.json"],
      "repair_instruction": "补充客户原话、截图、指标或历史案例。",
      "page_id": "beat_004_architecture",
      "risk_flags": ["evidence_gap"],
      "blocking_scope": "page"
    }
  ],
  "page_findings": [],
  "repair_plan": [],
  "blocks_delivery": true,
  "created_at": "2026-06-11T00:00:00Z"
}
```

### 16.4 Scorecard 维度

- Narrative Integrity。
- Page Job Clarity。
- Information Density。
- Evidence And Specificity。
- Screenshot And Asset Integration。
- Layout Variety。
- Consulting-Style Expression。
- Visual Readiness。
- Delivery Readiness。

### 16.5 Severity

| Severity | 含义 | 默认阻断 |
|---|---|---|
| P0 | 绝对交付阻断 | 是 |
| P1 | 客户可见前必须修复 | 是 |
| P2 | 应修复，可条件通过 | 否 |
| P3 | 建议优化 | 否 |

### 16.6 Draft Gate checks

- Deck 有清晰受众。
- Deck 有业务目标。
- 每页有页面职责。
- 每页有核心主张。
- 每页有 decision intent。
- Evidence-heavy 页面有 evidence policy。
- 缺客户事实写入 gaps。
- 页面顺序有叙事推进。
- 长 Deck 有章节交接。
- 页面密度匹配角色。
- claim/evidence 风险映射到页面。

### 16.7 Export 阻断规则

- 任意 P0/P1 finding 阻断 client-facing export。
- `rework_required` 阻断 client-facing export。
- `manual_placeholder` 页面不得进入最终交付页。
- override 必须显式记录。

### 16.8 Override schema

```json
{
  "schema_version": "deck_quality_override.v1",
  "override_id": "override_001",
  "run_id": "retail-conversation",
  "target": "beat_004_architecture",
  "finding_id": "beat_004_evidence_gap",
  "reason": "客户口头确认，下一版补截图。",
  "actor": "user",
  "created_at": "2026-06-11T00:00:00Z"
}
```

### 16.9 验收

- Draft Gate 可在没有 rendered artifact 时运行。
- Render/Delivery Gate 没有 artifact 时不自动运行。
- Web UI 展示 run-level 和 page-level quality。
- P0/P1 阻断 export。
- Markdown 报告可读。

---

## 17. Spec 12：Export、Delivery Outcome 与 Feedback

### 17.1 目标

确保导出队列只包含人工批准且质量允许的页面，并记录最终交付结果。

### 17.2 `approved_queue.json` schema

```json
{
  "schema_version": "deck_approved_queue.v1",
  "run_id": "retail-conversation",
  "title": "Retail Digital Transformation Deck",
  "source_manifest": "runs/retail-conversation/preview_manifest.json",
  "export_policy": {
    "include_review_status": ["approved"],
    "block_p0_p1": true,
    "exclude_manual_placeholder": true,
    "allow_override": true
  },
  "pages": [
    {
      "page_id": "beat_004_architecture",
      "order": 4,
      "title": "库存可视化目标架构",
      "source_type": "library_slide",
      "source_decision": "adapt",
      "review_status": "approved",
      "preview_path": "links/beat_004_architecture.svg",
      "source_preview_asset": "",
      "source_pptx": "",
      "source_slide_index": 12,
      "narrative_role": "architecture",
      "notes": ""
    }
  ],
  "excluded_pages": [
    {
      "page_id": "beat_008_case",
      "reason": "manual_placeholder cannot enter final handback"
    }
  ],
  "created_at": "2026-06-11T00:00:00Z"
}
```

### 17.3 CLI

```bash
python3 scripts/deck_master.py export --run-id <run_id>
python3 scripts/deck_master.py export --run-id <run_id> --allow-quality-override
```

### 17.4 `delivery_outcome.json` schema

```json
{
  "schema_version": "deck_delivery_outcome.v1",
  "run_id": "retail-conversation",
  "delivered": true,
  "final_artifact": "exports/retail_solution_v1.pptx",
  "delivered_pages": ["beat_001", "beat_002"],
  "removed_pages": ["beat_008_case"],
  "pages_rewritten_after_export": [],
  "customer_reaction": {
    "status": "positive",
    "notes": "客户认可库存闭环主线。"
  },
  "business_signal": {
    "advanced_to_next_stage": true,
    "quote_requested": false,
    "sow_requested": true,
    "contract_signed": false
  },
  "claim_feedback": [
    {
      "claim_id": "claim_001",
      "outcome": "accepted",
      "notes": "客户认可，但要求补充数据。"
    }
  ],
  "created_at": "2026-06-11T00:00:00Z"
}
```

### 17.5 Feedback event schema

```json
{
  "schema_version": "deck_feedback_event.v1",
  "timestamp": "2026-06-11T00:00:00Z",
  "run_id": "retail-conversation",
  "beat_id": "beat_004_architecture",
  "decision": "adapt",
  "candidate_id": "slide_123",
  "outcome": "approved",
  "source": "review_cockpit"
}
```

### 17.6 Feedback 文件

```text
feedback/
  sourcing_outcomes.jsonl
  slide_outcomes.jsonl
  quality_outcomes.jsonl
  delivery_outcomes.jsonl
```

首版只要求写：

- approved。
- rejected。
- delivered。
- excluded_by_quality。

### 17.7 验收

- rejected 页面不进入 approved queue。
- P0/P1 页面不进入 export，除非 override。
- manual_placeholder 不作为 client-facing page。
- export 写 event。
- delivery outcome 可选填写，但 schema 固定。

---

## 18. Spec 13：Review & Decision Cockpit UI

### 18.1 目标

提供本地 Web UI，用于专业方案人员审查页面、来源、证据、质量风险和审批状态。

### 18.2 信息架构

```text
Top Status Bar
  - Run title
  - Current status
  - Quality status
  - Page count
  - Approved / rejected / needs_review count
  - Next step

Left Page Rail
  - Page order
  - Page title
  - Role
  - Review status
  - Source decision
  - Quality badge
  - Filters

Center Preview
  - Page preview
  - Asset missing state
  - Zoom controls
  - Source preview metadata

Right Review Panel
  - Core claim
  - Decision intent
  - Source decision and reason
  - Selected candidate
  - Alternatives
  - Evidence needs and gaps
  - Quality findings
  - Generation task status
  - Review actions

Bottom Status Drawer
  - Events
  - Build Skill tasks
  - Export readiness
  - Repair plan
```

### 18.3 首版功能

必须实现：

- 中文 / 英文语言包。
- 跟随浏览器语言。
- 显式语言切换。
- 用户语言偏好 localStorage。
- 顶部 run 状态条。
- 左侧页面列表和筛选。
- 中央页面预览。
- 右侧页面审查面板。
- 底部状态抽屉。
- Draft Gate 阻断显示。
- Build Skill 状态显示。
- 页面审批、拒绝、备注。
- 替换来源。
- 转生成页。
- 锁定历史页。

### 18.4 用户可见状态

Review status：

- `needs_review`
- `approved`
- `rejected`

Source decision：

- `reuse`
- `adapt`
- `generate`
- `manual_placeholder`

Quality status：

- `not_run`
- `pass`
- `conditional_pass`
- `rework_required`

Build status：

- `pending`
- `running`
- `completed`
- `failed`
- `skipped`

### 18.5 操作规则

- Approve：只有非 P0/P1 阻断页面可直接 approve；否则需要 override。
- Reject：任何页面都可 reject，必须记录 note 或默认 reason。
- Replace source：只能从 alternatives 中选。
- Convert to generate：更新 sourcing decision，并刷新 generation task。
- Lock source：阻止后续自动 sourcing 覆盖该页来源。
- Manual placeholder：只能作为内部任务提醒，不作为最终交付页。

### 18.6 I18n

文件：

```text
scripts/preview/static/i18n/zh-CN.json
scripts/preview/static/i18n/en-US.json
```

所有用户可见字段必须从 i18n 读取。

### 18.7 验收

- 无同屏中英混排。
- 页面级 findings 可见。
- run-level quality status 可见。
- approve/reject 后 manifest 更新。
- event log 记录人工操作。
- 旧 manifest 可迁移或兼容读取。

---

## 19. Spec 14：CLI 总命令规范

### 19.1 Workspace

```bash
init-workspace
register-workspace
validate-workspace
```

### 19.2 Run lifecycle

```bash
start-conversation
build-brief
build-judgments
build-claim-map
build-claim-graph
plan
build-page-tasks
autoplan
resume
status
next-step
validate-run
```

### 19.3 Retrieval / sourcing

```bash
search-library
decide-sourcing
```

### 19.4 Build skill

```bash
create-generation-tasks
run-build-skill
ingest-build-artifact
```

### 19.5 Preview / review

```bash
build-preview
open-preview
review-page
replace-source
convert-to-generate
lock-source
```

### 19.6 Quality

```bash
quality-gate draft
quality-gate render --artifact <pptx> --expected-pages <n>
quality-gate delivery --artifact <pptx> --expected-pages <n> --forbidden <term>
```

### 19.7 Export / feedback

```bash
export
record-delivery-outcome
record-feedback
```

### 19.8 命令输出格式

所有 CLI 成功输出 JSON：

```json
{
  "run_id": "retail-conversation",
  "run_dir": "/abs/path/to/run",
  "status": "preview_ready",
  "next_step": "open_review_cockpit",
  "artifacts": ["preview_manifest.json"]
}
```

失败输出 stderr，但结构化错误必须写 event。

---

## 20. Spec 15：Schema Versioning 与 Migration

### 20.1 目标

所有重要 artifact 必须有 `schema_version`，支持后续迁移。

### 20.2 版本命名

```text
deck_workspace.v1
deck_request.v1
deck_event.v1
deck_context_manifest.v1
deck_conversation_session.v1
deck_brief.v1
deck_claim_map.v1
deck_claim_evidence_graph.v1
deck_narrative_plan.v1
deck_page_tasks.v1
deck_sourcing_plan.v1
deck_generation_task.v1
deck_preview_manifest.v1
deck_quality_report.v1
deck_approved_queue.v1
deck_delivery_outcome.v1
```

### 20.3 Migration module

```text
scripts/runtime/migrations.py
```

必须支持：

- preview manifest 旧 decision 字段迁移。
- sourcing decision `source_decision` / `decision` 双写兼容。
- events 旧 action/status 模型升级。
- page_tasks 缺少 review/quality 分层时补默认值。

### 20.4 验收

- 旧 run 可被 `validate-run` 检测并给出 migration suggestion。
- 迁移写备份：`<file>.bak.<timestamp>`。
- migration 写 event。
- 不自动破坏用户审批状态。

---

## 21. Spec 16：测试矩阵

### 21.1 基础命令

```bash
uvx pytest
python3 -m unittest discover -s tests
```

仓库最终应统一到一种测试入口；如果并存，CI 中都要执行。

### 21.2 必测类别

| 类别 | 用例 |
|---|---|
| Workspace | init、register、validate、缺文件 pending |
| Runtime | create run、duplicate run、force、resume、bad JSON |
| Events | typed schema、warning、error、manual_action |
| Next step | 每个缺失 artifact 对应正确 next_step |
| Context | 多 context file、hash、kind detection、不支持格式报错 |
| Conversation | guided questions、locked decisions、context refs |
| Brief | business_goal、core_points、boundaries |
| Judgment | judgment、evidence、assumption、deck_implication |
| Claim Graph | claims、evidence、assumptions、risks、links |
| Planner | workspace archetype、fallback、target_pages、gaps |
| Page Tasks | 分层字段、decision_intent、evidence_policy |
| PPT Library | normal、empty、bad JSON、CLI missing、screenshot missing |
| Sourcing | reuse、adapt、generate、manual_placeholder、tie-break |
| Build Skill | task creation、fake executor、artifact handback、failed state |
| Preview | manifest compatibility、asset missing、page payload |
| Review API | approve、reject、note、replace、convert、lock |
| Quality | draft hard path、render artifact、delivery artifact、P0/P1 blocking |
| Export | approved-only、quality block、manual_placeholder exclusion、override |
| Feedback | approved/rejected/delivered events |
| I18n | zh-CN/en-US completeness、language switch |
| E2E fixture | retail from context to preview + draft gate |
| Real regression | 达能 AI 消费者样本到可审查草案 |

### 21.3 Smoke test

```bash
tmp=$(mktemp -d)
python3 scripts/deck_master.py init-workspace --workspace "$tmp/ws" --name Test
python3 scripts/deck_master.py start-conversation \
  --workspace "$tmp/ws" \
  --context-file examples/context/retail_meeting_transcript.txt \
  --industry retail \
  --runs-dir "$tmp/runs" \
  --run-id smoke
python3 scripts/deck_master.py build-brief --run-dir "$tmp/runs/smoke"
python3 scripts/deck_master.py build-claim-map --run-dir "$tmp/runs/smoke"
python3 scripts/deck_master.py autoplan --run-dir "$tmp/runs/smoke" --library-mode fixture
python3 scripts/deck_master.py quality-gate --run-dir "$tmp/runs/smoke" draft
python3 scripts/deck_master.py export --run-dir "$tmp/runs/smoke"
rm -rf "$tmp"
```

---

## 22. Spec 17：阶段路线与开发包

### Phase 1：Run OS Core

目标：一次客户方案 Deck 生产可运行、可追踪、可审查。

必须完成：

1. Workspace Foundation。
2. Typed Events。
3. Next Step Resolver。
4. Context / Brief / Claim Map。
5. Workspace-aware Planner。
6. Sourcing Decision。
7. Draft Gate。
8. Review UI 基础审查。
9. Approved Queue。

完成标准：零售 fixture 可从 context 跑到 preview + Draft Gate + approved export。

### Phase 2：Solution Narrative Engine

目标：输出更像专业顾问写的方案主线。

必须完成：

1. Consulting Judgment Layer。
2. Claim-Evidence Graph。
3. Argument Chain。
4. Decision Intent。
5. Evidence Policy。
6. Customer Specificity Level。
7. Objection Handling。

完成标准：真实客户样本中，用户主要审主线和证据，避免重写整套页面结构。

### Phase 3：Asset Intelligence

目标：历史方案资产产生复利。

必须完成：

1. Slide-level asset graph。
2. Canonical slide id 对齐。
3. Page archetype tagging。
4. Claim/evidence tagging。
5. Approval/rejection feedback。
6. Reuse/adapt/generate 决策学习。
7. Workspace asset health report。

完成标准：历史页有效复用率可统计，低质量页面可识别。

### Phase 4：Quality & Delivery Governance

目标：具备交付级质量控制。

必须完成：

1. Evidence Gate。
2. Brand Gate。
3. Confidentiality Gate。
4. Client Context Conflict Gate。
5. Override Governance。
6. Delivery Package Validation。
7. Final Version Lineage。

完成标准：最终交付前可解释阻断项，Delivery Outcome 可反哺资产。

### Phase 5：Team / Enterprise Solution Deck Factory

目标：从个人工作流扩展到团队级方案生产系统。

必须完成：

1. 多用户。
2. 角色权限。
3. 审批流。
4. Shared workspace。
5. Team quality dashboard。
6. Opportunity-level deck history。
7. CRM / 文档库 / 会议系统集成。
8. Business outcome feedback。

完成标准：团队可复用专家经验，新人可基于工作区资产稳定产出专业方案草案。

---

## 23. Definition of Done

任意开发包完成必须满足：

1. 对应 CLI 或 API 可运行。
2. 新 artifact 有 schema_version。
3. 关键步骤写 typed events。
4. 坏输入有明确错误，不静默覆盖。
5. 有单元测试。
6. 有至少一个 fixture 测试。
7. 文档更新。
8. 不破坏现有 smoke test。
9. Web UI 可见的状态必须来自 run artifact，不能依赖临时内存。
10. Agent 能通过 `next-step` 解释下一步。

---

## 24. 最终验收场景

### 24.1 零售数字化 fixture

输入：全渠道、库存可视化、最后一公里配送。

期望：

- 生成 deck brief。
- 生成 consulting judgments。
- 生成 claim map / claim evidence graph。
- 生成 10 页以上 page tasks。
- 包含架构、案例、价值、路线图等页面。
- sourcing 有 reuse / adapt / generate / manual_placeholder。
- Draft Gate 输出质量报告。
- Web UI 能审查来源、风险和审批状态。
- approved queue 可导出。

### 24.2 达能 AI 消费者真实回归

输入：会议转写、客户材料、历史方案摘要、用户口头判断。

期望：

- 2 小时内形成可审查草案。
- 页面主线可用。
- 证据缺口明确。
- 历史页复用可解释。
- Draft Gate 能指出内容和证据风险。
- 用户能继续人工打磨。

### 24.3 外部工具失败

输入：PPT Library 不可用或 embedding 服务失败。

期望：

- run 不进入不可恢复状态。
- events 记录失败。
- sourcing 回退 generate 或 manual_placeholder。
- Web UI 显示风险和下一步。

### 24.4 Build Skill 失败

输入：某页 generation task 失败。

期望：

- 对应页 failed。
- 其他页仍可 preview。
- event 记录失败。
- Agent 可解释下一步。

### 24.5 审批导出

输入：部分 approved、部分 rejected、部分 P1 finding。

期望：

- approved queue 只包含 approved 且无 P0/P1 阻断页面。
- rejected 页面保留审查记录。
- P1 页面无 override 不导出。
- manual_placeholder 不进入 client-facing export。

---

## 25. 开发优先级建议

后续连续开发建议按以下顺序执行：

1. `Spec 00`：迁移保护。
2. `Spec 02`：Typed Events + Next Step。
3. `Spec 01`：Workspace Foundation 真接入。
4. `Spec 03`：Context manifest 强化。
5. `Spec 04`：Brief + Consulting Judgment。
6. `Spec 05`：Claim-Evidence Graph。
7. `Spec 06`：Narrative Engine / Page Tasks 强化。
8. `Spec 08`：Sourcing score_breakdown 与阈值对齐。
9. `Spec 11`：Draft Gate 强化并接入 export 阻断。
10. `Spec 10/13`：Review Cockpit API + UI。
11. `Spec 09`：Build Skill Runtime contract。
12. `Spec 12`：Delivery Outcome + Feedback。
13. `Spec 16`：测试矩阵补齐。

这个顺序的核心原则是：先稳定状态和数据契约，再增强智能；先让 run 可解释，再让页面更漂亮；先沉淀资产结构，再做学习闭环。

---

## 26. 附录：关键不变量

1. Deck Master 的核心是生产可证明、可审查、可复用的 Solution Deck。
2. Run OS 是底座，不是终局全部。
3. 每一页必须承担客户决策推进中的明确职责。
4. 每一个 claim 必须能追踪 evidence 或明确证据缺口。
5. 历史页复用必须有解释理由。
6. AI 推断必须标记，不得伪装为客户事实。
7. P0/P1 不能静默交付。
8. 用户审批是生产闭环的一部分，不是 UI 附属功能。
9. 每一次交付都应反哺 workspace 资产。
10. 系统价值来自长期资产复利，单次自动生成只是一层近期效率收益。
