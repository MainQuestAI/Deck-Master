# Deck Master v0.9.5 Review Cockpit Frontend Maturity Spec

日期：2026-06-12
状态：开发主控 Spec v0.1
适用范围：Deck Master v0.9.5
优先级：P0
第一运行环境：Codex-first 本地 Agent 工作流
核心定位：将 v0.9 已完成的 Agentic backend contract 收敛为可日常使用的 localhost Review Cockpit 前端体验

---

## 0. Executive Summary

v0.9.5 的目标聚焦于前端审查工作台：把 v0.9 已完成的 F1/F2/F3 后端 API 收成一个可持续使用的 localhost Review Cockpit，不新增后端 Agent contract，也不扩展商业团队版。

完成后，用户应能在浏览器里完成一次 Deck run 的核心审查闭环：

1. 看清 Deck readiness：整体状态、质量阻断、生成状态、导出状态。
2. 看清 claim coverage：每个核心论点是否有页面和证据支撑。
3. 看清 next actions：优先处理 P0/P1、证据缺口、生成失败、占位页。
4. 对页面执行 approve / reject / request evidence / convert to generate / lock source / add note。
5. 查看 narrative advice、external quality review、generation results。
6. 查看 export queue，并理解哪些页面进入队列、哪些被质量门禁挡住。
7. 看见 metrics 摘要：页数、审批数、质量问题数、来源决策分布。

v0.9.5 是 Deck Master 从“后端 contract 成熟”进入“用户真实可用”的关键版本。

---

## 1. 背景与当前基线

### 1.1 已完成能力

v0.9 已经完成：

- Skill Packaging & Installation。
- Agent Context Pack Contract。
- Narrative Advisory Contract。
- External Quality Review Contract。
- Build Tool Handoff / Handback Contract。
- Review Cockpit F1/F2/F3 后端 API。
- Workspace Learning Pack。
- Companion Tool Validators。
- Lightweight Metrics Hooks。
- Workbench approve / reject 与 `preview_manifest.json` 同步。
- Generation refresh 写入正式 `preview_path` runtime 字段。
- Readiness / Metrics 改为读取真实状态源。

当前可用 API：

```text
GET  /api/review-summary/<run_id>
GET  /api/claim-coverage/<run_id>
GET  /api/next-actions/<run_id>
GET  /api/external-results/<run_id>
POST /api/page/<page_id>/review-action?run_id=<run_id>
GET  /api/quality-governance/<run_id>
GET  /api/page/<page_id>?run_id=<run_id>
GET  /api/deck?run_id=<run_id>
```

### 1.2 当前问题

当前前端仍偏基础 preview UI，用户需要理解多个 artifact 才能完成审查。v0.9.5 应将信息组织为“审查决策工作台”，避免继续堆 JSON 面板。

---

## 2. 产品目标

### 2.1 用户故事

作为 AI 解决方案架构师，我希望打开 localhost Review Cockpit 后，立刻知道：

- 这份 Deck 是否可以进入客户可审查草案。
- 哪些页面已通过，哪些页面被拒绝，哪些还需要处理。
- 哪些 claim 没有页面或证据支撑。
- 哪些 P0/P1 finding 正在阻断交付。
- 哪些生成页失败或缺 preview asset。
- 下一步最值得处理的 5 件事是什么。
- 我可以直接在页面上 approve / reject / request evidence / convert to generate / lock source / add note。

### 2.2 成功标准

v0.9.5 完成后：

- 用户不需要打开 JSON 文件即可完成主审查流程。
- UI 中显示的状态与 `preview_manifest.json`、`sourcing_plan.json`、`generation_tasks/index.json`、`quality_reports/` 一致。
- UI 操作不绕过 Quality Gate。
- approve / reject 后 export queue 状态一致。
- 浏览器刷新后状态仍一致。
- 无任何内置 LLM provider。
- 不修改 v0.9 Agentic contract schema。

---

## 3. Non-goals

v0.9.5 不做：

- 新 LLM provider。
- 新 Agent runtime。
- 新 Context Pack / Narrative Advice / External Review schema。
- 新 PPT 生成器。
- 新 PPT Library 能力。
- Benchmark 系统。
- 团队协作、远程 workspace、权限系统。
- 大规模视觉重设计。
- 移动端主体验。
- 复杂实时协作或 WebSocket。

---

## 4. 信息架构

### 4.1 页面布局

推荐保持三栏结构，但强化顶部状态区和右侧工作台：

```text
┌──────────────────────────────────────────────────────────────┐
│ Top Bar: Run title / status / next-step / export readiness    │
├───────────────┬──────────────────────────────┬───────────────┤
│ Left Rail     │ Center Preview                │ Right Cockpit │
│ - Run list    │ - slide preview               │ - Page status │
│ - Page list   │ - asset missing state         │ - Actions     │
│ - Filters     │ - page navigation             │ - Findings    │
├───────────────┴──────────────────────────────┴───────────────┤
│ Bottom / Side Panels: Readiness / Claim Coverage / Next Actions│
└──────────────────────────────────────────────────────────────┘
```

### 4.2 主要模块

| 模块 | 数据来源 | 用途 |
|---|---|---|
| Deck Readiness Panel | `/api/review-summary/<run_id>` | 判断整体是否 ready / blocked / needs_review |
| Claim Coverage Matrix | `/api/claim-coverage/<run_id>` | 判断每个 claim 是否有页面和证据支撑 |
| Next Actions | `/api/next-actions/<run_id>` | 给出下一步最优处理顺序 |
| Page Decision Workbench | `/api/page/<page_id>` + `/review-action` | 页面级审批与处理 |
| External Result Visibility | `/api/external-results/<run_id>` | 展示 narrative advice / external review / generation result |
| Quality Governance | `/api/quality-governance/<run_id>` | 展示阻断、override、delivery readiness |
| Export Queue Preview | 新增或复用 export queue API | 展示可导出与被阻断页面 |
| Metrics Summary | `summarize-run-metrics` 或新增 API | 显示页数、审批数、质量问题和来源分布 |

---

## 5. API 需求

### 5.1 已有 API 必须继续稳定

不得破坏：

```text
GET  /api/deck
GET  /api/page/<page_id>
POST /api/page/<page_id>/decision
POST /api/page/<page_id>/review-action
GET  /api/review-summary/<run_id>
GET  /api/claim-coverage/<run_id>
GET  /api/next-actions/<run_id>
GET  /api/external-results/<run_id>
GET  /api/quality-governance/<run_id>
```

### 5.2 建议新增 API：Export Queue Preview

新增：

```text
GET /api/export-queue/<run_id>?queue_type=client&decision=approved&allow_quality_override=false
```

返回：

```json
{
  "run_id": "retail-demo",
  "queue_type": "client",
  "pages": [
    {
      "page_id": "beat_001",
      "order": 1,
      "title": "客户现状诊断",
      "decision": "approved",
      "preview_path": "links/beat_001.svg",
      "quality_override_active": false
    }
  ],
  "blocked_pages": [
    {
      "page_id": "beat_009",
      "order": 9,
      "title": "ROI 价值测算",
      "quality_blocked": true,
      "quality_block_reason": "P1 quality findings without active override: ['roi_evidence_gap']"
    }
  ]
}
```

实现要求：

- 复用 `orchestrate.export_queue.export_queue()`。
- 不复制 quality blocking 逻辑。
- 返回被阻断页面和原因。
- 对 bad run_id 返回 404 / 400。

### 5.3 建议新增 API：Run Metrics Summary

新增：

```text
GET /api/run-metrics/<run_id>
```

返回：

```json
{
  "schema_version": "deck_run_metrics.v1",
  "run_id": "retail-demo",
  "durations": {
    "created_to_preview_minutes": 18.2,
    "preview_to_first_quality_gate_minutes": 3.1
  },
  "counts": {
    "pages": 14,
    "approved": 5,
    "rejected": 2,
    "needs_review": 7,
    "reuse": 3,
    "adapt": 4,
    "generate": 5,
    "manual_placeholder": 2,
    "quality_findings": 11,
    "p0": 0,
    "p1": 3,
    "p2": 8
  }
}
```

实现要求：

- 复用 `metrics.run_metrics.summarize_run_metrics()`。
- 不要求写入 `run_metrics.json`，除非 CLI 命令明确触发。
- 前端只读展示。

---

## 6. 前端功能需求

### 6.1 Cockpit Shell

显示：

- Run title。
- Run status。
- Page count。
- 当前 selected page。
- Overall readiness。
- Export readiness。
- Draft gate / external gate blocking summary。

状态标签建议：

| 状态 | 文案 |
|---|---|
| ready | 可进入导出准备 |
| needs_review | 仍需人工审查 |
| blocked | 存在质量阻断 |
| pending | 数据尚未生成 |
| partial | 部分生成或部分审查完成 |

### 6.2 Deck Readiness Panel

读取：

```text
GET /api/review-summary/<run_id>
```

展示：

- overall。
- narrative / evidence / generation / quality / export。
- pages / approved / rejected / needs_review。
- reuse / adapt / generate / manual_placeholder。
- P0 / P1 / P2。

UI 要求：

- P0/P1 高亮。
- export blocked 时显示原因入口。
- approved > 0 且 quality pass 时显示可预览 export queue。

### 6.3 Claim Coverage Matrix

读取：

```text
GET /api/claim-coverage/<run_id>
```

展示字段：

- claim statement。
- linked pages。
- evidence refs。
- status。

状态解释：

| status | UI 行为 |
|---|---|
| covered | 正常 |
| evidence_gap | 黄色提示 |
| review_required | 蓝色提示 |
| uncovered | 橙色提示 |
| blocked | 红色提示 |

交互：

- 点击 page refs 跳转页面。
- 点击 evidence refs 显示 refs 字符串。
- evidence_gap 显示 `request_evidence` 操作建议。

### 6.4 Next Actions

读取：

```text
GET /api/next-actions/<run_id>
```

展示：

- priority。
- action_type。
- target。
- severity。
- message。
- refs。

交互建议：

| action_type | 推荐动作 |
|---|---|
| fix_quality_finding | 跳到对应页面和 Quality Findings |
| fix_evidence_gap | 跳到 Claim Coverage |
| resolve_placeholder | 跳到对应页面，建议 request evidence |
| rerun_generation | 跳到 Page Workbench generation 状态 |
| generate_preview | 跳到页面 preview 状态 |

### 6.5 Page Decision Workbench

读取：

```text
GET /api/page/<page_id>?run_id=<run_id>
```

动作：

```text
POST /api/page/<page_id>/review-action?run_id=<run_id>
```

支持操作：

| 操作 | UI 元素 | 请求体 |
|---|---|---|
| approve | 主按钮 | `{ "action": "approve", "actor": "user", "note": "" }` |
| reject | 主按钮 + reason | `{ "action": "reject", "reason": "..." }` |
| request_evidence | 按钮 + reason | `{ "action": "request_evidence", "reason": "..." }` |
| convert_to_generate | 按钮 | `{ "action": "convert_to_generate" }` |
| lock_source | toggle / button | `{ "action": "lock_source" }` |
| add_note | 文本框 | `{ "action": "add_note", "note": "..." }` |
| move_to_appendix | 次级按钮 | `{ "action": "move_to_appendix" }` |
| rerun_generation | 次级按钮 | `{ "action": "rerun_generation" }` |
| create_override | 高风险按钮 | `{ "action": "create_override", "finding_id": "...", "approver": "...", "reason": "..." }` |

要求：

- 所有动作后重新拉取 page payload、review summary、next actions。
- approve 失败时必须显示后端错误，例如 P0 finding 阻断。
- create_override 必须显示风险说明，不作为默认入口。
- 不再只使用 legacy `/decision` 作为主要审批入口，但保留兼容。

### 6.6 External Result Visibility

读取：

```text
GET /api/external-results/<run_id>
```

展示：

- narrative advice：
  - advisor。
  - core thesis。
  - page recommendations 数量。
  - deck-level risks 数量。
- external reviews：
  - reviewer。
  - scope。
  - P0/P1/P2 数量。
  - findings 列表。
- generation results：
  - task_id。
  - beat_id。
  - tool。
  - status。
  - preview_path。
  - errors。

要求：

- failed generation 显示明显状态。
- P0/P1 external findings 显示到 Page Workbench 和 Next Actions。
- 不允许在前端编辑 external result JSON。

### 6.7 Export Queue Preview

读取新增 API：

```text
GET /api/export-queue/<run_id>?queue_type=client
```

展示：

- pages：可导出页面。
- blocked_pages：被阻断页面。
- quality_block_reason。
- quality_override_active。
- 页面 order / title / source_type / decision。

要求：

- 用户能理解“approved 但不能导出”的原因。
- P0 阻断不可 override。
- P1 有 override 时标记为 override active。

### 6.8 Metrics Summary

读取新增 API：

```text
GET /api/run-metrics/<run_id>
```

展示：

- pages / approved / rejected / needs_review。
- reuse / adapt / generate / manual_placeholder。
- p0 / p1 / p2。
- created_to_preview_minutes。
- preview_to_first_quality_gate_minutes。

要求：

- 标注这是 lightweight metrics，不能作为 v1.0 benchmark 结论。
- 空值显示为 `-`，不要报错。

---

## 7. 数据一致性要求

### 7.1 状态源

| 数据 | Source of Truth |
|---|---|
| 页面审批状态 | `preview_manifest.json.pages[].review_status / decision` |
| 来源决策分布 | `sourcing_plan.json.decisions[]` |
| 生成任务状态 | `generation_tasks/index.json` + individual task files |
| 生成结果 | `generation_results/*.json` |
| 预览资产 | `preview_manifest.json.pages[].preview_path` |
| 质量问题 | `quality_reports/*_gate.json` |
| claim coverage | `claim_evidence_graph.json` |
| next actions | `quality_reports` + `claim_evidence_graph` + `generation_tasks` + `preview_manifest` |

### 7.2 UI 刷新策略

每次页面动作后，必须刷新：

- 当前 page payload。
- review summary。
- next actions。
- export queue preview。
- metrics summary。

### 7.3 错误处理

前端必须显示：

- run not found。
- preview asset missing。
- P0 blocks approval。
- invalid action。
- export queue blocked。
- quality report bad JSON。
- external result bad JSON。

---

## 8. 实现边界

### 8.1 可修改文件建议

优先修改：

```text
scripts/preview/static/index.html
scripts/preview/static/app.js
scripts/preview/static/style.css
scripts/preview/server.py
tests/test_review_cockpit.py
tests/test_review_workbench.py
tests/test_preview_server.py 或新增 tests/test_review_cockpit_frontend_contract.py
docs/2026-06-12-v09-5-review-cockpit-frontend-maturity-plan.md
```

### 8.2 不建议修改

除非必要，不改：

```text
scripts/context_intake/context_pack.py
scripts/advisory/narrative.py
scripts/quality/external_review.py
scripts/generation/handback.py
scripts/orchestrate/export_queue.py
scripts/metrics/run_metrics.py
```

如果需要新增 export queue / metrics API，只在 `server.py` 中复用现有函数。

---

## 9. 测试要求

### 9.1 单元测试

新增或补齐：

```text
GET /api/export-queue/<run_id>
GET /api/run-metrics/<run_id>
review-action approve -> UI/API summary refresh data source
review-action reject -> export queue excludes page
export queue API returns blocked_pages
metrics API returns counts
external-results API returns narrative/review/generation result
```

### 9.2 浏览器 Smoke

用真实 run 验证：

1. 打开 Review Cockpit。
2. readiness 正确显示。
3. claim coverage 正确显示。
4. next actions 正确显示。
5. approve 一个无阻断页面。
6. reject 一个页面并显示原因。
7. 查看 external results。
8. 查看 generation result。
9. 查看 export queue。
10. 查看 metrics summary。
11. 刷新页面后状态一致。

### 9.3 回归命令

```bash
python3 -m unittest discover -s tests
git diff --check main...HEAD
```

LLM provider scan 保持 clean：

```bash
grep -R "openai\|anthropic\|gemini\|OPENAI_API_KEY\|ANTHROPIC_API_KEY" -n scripts skills docs tests || true
```

---

## 10. Definition of Done

v0.9.5 完成条件：

- Cockpit 首页可以承载 run 审查。
- Deck Readiness Panel 可用。
- Claim Coverage Matrix 可用。
- Next Actions 可用。
- Page Decision Workbench 至少支持 approve / reject / request_evidence / convert_to_generate / lock_source / add_note。
- External Results 可见。
- Export Queue Preview 可见。
- Metrics Summary 可见。
- 所有页面操作写 typed events。
- approve / reject 与 export queue 一致。
- 质量阻断不能被 UI 绕过。
- 浏览器 smoke 通过。
- 单元测试通过。
- 文档更新。

---

## 11. Codex 执行提示模板

```text
你正在开发 MainQuestAI/Deck-Master。

请阅读：
- docs/deck-master-v0.9-agentic-integration-review-maturity-spec.md
- docs/2026-06-12-v09-5-review-cockpit-frontend-maturity-plan.md
- docs/specs/deck-master-v0.9.5-review-cockpit-frontend-spec.md

本次只实现 v0.9.5 Review Cockpit Frontend Maturity。

必须遵守：
- 不新增任何 LLM provider。
- 不改 external Agent contract schema。
- 不重做 PPT Library / PPT Deck Pro Max / PPT Master。
- 前端只消费现有 F1/F2/F3 API，必要时新增 export queue / metrics 只读 API。
- 页面审批状态以 preview_manifest 为 source of truth。
- 所有 review-action 操作不能绕过 Quality Gate。
- 保持 python3 -m unittest discover -s tests 通过。

完成后输出：
- 修改文件列表。
- 新增 API 列表。
- 浏览器 smoke 结果。
- 测试命令和结果。
- 已知限制。
```
