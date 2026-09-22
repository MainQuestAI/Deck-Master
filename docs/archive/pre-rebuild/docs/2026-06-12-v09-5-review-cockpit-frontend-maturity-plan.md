# Deck Master v0.9.5 Review Cockpit Frontend Maturity Plan

日期：2026-06-12
状态：PR #2 后续项计划
适用分支：PR #2 合并后的下一轮迭代

---

## 1. 结论

PR #2 当前已完成 v0.9 Agentic Integration 后端 contract 与 F1/F2/F3 API 主链路。下一轮 v0.9.5 的目标，是把这些后端能力收成一个可持续使用的 localhost Review Cockpit 前端体验。

本计划不重新设计 Agentic contract，不改外部 handoff / handback schema，不扩大到商业团队协作版。核心任务是让用户在浏览器里完成审查、阻断处理、生成结果确认和导出判断。

---

## 2. 背景

PR #2 最新复查结论：

- 3 个 blocking contract gap 已修复。
- 2 个 state-source gap 已修复。
- 580 tests 全部通过。
- 真实 smoke 链路通过：external review import -> generation refresh -> review approve -> export queue -> metrics。
- PR 描述和 QA 报告已明确：F1/F2/F3 backend APIs and Agentic contract 已完成，完整 F.7 front-end cockpit UI 作为后续项。

因此 v0.9.5 应该承接前端体验，避免继续在 v0.9 PR 里堆后端范围。

---

## 3. 成功标准

v0.9.5 完成时，用户应当能在 localhost Cockpit 中完成一次 run 的核心审查闭环：

1. 看清 Deck readiness：整体状态、质量阻断、生成状态、导出状态。
2. 看清 claim coverage：每个核心论点是否有页面和证据支撑。
3. 看清 next actions：优先处理 P0/P1、证据缺口、生成失败、占位页。
4. 对页面执行 approve / reject / request evidence / convert to generate / lock source / add note。
5. 查看 narrative advice、external quality review、generation results。
6. 触发 export queue，并理解哪些页面进入队列，哪些被质量门禁挡住。
7. 看见 metrics 摘要：页数、审批数、质量问题数、来源决策分布。

---

## 4. Scope

### 4.1 Review Cockpit 首页

首页应直接进入 run 审查工作台，避免让用户先理解底层 artifacts。

需要展示：

- 当前 run 标题、创建时间、状态。
- Readiness 总览。
- 质量阻断摘要。
- 待处理动作列表。
- 进入页面列表和 claim coverage 的入口。

### 4.2 Deck Readiness Panel

读取现有 `GET /api/review-summary/<run_id>`。

展示：

- overall。
- narrative / evidence / generation / quality / export 五个维度。
- approved / rejected / needs_review。
- reuse / adapt / generate / manual_placeholder。
- P0 / P1 / P2。

### 4.3 Claim Coverage Matrix

读取现有 `GET /api/claim-coverage/<run_id>`。

展示：

- claim statement。
- linked pages。
- evidence refs。
- status：covered / evidence_gap / review_required / uncovered / blocked。
- 对 evidence_gap 和 blocked 给出明显视觉提示。

### 4.4 Next Actions

读取现有 `GET /api/next-actions/<run_id>`。

展示：

- action_type。
- target page / claim。
- severity。
- message。
- refs。

每个 action 尽量提供对应跳转，例如跳到页面、质量报告或 claim。

### 4.5 Page Decision Workbench

复用现有 `POST /api/page/<page_id>/review-action`。

需要支持：

- approve。
- reject。
- request_evidence。
- convert_to_generate。
- replace_candidate。
- move_to_appendix。
- lock_source。
- create_override。
- rerun_generation。
- add_note。

前端必须把失败原因直接显示给用户，例如 P0 finding 阻断 approve、缺失 preview_manifest、无效 action。

### 4.6 External Result Visibility

读取现有 `GET /api/external-results/<run_id>`。

展示：

- narrative advice 摘要。
- external reviews 列表和 finding 数。
- generation results 列表、状态和 preview asset。

### 4.7 Export Queue Preview

基于现有 export queue 逻辑增加前端展示。

需要展示：

- 可导出页面。
- 被阻断页面。
- 阻断原因。
- 是否存在 override。

### 4.8 Studio Create Run Follow-up

当前 Studio create-run 仍是轻路径。v0.9.5 可以补一个最小升级：

- 支持选择 `planning_mode=narrative_v2`。
- 明确显示 run 创建后下一步。
- 显示 Context Pack / local source flow 的入口状态。

如果实现成本升高，可把 Studio create-run 升级拆到 v0.9.6。

---

## 5. Non-goals

v0.9.5 不纳入：

- 新 Agent runtime。
- 新 LLM provider。
- 新 external result schema。
- 新 PPT 生成器。
- 完整团队协作、权限、远程 workspace。
- Benchmark 系统。
- 大规模视觉重设计。

---

## 6. 验收方式

### 6.1 自动化验证

- `python3 -m unittest discover -s tests`
- `git diff --check main...HEAD`
- 内置 LLM provider 扫描保持 clean。

### 6.2 浏览器 smoke

用一个真实 run 验证：

1. 打开 Review Cockpit。
2. readiness 正确显示。
3. claim coverage 正确显示。
4. next actions 正确显示。
5. approve 一个无阻断页面。
6. reject 一个页面并显示原因。
7. 查看 external results。
8. 查看 export queue。
9. 刷新页面后状态仍一致。

### 6.3 数据一致性验收

必须确认：

- approve / reject 后 `preview_manifest.json` 与页面 UI 一致。
- export queue 与页面审批状态一致。
- generation result refresh 后 UI 使用 `preview_path`。
- readiness / metrics 与 `preview_manifest`、`sourcing_plan`、`generation_tasks/index.json` 一致。

---

## 7. 建议开发包

建议拆成 3 个提交或 3 个小任务：

1. Cockpit shell + readiness / claim / next actions 展示。
2. Page Decision Workbench 完整动作和错误态。
3. External results + export queue + browser smoke 报告。

每个任务都要保持后端 contract 不变，只消费现有 API。
