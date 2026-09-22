# Deck Master P2-P5 Claude Code 开发说明书

版本：v0.2  
日期：2026-06-12  
适用仓库：`MainQuestAI/Deck-Master`  
适用对象：Claude Code / Codex / OpenCode  
主文档：本文件是 P2-P5 开发唯一主版本。拆包目录只保留索引和任务入口。

---

## 0. 使用方式

这份文档的目标是让 Claude Code 可以直接开始执行开发任务。每次只执行一个任务包，完成后必须跑对应测试，并输出修改清单、测试结果、已知限制。

推荐下发模板：

```text
你正在开发 MainQuestAI/Deck-Master。
请阅读 docs/deck-master-p2-p5-development-guide.md。
本次只执行 <任务编号>：<任务名称>。

执行边界：
- 严格遵守该任务的允许修改范围。
- 不扩展到相邻阶段。
- 不重写无关模块。
- 不破坏现有 start-conversation / autoplan / preview / quality-gate / export。
- 新增 artifact 必须带 schema_version。
- 关键步骤必须写 typed events，并兼容旧 events.jsonl。
- 坏 JSON 不得覆盖原文件。

完成后输出：
- 修改文件清单。
- 测试命令和结果。
- 仍未完成的限制。
```

---

## 1. 当前基线

### 1.1 当前 main 已具备能力

截至 2026-06-12，`main` 的 `scripts/deck_master.py` 已有命令：

```text
plan
start-conversation
build-brief
build-claim-map
autoplan
search-library
decide-sourcing
create-generation-tasks
build-preview
export
quality-gate
```

当前主链路已经可以作为 P1 Run OS 原型运行：

- 从 brief 或本地 context 创建 run。
- 生成 `context_manifest.json`、`conversation_session.json`、`deck_brief.json`、`claim_map.json`。
- 生成 narrative plan、page tasks、library results、sourcing plan、generation tasks、preview manifest。
- 运行基础 quality gate。
- 导出 approved queue。
- 启动 preview server 做基础审查。

### 1.2 P1.1 是硬前置

P2-P5 要建立在更稳定的工程契约上。以下 P1.1 能力必须先补齐，才能进入 P2 主开发：

| 编号 | 能力 | 当前问题 | 硬要求 |
|---|---|---|---|
| S0-A | Workspace CLI | 还缺 `init-workspace / register-workspace / validate-workspace` | 必须先有完整 workspace 容器 |
| S0-B | Typed Events | 当前事件偏旧字段 | 新增 canonical event，同时兼容旧字段 |
| S0-C | Next Step Resolver | 只有粗粒度 `run_status` | 新增 `next-step`，让 Agent 可恢复执行 |
| S0-D | Review Status Migration | preview 仍以 legacy decision 为主 | 新增 `review_status/action_intent`，保留 legacy decision |
| S0-E | Export Quality Blocking | export 只按 decision 过滤 | 接入 quality blocking 和 override 读取 |
| S0-F | Schema Version Helper | artifact 版本不统一 | 新增 schema helper，所有新增 artifact 带版本 |

判断标准：Sprint 0 未通过时，Claude Code 只能执行 S0 任务，不能开始 P2-P5。

---

## 2. 全局工程约束

### 2.1 Artifact-first

核心状态必须落到 run 或 workspace artifact。前端状态、日志和临时变量不能作为唯一事实来源。

### 2.2 写文件安全

- 写 JSON 时使用临时文件加原子替换。
- 读取坏 JSON 时抛出明确错误，保留原文件。
- JSONL 只能 append，不能整体重写。
- 需要迁移旧 artifact 时，先生成备份或保留兼容读取。

### 2.3 Schema Version

新增 artifact 必须包含：

```json
{
  "schema_version": "deck_xxx.v1"
}
```

旧 artifact 读取策略：

- 无 `schema_version` 时按 legacy schema 解析。
- 写回时补 `schema_version`。
- 不因缺少版本字段直接丢弃用户数据。

### 2.4 Typed Events

新增事件使用 canonical 字段，并保留旧字段：

```json
{
  "schema_version": "deck_event.v1",
  "timestamp": "2026-06-12T00:00:00Z",
  "run_id": "run_001",
  "event_type": "step_completed",
  "step": "build_claim_graph",
  "message": "Claim evidence graph generated.",
  "refs": ["claim_evidence_graph.json"],
  "severity": "info",
  "action": "build_claim_graph",
  "status": "completed"
}
```

允许的 `event_type`：

| event_type | 用途 |
|---|---|
| `step_started` | 阶段开始 |
| `step_completed` | 阶段完成 |
| `tool_call` | 外部工具调用 |
| `decision` | planner、sourcing、quality、export 决策 |
| `error` | 可恢复或不可恢复错误 |
| `manual_action` | 人工审批、override、备注 |
| `artifact_written` | 关键 artifact 写入 |

### 2.5 Review 状态契约

P1 legacy 字段继续读取，但新逻辑以两个字段为准：

```json
{
  "review_status": "needs_review",
  "action_intent": "none",
  "decision": "needs_review"
}
```

取值：

| 字段 | 允许值 |
|---|---|
| `review_status` | `needs_review`、`approved`、`rejected` |
| `action_intent` | `none`、`reuse`、`adapt`、`generate`、`manual_placeholder`、`replace` |
| `decision` | legacy 兼容字段，读写时保留 |

### 2.6 Delivery Outcome 路径兼容

P4 起采用 canonical 路径：

```text
delivery/delivery_outcome.json
```

兼容策略：

- 写入 canonical 路径。
- 读取时优先 canonical 路径。
- 如果只存在 legacy `delivery_outcome.json`，正常读取。
- 如果两个文件同时存在，canonical 路径优先，并写 event 提示存在 legacy 文件。

### 2.7 UI 边界

Web UI 是任务唤起式 Review Cockpit。它负责审查、对比、批准、拒绝、备注、查看质量状态。它不承担完整桌面 App 职责。

P2-P5 UI 开发必须遵守：

- 信息架构用中文为主，保留必要英文 artifact 名。
- 同一页面避免中英混排标题。
- 每个 UI 新能力必须有对应 artifact 作为数据来源。
- 操作必须写回 artifact 和 events。

---

## 3. Sprint 0：P1.1 Hardening

Sprint 0 是 P2-P5 的入口门槛。

### S0-A：Workspace Foundation

目标：建立完整 Deck Workspace，承载视觉规范、页型资产、质量规则、runs、exports。

允许修改：

- `scripts/deck_master.py`
- `scripts/workspace/`
- `tests/test_workspace_foundation.py`
- `docs/schemas/workspace.schema.json`

新增命令：

```bash
python3 scripts/deck_master.py init-workspace --workspace <path> --name <name>
python3 scripts/deck_master.py register-workspace --workspace <path> --reference-ppt <pptx>
python3 scripts/deck_master.py validate-workspace --workspace <path>
```

Workspace 目录：

```text
deck-workspace/
  workspace_manifest.json
  visual-system/
    design_spec.md
    spec_lock.md
    brand_assets.md
  structure-assets/
    page_archetypes.md
    section_patterns.md
    component_library.md
  quality/
    scoring_rubric.md
    forbidden_terms.md
    delivery_checklist.md
  assets/
    slide_assets/
    asset_graph.json
    asset_feedback.jsonl
  runs/
  exports/
```

首版 reference PPT 边界：

- 只记录路径、文件 hash、页数、注册时间。
- 不承诺自动提取视觉系统。
- 后续视觉提取另列任务。

验收：

- 新 workspace 可创建。
- 已存在 workspace 可注册。
- 缺少标准文件时 `validate-workspace` 输出 `pending_manual_review`，进程不崩溃。
- 新增测试覆盖重复初始化、坏 manifest、reference PPT 不存在。

### S0-B：Typed Events

目标：把事件日志升级成 typed event，同时不破坏旧事件读取。

允许修改：

- `scripts/runtime/events.py`
- `scripts/runtime/run_state.py`
- `tests/test_runtime_events.py`

要求：

- 新增 `append_event(run_dir, event_type, step, message, refs=None, severity="info", payload=None)`。
- 自动补 `timestamp/run_id/schema_version/action/status`。
- 写入 `events.jsonl`。
- 旧调用继续可用。

验收：

- 旧测试通过。
- 新事件包含 canonical 字段。
- 坏 JSONL 行不会导致整个 run 无法读取。

### S0-C：Next Step Resolver

目标：让 Agent 可以知道当前 run 下一步该做什么。

允许修改：

- `scripts/runtime/next_step.py`
- `scripts/deck_master.py`
- `tests/test_next_step.py`

新增命令：

```bash
python3 scripts/deck_master.py next-step --run-id <run_id>
python3 scripts/deck_master.py next-step --run-dir <run_dir>
```

输出：

```json
{
  "schema_version": "deck_next_step.v1",
  "run_id": "run_001",
  "status": "needs_sourcing",
  "next_command": "python3 scripts/deck_master.py decide-sourcing --run-dir ...",
  "missing_artifacts": ["sourcing_plan.json"],
  "blocking_issues": []
}
```

状态优先级：

1. 缺 request。
2. 缺 context 或 brief。
3. 缺 claim map。
4. 缺 narrative plan。
5. 缺 page tasks。
6. 缺 library results。
7. 缺 sourcing plan。
8. 缺 generation tasks。
9. 缺 preview manifest。
10. 缺 draft gate。
11. 有 approved 页面可 export。
12. 已完成本地交付队列。

验收：

- 每个缺失状态都有测试。
- `--resume` 类流程可以复用 resolver。

### S0-D：Review Status Migration

目标：preview manifest 支持 `review_status/action_intent`，并兼容旧 `decision`。

允许修改：

- `scripts/preview/manifest.py`
- `scripts/preview/server.py`
- `tests/test_preview_manifest.py`
- `docs/schemas/preview_manifest.schema.json`

迁移规则：

| legacy decision | review_status | action_intent |
|---|---|---|
| `approved` | `approved` | 原来源决策或 `none` |
| `rejected` | `rejected` | `none` |
| `needs_review` | `needs_review` | `none` |
| `keep` | `approved` | `reuse` |
| `replace` | `needs_review` | `replace` |

验收：

- 旧 manifest 可读。
- 新 manifest 写入新字段。
- API 更新页面状态时同步 legacy decision。
- UI approve/reject/note 不回归。

### S0-E：Export Quality Blocking

目标：export 阶段读取 quality reports 和 override，阻断高风险页面进入客户交付队列。

允许修改：

- `scripts/orchestrate/export_queue.py`
- `scripts/quality/`
- `tests/test_export_quality_blocking.py`

规则：

- `review_status=approved` 才能进入 client-facing export。
- P0 finding 一律阻断 client-facing export。
- P1 finding 需要 active override。
- `manual_placeholder` 页面只能进入 internal task queue。
- 找不到 quality report 时，默认 `needs_quality_review`，不直接客户交付。

新增参数：

```bash
python3 scripts/deck_master.py export --run-id <run_id> --queue-type client
python3 scripts/deck_master.py export --run-id <run_id> --queue-type internal
python3 scripts/deck_master.py export --run-id <run_id> --allow-quality-override
```

验收：

- P0 页面不能导出到 client queue。
- P1 页面无 override 时不能导出到 client queue。
- internal queue 保留待修复页面。
- export 写 typed event。

### S0-F：Schema Helper 与 Baseline Smoke

目标：统一 schema 版本工具，并建立 P2 前回归基线。

允许修改：

- `scripts/runtime/schema.py`
- `tests/test_schema_versioning.py`
- `tests/test_end_to_end_autoplan.py`
- `examples/briefs/retail_digital_transformation.txt`

验收命令：

```bash
python3 -m unittest discover -s tests
python3 scripts/deck_master.py --help
```

Smoke 场景：

```bash
tmp=$(mktemp -d)
python3 scripts/deck_master.py init-workspace --workspace "$tmp/ws" --name "Retail Demo"
python3 scripts/deck_master.py start-conversation \
  --runs-dir "$tmp/runs" \
  --workspace "$tmp/ws" \
  --brief "零售客户数字化转型方案，关注全渠道、库存可视化、最后一公里配送" \
  --run-id retail_demo
python3 scripts/deck_master.py build-brief --runs-dir "$tmp/runs" --run-id retail_demo
python3 scripts/deck_master.py build-claim-map --runs-dir "$tmp/runs" --run-id retail_demo
python3 scripts/deck_master.py next-step --runs-dir "$tmp/runs" --run-id retail_demo
```

完成标准：

- 上述命令能稳定运行。
- 新旧测试通过。
- `events.jsonl`、workspace manifest、request、brief、claim map 可检查。

---

## 4. P2：Solution Narrative Engine

P2 目标：让 Deck Master 从“生成页面清单”升级为“形成专业方案主线”。P2 先解决论点、论证、证据和页面职责，再进入资产复用。

P2 前置条件：Sprint 0 全部完成。

### P2-A：Consulting Judgment Layer

目标：从 context、deck brief、claim map 中生成专业判断。

允许修改：

- `scripts/narrative/judgment_builder.py`
- `scripts/deck_master.py`
- `docs/schemas/consulting_judgments.schema.json`
- `tests/test_consulting_judgments.py`

命令：

```bash
python3 scripts/deck_master.py build-judgments --run-id <run_id>
```

产物：`consulting_judgments.json`

最小 schema：

```json
{
  "schema_version": "deck_consulting_judgments.v1",
  "run_id": "retail_demo",
  "judgments": [
    {
      "judgment_id": "judgment_001",
      "topic": "business_problem",
      "statement": "客户核心问题是跨渠道履约闭环薄弱。",
      "rationale": "会议转写和 brief 同时指向库存、渠道和配送协同问题。",
      "confidence": 0.72,
      "source_refs": ["context_manifest.json#source_001"],
      "risk_flags": ["needs_customer_evidence"]
    }
  ],
  "open_questions": []
}
```

验收：

- 短 brief 可生成至少 3 条 judgment。
- 缺证据 judgment 必须带 risk flag。
- 重复执行同一输入输出稳定。

### P2-B：Claim-Evidence Graph

目标：把 claims、evidence、assumptions、risks、pages 连成图。

允许修改：

- `scripts/narrative/claim_graph.py`
- `scripts/deck_master.py`
- `docs/schemas/claim_evidence_graph.schema.json`
- `tests/test_claim_evidence_graph.py`

命令：

```bash
python3 scripts/deck_master.py build-claim-graph --run-id <run_id>
```

产物：`claim_evidence_graph.json`

要求：

- claim 必须包含 `claim_id/type/statement/supporting_evidence/assumptions/risks/required_evidence/page_refs`。
- evidence 必须包含 `evidence_id/source_ref/evidence_type/summary/confidence/publication_status`。
- `publication_status` 取值：`safe_to_use`、`internal_only`、`needs_redaction`、`unknown`。
- 缺关键证据时写入 `gaps`。

验收：

- 每个核心 claim 至少有 required evidence。
- 无证据 claim 被标记为 gap。
- 可从 page task 反查 claim。

### P2-C：Narrative Planner v2 与 Page Tasks

目标：planner 读取 judgments、claim graph、workspace archetypes，生成增强 plan 和 page tasks。

允许修改：

- `scripts/planning/narrative_planner.py`
- `scripts/planning/page_tasks.py`
- `scripts/planning/page_budget.py`
- `tests/test_narrative_planner.py`
- `tests/test_page_tasks.py`

新增字段：

```json
{
  "decision_intent": "让客户认可库存可视化需要跨渠道履约闭环支撑。",
  "argument_chain": ["业务问题", "根因", "解决路径", "证据", "客户决策"],
  "evidence_policy": {
    "required": true,
    "allowed_evidence_types": ["meeting_quote", "customer_material", "case_study", "product_screenshot"],
    "missing_evidence_action": "manual_placeholder"
  },
  "customer_specificity_level": "client_specific",
  "workspace_refs": ["structure-assets/page_archetypes.md#architecture"]
}
```

验收：

- 零售 fixture 生成 10 页以上。
- 必须包含全渠道、库存可视化、最后一公里、架构、案例、价值页。
- 每页必须关联 claim 或明确标记为 opener/closing。
- 有 workspace 时写入 `workspace_refs`。

### P2-D：Draft Gate 2.0

目标：Draft Gate 从“字段检查”升级为“主线和证据链检查”。

允许修改：

- `scripts/quality/draft_gate.py`
- `scripts/quality/draft_gate_v2.py`
- `tests/test_draft_gate_v2.py`

检查维度：

| 维度 | 阻断条件 |
|---|---|
| thesis_clarity | 没有核心主张 |
| claim_coverage | 核心 claim 无页面承载 |
| evidence_readiness | required evidence 缺失 |
| argument_flow | 页面顺序无法形成证明链 |
| audience_fit | 受众和表达密度不匹配 |
| specificity | 客户专属页缺客户证据 |
| risk_visibility | 风险未暴露 |

状态：

- `pass`
- `conditional_pass`
- `rework_required`

验收：

- 缺证据 claim 产生 P1 finding。
- 没有页面承载的核心 claim 产生 P1 finding。
- opener/closing 不强制 evidence。
- 输出兼容旧 `draft_gate.json`。

### P2-E：Narrative Review Cockpit

目标：Preview UI 能审主线。

允许修改：

- `scripts/preview/server.py`
- `scripts/preview/static/`
- `tests/test_preview_server.py`

新增展示：

- Deck objective。
- Core thesis。
- Audience strategy。
- Top judgments。
- Claim evidence coverage。
- Page-level core claim。
- Evidence policy。
- Gaps。

操作：

- approve。
- reject。
- add note。

验收：

- 不新增复杂编辑器。
- 操作写回 preview manifest。
- 操作写 typed event。

---

## 5. P3：Asset Intelligence

P3 目标：让历史方案资产在 workspace 层沉淀，并影响 sourcing 决策。

P3 前置条件：P2-D 至少完成，P2-E 可并行。

### P3-A：Asset Schema 与 Canonical ID

目标：定义稳定 slide asset 身份和 asset graph。

允许修改：

- `scripts/assets/schema.py`
- `scripts/assets/canonical_id.py`
- `docs/schemas/asset_graph.schema.json`
- `tests/test_asset_schema.py`

Canonical ID 规则：

```text
canonical_slide_id = "slide_" + sha256(file_sha256 + ":" + page_number + ":" + normalized_title)[0:16]
```

Fallback：

- 如果缺 `file_sha256`，使用 `normalized_source_ref + page_number + normalized_title`。
- 如果 title 缺失，使用 text summary 前 120 字。

路径规则：

- workspace 内路径必须存 workspace-relative path。
- workspace 外文件存 `external_path`，并记录 `sha256`。
- 禁止把绝对路径作为唯一引用。

产物：

```text
assets/asset_graph.json
assets/slide_assets/<canonical_slide_id>.json
```

验收：

- 文件移动后，只要 hash 和页码不变，ID 保持稳定。
- 缺截图不阻断注册，但标记 `missing_screenshot`。
- 重复 candidate 合并到同一 slide asset。

### P3-B：Library Result Ingestion

目标：把 PPT Library 返回的候选页注册成 workspace asset。

允许修改：

- `scripts/assets/ingest_library_results.py`
- `scripts/tools/ppt_library_client.py`
- `tests/test_asset_ingestion.py`

输入：

```text
runs/<run_id>/library_results/selection.json
runs/<run_id>/library_results/by_beat/*.json
```

输出：

- `assets/asset_graph.json`
- `assets/slide_assets/*.json`
- run 内 `asset_refs.json`

验收：

- 正常候选注册为 asset。
- 空结果写 event。
- 错误 JSON 报错但不覆盖旧 asset graph。
- 缺截图降级为 risk flag。

### P3-C：Feedback Collector

目标：把 approve/reject/export/delivery 信号反哺 asset。

允许修改：

- `scripts/assets/feedback.py`
- `scripts/preview/manifest.py`
- `scripts/orchestrate/export_queue.py`
- `tests/test_asset_feedback.py`

产物：

```text
assets/asset_feedback.jsonl
```

事件类型：

- `preview_approved`
- `preview_rejected`
- `exported_internal`
- `exported_client`
- `delivered`
- `delivery_positive_signal`
- `delivery_negative_signal`

验收：

- preview approve/reject 写 feedback。
- export 写 feedback。
- 同一事件重复写入时可去重。

### P3-D：Asset Health 与 Archetype Tagging

目标：识别资产健康状态和页型标签。

允许修改：

- `scripts/assets/health.py`
- `scripts/assets/archetype_tagger.py`
- `tests/test_asset_health.py`

Health 规则：

- `missing_screenshot`
- `low_approval_rate`
- `high_rejection_rate`
- `stale_asset`
- `confidential_risk`
- `orphan_asset`

产物：

```text
assets/asset_health_report.json
```

验收：

- 低 approval asset 被标记。
- 缺 screenshot asset 被标记。
- 未被任何 run 使用的 asset 被标记为 orphan。

### P3-E：Sourcing Scoring v2

目标：sourcing decision 读取 asset intelligence 信号，并输出可解释分数。

允许修改：

- `scripts/planning/sourcing_decider.py`
- `scripts/assets/scoring.py`
- `tests/test_sourcing_decider.py`
- `tests/test_sourcing_scoring_v2.py`

初始权重：

| 维度 | 权重 |
|---|---:|
| semantic_match | 0.24 |
| narrative_role_match | 0.14 |
| archetype_match | 0.10 |
| screenshot_available | 0.08 |
| source_credibility | 0.08 |
| win_rate | 0.10 |
| approval_history | 0.08 |
| delivery_history | 0.06 |
| visual_continuity | 0.06 |
| evidence_sufficiency | 0.06 |

Penalty：

| 条件 | 调整 |
|---|---:|
| high customer_context_conflict | -0.25 |
| medium customer_context_conflict | -0.10 |
| missing screenshot | reuse score cap 0.69 |
| internal_only evidence | client export cap 0.59 |

决策阈值：

| decision | 条件 |
|---|---|
| `reuse` | score >= 0.78，截图可用，context conflict <= 0.20 |
| `adapt` | score >= 0.58，结构可用，context conflict <= 0.50 |
| `generate` | 无候选达到 adapt 阈值，或需要客户专属新内容 |
| `manual_placeholder` | required evidence 缺失，且不能由生成页安全补齐 |

Tie-breaker：

1. evidence_sufficiency 高者优先。
2. approval_history 高者优先。
3. delivery_history 高者优先。
4. `canonical_slide_id` 字典序靠前者优先。

验收：

- 相同输入稳定输出相同决策。
- 高胜率但客户语境冲突的候选会降级。
- 缺截图候选不能进入 reuse。

### P3-F：Asset Signals UI

目标：Review Cockpit 展示候选页历史表现。

允许修改：

- `scripts/preview/server.py`
- `scripts/preview/static/`
- `tests/test_preview_server.py`

展示：

- approval rate。
- rejection count。
- delivered count。
- health flags。
- screenshot 状态。
- selected candidate 评分拆解。

验收：

- 页面可看到候选页为何被选中。
- 缺 asset graph 时 UI 降级显示。

---

## 6. P4：Quality & Delivery Governance

P4 目标：让 Deck Master 具备交付级质量治理。P4 必须补齐 gate 闭环，避免只做报告展示。

P4 前置条件：S0-E 完成，P2-D 完成，P3-E 完成。

### P4 Gate 范围

| Gate | P4 范围 | 说明 |
|---|---|---|
| Evidence Gate | 必做 | 检查 claim 与 required evidence |
| Context Conflict Gate | 必做 | 检查复用页与当前客户语境冲突 |
| Confidentiality Gate | 必做 | 检查内部词、客户名残留、敏感来源 |
| Delivery Gate 2.0 | 必做 | 校验最终交付包、页数、hash、lineage |
| Brand Gate | P4 轻量版 | 有 PPTX/HTML/SVG 时运行；无渲染资产时 `not_applicable` |

### P4-A：Evidence Gate

允许修改：

- `scripts/quality/evidence_gate.py`
- `scripts/deck_master.py`
- `tests/test_evidence_gate.py`

命令：

```bash
python3 scripts/deck_master.py quality-gate evidence --run-id <run_id>
```

阻断规则：

- required evidence 缺失：P1。
- claim 无页面承载：P1。
- evidence 标记 `internal_only` 仍进入 client queue：P0。

验收：

- 输出 `quality_reports/evidence_gate.json`。
- P1/P0 写入 blocking summary。

### P4-B：Context Conflict Gate

允许修改：

- `scripts/quality/context_conflict_gate.py`
- `tests/test_context_conflict_gate.py`

检查：

- 历史页行业与当前行业冲突。
- 历史页客户名残留。
- 历史页场景与当前 claim 不匹配。
- 历史证据缺对外授权。

验收：

- 高冲突 reuse/adapt 页面产生 finding。
- finding 带 `page_id/asset_id/source_ref/repair_instruction`。

### P4-C：Confidentiality Gate

允许修改：

- `scripts/quality/confidentiality_gate.py`
- `quality/forbidden_terms.md`
- `tests/test_confidentiality_gate.py`

检查来源：

- workspace `quality/forbidden_terms.md`。
- run context source metadata。
- final artifact 文本抽取结果。
- preview manifest 页面标题、备注、候选页摘要。

规则：

- 密钥、token、账号、报价底线类命中：P0。
- 其他客户名称残留：P1。
- 内部项目代号残留：P1 或 P2，按 forbidden term 配置。
- `needs_redaction` 来源进入 client export：P0。

验收：

- 命中 forbidden term 产生 finding。
- 支持 fixture PPTX/text 输入。
- 不把敏感原文大段写入报告，只保留短摘录和来源指针。

### P4-D：Brand Gate 轻量版

允许修改：

- `scripts/quality/brand_gate.py`
- `tests/test_brand_gate.py`

检查：

- 是否存在 workspace visual-system。
- final artifact 是否存在。
- 页数是否与 approved queue 一致。
- 可抽取文本时检查字体/品牌词基础一致性。
- 有图片目录时检查截图缺失。

状态：

- `pass`
- `conditional_pass`
- `rework_required`
- `not_applicable`

验收：

- 没有 render artifact 时输出 `not_applicable`，并提示等待渲染资产。
- 有 final artifact 时输出报告。

### P4-E：Override Governance

允许修改：

- `scripts/quality/overrides.py`
- `scripts/deck_master.py`
- `tests/test_overrides.py`

命令：

```bash
python3 scripts/deck_master.py override create --run-id <run_id> --finding-id <id> --reason <text> --approver <user>
python3 scripts/deck_master.py override list --run-id <run_id>
python3 scripts/deck_master.py override revoke --run-id <run_id> --override-id <id> --reason <text>
```

Override schema：

```json
{
  "schema_version": "deck_quality_override.v1",
  "timestamp": "2026-06-12T00:00:00Z",
  "override_id": "override_001",
  "run_id": "retail_demo",
  "target_type": "quality_finding",
  "target_id": "finding_001",
  "severity": "P1",
  "scope": "client_export",
  "reason": "客户已确认下一版补充截图。",
  "actor": "user_001",
  "approver": "owner",
  "expires_at": "2026-06-26T00:00:00Z",
  "status": "active"
}
```

政策：

- P0 不能 override 到 client export。
- P1 override 必须有 reason、approver、expires_at。
- P1 override 最长期限 14 天。
- override create/revoke 必须写 typed event。

验收：

- P0 override 被拒绝。
- P1 缺 approver 或 expires_at 被拒绝。
- revoke 后 export blocking 恢复。

### P4-F：Delivery Validation 与 Outcome

允许修改：

- `scripts/delivery/validate.py`
- `scripts/delivery/outcome.py`
- `scripts/deck_master.py`
- `tests/test_delivery_validation.py`
- `tests/test_delivery_outcome.py`

命令：

```bash
python3 scripts/deck_master.py delivery validate --run-id <run_id> --artifact <pptx>
python3 scripts/deck_master.py delivery record-outcome --run-id <run_id> --delivered --advanced-to-next-stage
```

检查：

- final artifact 存在。
- artifact hash 写入 lineage。
- final page count 与 approved queue 一致。
- quality reports 均已读取。
- P0/P1 blocking 状态符合 override 策略。

产物：

```text
delivery/final_version_lineage.json
delivery/delivery_outcome.json
```

验收：

- 页数不一致产生 P1。
- hash 变化产生 stale export finding。
- delivery outcome 反哺 `assets/asset_feedback.jsonl`。

### P4-G：Quality Governance UI

允许修改：

- `scripts/preview/server.py`
- `scripts/preview/static/`
- `tests/test_preview_server.py`

展示：

- gate summary。
- page-level findings。
- active overrides。
- delivery readiness。
- final artifact validation。
- delivery outcome form。

操作：

- create override。
- revoke override。
- mark delivered。
- record customer reaction。

验收：

- UI 可展示 `pass/conditional_pass/rework_required/not_applicable`。
- 操作写 artifact 和 event。
- 旧 approve/reject/note 不回归。

---

## 7. P5A：Local Team Solution Deck Factory

P5A 目标：在本地文件系统和 Git 语境下支持轻量团队协作。P5B 外部系统集成只做 contract，不接实时服务。

P5A 前置条件：P4-E 完成。

### P5A-A：Team Identity

允许修改：

- `scripts/team/identity.py`
- `scripts/deck_master.py`
- `tests/test_team_identity.py`

产物：

```text
team/users.json
team/roles.json
team/permissions.json
team/audit_log.jsonl
```

并发规则：

- JSON 写入使用临时文件加原子替换。
- audit log 只 append。
- 同一 user_id 重复创建时报错。

验收：

- add user。
- assign role。
- list audit。
- 个人本地模式继续可用。

### P5A-B：Opportunity Model

允许修改：

- `scripts/team/opportunity.py`
- `tests/test_opportunity_model.py`

产物：

```text
opportunities/<opp_id>/opportunity.json
opportunities/<opp_id>/runs/
opportunities/<opp_id>/exports/
opportunities/<opp_id>/outcomes/
```

命令：

```bash
python3 scripts/deck_master.py opportunity create --workspace <ws> --client-name <name> --industry <industry>
python3 scripts/deck_master.py opportunity attach-run --workspace <ws> --opportunity-id <id> --run-id <run_id>
```

验收：

- run 可关联到 opportunity。
- opportunity 可聚合 run history 和 delivery outcomes。

### P5A-C：Approval Flow

允许修改：

- `scripts/team/approval.py`
- `tests/test_approval_flow.py`

产物：

```text
team/approval_flows.json
team/approval_requests.jsonl
```

规则：

- final export requested 时可提交审批。
- 审批通过后才允许 client delivery handback。
- 审批拒绝写 finding 或 review note。

验收：

- submit/approve/reject 可运行。
- 审批动作写 audit log。
- export 读取 approval 状态。

### P5A-D：Team Dashboards

允许修改：

- `scripts/team/dashboard.py`
- `tests/test_team_dashboard.py`

产物：

```text
dashboards/team_quality_dashboard.json
dashboards/asset_usage_dashboard.json
```

指标：

- run count。
- average draft gate score。
- P0/P1 finding count。
- approved page rate。
- historical reuse rate。
- delivered deck count。
- top failure modes。

验收：

- 从多个 run 聚合 dashboard。
- 缺 run 时输出空 dashboard。

### P5A-E：Solution Package

允许修改：

- `scripts/team/solution_package.py`
- `tests/test_solution_package.py`

产物：

```text
packages/solution_packages/<package_id>.json
```

内容：

- industry。
- best_for。
- recommended_archetypes。
- claim_patterns。
- slide_assets。
- quality_policy_refs。
- example_runs。

验收：

- 可从已交付 run 创建 package。
- 可在新 run 应用 package，写入 workspace refs。

### P5B：Connector Import Contract

P5B 只定义离线导入契约，不接飞书、CRM、SharePoint、Notion 实时 API。

允许修改：

- `docs/schemas/connector_import.schema.json`
- `scripts/connectors/import_contract.py`
- `tests/test_connector_import_contract.py`

输入：

```json
{
  "schema_version": "deck_connector_import.v1",
  "source_system": "feishu_export",
  "source_export_id": "export_001",
  "source_files": [
    {
      "path": "context/meeting_transcript.md",
      "source_kind": "meeting_transcript",
      "sha256": "..."
    }
  ],
  "redaction_status": "reviewed",
  "import_policy": {
    "allow_sensitive_raw_text": false,
    "store_source_pointer_only": true
  }
}
```

验收：

- 本地导出包可导入 context manifest。
- 未 redaction 的高敏来源被拒绝。
- 不调用外部实时 API。

---

## 8. 推荐执行顺序

| 顺序 | 任务 | 能否并行 | 阻断关系 |
|---:|---|---|---|
| 0 | S0-A Workspace Foundation | 否 | P2-P5 前置 |
| 1 | S0-B Typed Events | 可与 S0-A 后半并行 | S0-C/S0-E 前置 |
| 2 | S0-F Schema Helper | 可与 S0-B 并行 | 所有新增 artifact 前置 |
| 3 | S0-C Next Step Resolver | 否 | Agent 可恢复执行前置 |
| 4 | S0-D Review Status Migration | 可与 S0-C 并行 | P4/P5 审批前置 |
| 5 | S0-E Export Quality Blocking | 否 | P4 前置 |
| 6 | P2-A Judgment | 否 | P2-B 前置 |
| 7 | P2-B Claim Graph | 否 | P2-C/P2-D 前置 |
| 8 | P2-C Planner v2 | 否 | P3/P4 前置 |
| 9 | P2-D Draft Gate 2.0 | 可与 P2-E 并行 | P4 前置 |
| 10 | P2-E Narrative UI | 可并行 | UI 增强 |
| 11 | P3-A/P3-B Asset Schema/Ingestion | 否 | P3-C/P3-E 前置 |
| 12 | P3-C/P3-D Feedback/Health | 可并行 | P3-E 前置 |
| 13 | P3-E Sourcing Scoring v2 | 否 | P4 Context Gate 前置 |
| 14 | P3-F Asset UI | 可并行 | UI 增强 |
| 15 | P4-A/P4-B/P4-C Gates | 可拆分并行 | P4-F 前置 |
| 16 | P4-D Brand Gate | 可并行 | P4-F 读取 |
| 17 | P4-E Override | 否 | P4-F/Export 前置 |
| 18 | P4-F Delivery | 否 | P5 Approval 前置 |
| 19 | P4-G Governance UI | 可并行 | UI 增强 |
| 20 | P5A-A/P5A-B Team/Opportunity | 可并行 | P5A-C 前置 |
| 21 | P5A-C Approval | 否 | P5A-D/P5A-E 前置 |
| 22 | P5A-D/P5A-E Dashboard/Package | 可并行 | P5A 完成 |
| 23 | P5B Connector Contract | 可独立 | 后续企业集成前置 |

---

## 9. 总测试矩阵

| 阶段 | 测试文件 | 核心用例 |
|---|---|---|
| S0 | `tests/test_workspace_foundation.py` | init/register/validate workspace |
| S0 | `tests/test_runtime_events.py` | typed event 兼容旧事件 |
| S0 | `tests/test_next_step.py` | artifact 缺失时给出下一步 |
| S0 | `tests/test_preview_manifest.py` | review status migration |
| S0 | `tests/test_export_quality_blocking.py` | P0/P1 阻断 export |
| P2 | `tests/test_consulting_judgments.py` | context/brief 生成 judgments |
| P2 | `tests/test_claim_evidence_graph.py` | claim/evidence/page links 完整 |
| P2 | `tests/test_narrative_planner.py` | 每页有 decision intent |
| P2 | `tests/test_draft_gate_v2.py` | 缺 evidence 阻断 |
| P3 | `tests/test_asset_schema.py` | canonical ID 稳定 |
| P3 | `tests/test_asset_ingestion.py` | library candidate 注册 |
| P3 | `tests/test_asset_feedback.py` | approved/rejected/delivered 反哺 |
| P3 | `tests/test_sourcing_scoring_v2.py` | scoring 阈值和稳定 tie-breaker |
| P4 | `tests/test_evidence_gate.py` | required evidence 缺失 |
| P4 | `tests/test_context_conflict_gate.py` | 客户语境冲突 |
| P4 | `tests/test_confidentiality_gate.py` | forbidden terms 和敏感来源 |
| P4 | `tests/test_brand_gate.py` | render artifact 可用性 |
| P4 | `tests/test_overrides.py` | override 政策 |
| P4 | `tests/test_delivery_validation.py` | page count/hash/lineage |
| P5A | `tests/test_team_identity.py` | users/roles/audit |
| P5A | `tests/test_opportunity_model.py` | opportunity attach run |
| P5A | `tests/test_approval_flow.py` | submit/approve/reject |
| P5A | `tests/test_team_dashboard.py` | 聚合团队指标 |
| P5A | `tests/test_solution_package.py` | create/apply package |
| P5B | `tests/test_connector_import_contract.py` | 离线导入契约 |
| All | `tests/test_end_to_end_autoplan.py` | 零售 fixture 到 preview/export |

每个任务最少执行：

```bash
python3 -m unittest <对应测试文件>
python3 -m unittest discover -s tests
```

---

## 10. Definition of Done

任意任务完成必须满足：

1. 对应 CLI 或 API 可运行。
2. 新 artifact 有 `schema_version`。
3. 关键步骤写 typed event。
4. 坏 JSON 不覆盖旧文件。
5. 对应测试新增或更新。
6. 全量 unittest 通过，或明确说明失败原因和无关性。
7. 不破坏现有主链路命令。
8. 文档中无错误路径。
9. 遵守仓库 `AGENTS.md` 文案要求。
10. `git status` 中只包含本任务相关文件。

---

## 11. 交接给 Claude Code 的任务包示例

### 示例 1：Sprint 0-A

```text
你正在开发 MainQuestAI/Deck-Master。
请阅读 docs/deck-master-p2-p5-development-guide.md。
本次只执行 S0-A：Workspace Foundation。

允许修改：
- scripts/deck_master.py
- scripts/workspace/
- tests/test_workspace_foundation.py
- docs/schemas/workspace.schema.json

验收：
- init-workspace/register-workspace/validate-workspace 可运行。
- 新 workspace 目录完整。
- reference PPT 只登记路径与元数据。
- python3 -m unittest tests/test_workspace_foundation.py 通过。
- python3 -m unittest discover -s tests 通过。
```

### 示例 2：P3-E

```text
你正在开发 MainQuestAI/Deck-Master。
请阅读 docs/deck-master-p2-p5-development-guide.md。
本次只执行 P3-E：Sourcing Scoring v2。

允许修改：
- scripts/planning/sourcing_decider.py
- scripts/assets/scoring.py
- tests/test_sourcing_decider.py
- tests/test_sourcing_scoring_v2.py

验收：
- scoring 权重与阈值按文档实现。
- 相同输入稳定输出相同 sourcing decision。
- 高客户语境冲突候选降级。
- 缺截图候选不能进入 reuse。
```

### 示例 3：P4-E

```text
你正在开发 MainQuestAI/Deck-Master。
请阅读 docs/deck-master-p2-p5-development-guide.md。
本次只执行 P4-E：Override Governance。

允许修改：
- scripts/quality/overrides.py
- scripts/deck_master.py
- tests/test_overrides.py

验收：
- override create/list/revoke 可运行。
- P0 不能进入 client export override。
- P1 override 必须有 approver 和 expires_at。
- override 写 typed event。
```

