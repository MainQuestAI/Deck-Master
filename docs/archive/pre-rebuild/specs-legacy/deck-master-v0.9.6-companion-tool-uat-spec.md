# Deck Master v0.9.6 Companion Tool UAT & Real Workflow Smoke Spec

日期：2026-06-12
状态：开发主控 Spec v0.1
适用范围：Deck Master v0.9.6
优先级：P0
核心定位：验证 Deck Master 与 PPT Library / PPT Deck Pro Max / PPT Master 的真实交接质量，为 v0.9.7 Benchmark Harness 做准备

---

## 0. Executive Summary

v0.9.6 的目标聚焦于 companion tool 交接验收：通过 UAT runner、contract validator 和真实 smoke，把 PPT Library、PPT Deck Pro Max、PPT Master 与 Deck Master 的交接从“schema 层可用”推进到“真实工作流可验证”。本版本不重做三个 companion tools，也不把 Deck Master 扩展成工具调度平台。

完成后，Deck Master 应具备：

1. PPT Library 结果 UAT：候选页字段、截图、canonical id、source file、page number、confidence、候选覆盖率。
2. PPT Deck Pro Max 生成 UAT：generation task 可消费、generation result 可导入、preview 可刷新。
3. PPT Master 渲染 UAT：render result 可验证、artifact 可进入 Render / Delivery Gate。
4. Real Workflow Smoke：以一个真实或 fixture case 跑通 Deck Master + companion tool contracts。
5. UAT Reports：所有 UAT 输出标准 JSON / Markdown 报告，便于后续 benchmark 读取。

---

## 1. 背景与当前基线

### 1.1 已完成能力

当前 Deck Master 已经有：

- `validate-ppt-library-result`
- `validate-generation-result`
- `validate-render-result`
- `prepare-generation-handoff`
- `import-generation-result`
- `refresh-preview-from-generation`
- `summarize-run-metrics`
- `quality-gate render`
- `quality-gate delivery`
- `delivery validate`
- `export`

v0.9.6 应在这些能力之上增加 UAT 层，并保持核心 contract 不变。

### 1.2 为什么需要 UAT

v0.9 的 contract 已经证明“JSON 能 import / validate”，但真实使用时还需要证明：

- PPT Library 真实返回的 selection 是否字段稳定。
- 600+ 历史 PPT 资产库返回的候选页是否有可用截图。
- sourcing decision 是否能消费真实候选。
- generation task 是否能被 PPT Deck Pro Max 实际消费。
- generation result 的 preview_path 是否真实可用。
- PPT Master render result 是否能进入 Render / Delivery Gate。
- 整条链路能否支持后续 benchmark。

---

## 2. 产品目标

### 2.1 用户故事

作为 Deck Master 使用者，我希望在开始真实 benchmark 前，先确认本地 companion tool chain 是健康的：

- PPT Library 是否能返回高质量候选页。
- PPT Deck Pro Max 是否能消费 Deck Master generation task。
- PPT Master 是否能输出可验证的 render / delivery artifact。
- 如果某个工具结果不合格，Deck Master 能告诉我具体缺哪些字段或资产。

### 2.2 成功标准

v0.9.6 完成后：

- 可以对 PPT Library selection JSON 生成 UAT report。
- 可以对 generation task/result 生成 UAT report。
- 可以对 PPT Master render result 生成 UAT report。
- 可以执行一个 real workflow smoke，并输出 smoke report。
- UAT report 能被 v0.9.7 benchmark harness 读取。
- 不引入任何内置 LLM provider。
- 不直接调用或实现 companion tool 内部逻辑，只校验输入输出和路径可用性。

---

## 3. Non-goals

v0.9.6 不做：

- 不实现 PPT Library 检索引擎。
- 不实现 PPT 解析、截图、embedding、索引。
- 不实现 PPT Deck Pro Max 页面生成。
- 不实现 PPT Master 渲染引擎。
- 不做 benchmark 结论。
- 不做 Web dashboard。
- 不做多 Agent 调度。
- 不做团队协作产品。
- 不引入 LLM provider。

---

## 4. 新增目录与产物

### 4.1 UAT 目录

每个 run 下新增：

```text
runs/<run_id>/
  uat_reports/
    ppt_library_uat.json
    ppt_library_uat.md
    generation_tool_uat.json
    generation_tool_uat.md
    render_tool_uat.json
    render_tool_uat.md
    real_workflow_smoke.json
    real_workflow_smoke.md
```

### 4.2 UAT Report 通用结构

```json
{
  "schema_version": "deck_uat_report.v1",
  "run_id": "retail-demo",
  "tool": "ppt_library",
  "status": "pass",
  "created_at": "2026-06-12T00:00:00Z",
  "summary": {
    "checks": 18,
    "passed": 16,
    "warnings": 2,
    "failed": 0
  },
  "metrics": {},
  "findings": [
    {
      "finding_id": "pptlib_warning_missing_canonical_id",
      "severity": "warning",
      "message": "3 candidates missing canonical_slide_id.",
      "refs": ["library_results/selection.json"]
    }
  ],
  "recommendations": [
    "补齐 canonical_slide_id 以支持长期 asset feedback。"
  ]
}
```

状态：

| status | 含义 |
|---|---|
| pass | 可用于真实 smoke / benchmark |
| warning | 可继续，但需要关注 |
| fail | 不建议进入 benchmark |
| not_applicable | 当前 run 没有相关 artifact |

严重级别：

| severity | 含义 |
|---|---|
| error | 会阻断 UAT pass |
| warning | 不阻断，但影响质量 |
| info | 信息提示 |

---

## 5. Package A：UAT Core

### 5.1 目标

建立 UAT report 的通用 builder、writer、Markdown renderer。

### 5.2 新增模块

```text
scripts/uat/__init__.py
scripts/uat/report.py
```

### 5.3 核心函数

```python
build_uat_report(
    run_dir: Path,
    tool: str,
    checks: list[dict],
    metrics: dict,
    recommendations: list[str],
) -> dict

write_uat_report(
    run_dir: Path,
    name: str,
    report: dict,
) -> dict

render_uat_markdown(report: dict) -> str
```

### 5.4 验收

- UAT report 有 `schema_version`。
- 同时输出 JSON 和 Markdown。
- bad JSON 不覆盖旧 report。
- 所有 UAT 操作写 typed event。

---

## 6. Package B：PPT Library UAT

### 6.1 目标

验证 PPT Library selection result 是否足够支撑 Deck Master sourcing / preview / asset feedback。

### 6.2 新增命令

```bash
python3 scripts/deck_master.py uat-ppt-library \
  --run-dir <run_dir> \
  --input <run_dir>/library_results/selection.json
```

可选参数：

```bash
--require-screenshot
--min-candidate-coverage 0.7
--min-screenshot-coverage 0.8
--min-confidence 0.4
```

### 6.3 检查项

| 检查项 | 级别 | 说明 |
|---|---|---|
| selection JSON 可读取 | error | 坏 JSON 直接 fail |
| run_id 匹配 | error | 与 request.json 不一致 fail |
| 每个 beat 有 candidates | warning/error | 根据 coverage 阈值判断 |
| candidate 有 slide_id | error | 必需 |
| candidate 有 source_file | error | 必需 |
| candidate 有 page_number | warning | 强建议 |
| candidate 有 screenshot_path | warning/error | 根据 require-screenshot 判断 |
| screenshot_path 存在 | warning/error | 根据 require-screenshot 判断 |
| confidence 在 0-1 | error | 超出 fail |
| canonical_slide_id 存在 | warning | 建议用于 feedback |
| title / text_summary 存在 | warning | 建议用于 Review UI |
| duplicate slide_id | warning | 可能影响 asset feedback |

### 6.4 输出指标

```json
{
  "candidate_count": 132,
  "beat_count": 14,
  "beats_with_candidates": 12,
  "candidate_coverage": 0.86,
  "screenshot_coverage": 0.91,
  "canonical_id_coverage": 0.78,
  "avg_confidence": 0.63,
  "missing_screenshot_count": 12,
  "duplicate_slide_id_count": 3
}
```

### 6.5 验收

- 支持 fixture 和真实 PPT Library selection。
- 能指出哪些 beat 没有候选。
- 能指出哪些 candidate 缺截图。
- 能生成 `uat_reports/ppt_library_uat.json` 和 `.md`。
- 不修改 `library_results/selection.json`。

---

## 7. Package C：Generation Tool UAT

### 7.1 目标

验证 PPT Deck Pro Max 或其他 generation tool 能消费 Deck Master generation task，并正确 handback result。

### 7.2 新增命令

```bash
python3 scripts/deck_master.py uat-generation-tool \
  --run-dir <run_dir> \
  --tool ppt-deck-pro-max
```

可选：

```bash
--require-preview
--require-artifact
--sample-limit 3
```

### 7.3 检查项

#### Generation Task Checks

| 检查项 | 级别 |
|---|---|
| `generation_tasks/index.json` 存在 | error |
| index 中有 tasks[] 或 task_ids[] | error |
| task 有 schema_version | error |
| task 有 run_id | error |
| task 有 task_id / beat_id | error |
| task 有 generation_brief | warning |
| task 有 workspace_refs | warning |
| task 有 quality_requirements | warning |
| task 有 expected_outputs | warning |

#### Generation Result Checks

| 检查项 | 级别 |
|---|---|
| generation_results 存在 | warning |
| result run_id 匹配 | error |
| result task_id 对应存在 | error |
| status 合法 | error |
| completed 有 preview_path 或 artifact_path | error |
| failed 有 errors[] | error |
| preview_path 是 run-relative | error |
| preview_path 存在 | error if require-preview |
| artifact_path 存在 | error if require-artifact |

#### Preview Refresh Checks

| 检查项 | 级别 |
|---|---|
| refresh-preview-from-generation 可执行 | error |
| 更新后的 preview_manifest 可通过 load_manifest | error |
| generated 页面 source_type=generated | warning |
| previous_preview_path 被保留 | warning |
| generation_status 写入 | warning |

### 7.4 输出指标

```json
{
  "task_count": 8,
  "enhanced_task_count": 8,
  "result_count": 5,
  "completed_count": 4,
  "failed_count": 1,
  "partial_count": 0,
  "preview_refresh_updated": 4,
  "preview_asset_coverage": 0.8,
  "artifact_coverage": 0.6
}
```

### 7.5 验收

- 可验证真实 generation task。
- 可验证真实 generation result。
- 可执行 refresh preview。
- 可生成 `uat_reports/generation_tool_uat.json` 和 `.md`。
- 不调用 PPT Deck Pro Max 内部实现。

---

## 8. Package D：Render Tool UAT

### 8.1 目标

验证 PPT Master 或渲染工具输出是否能进入 Deck Master Render / Delivery Gate。

### 8.2 新增命令

```bash
python3 scripts/deck_master.py uat-render-tool \
  --run-dir <run_dir> \
  --input render_result.json
```

或者：

```bash
python3 scripts/deck_master.py uat-render-tool \
  --run-dir <run_dir> \
  --artifact exports/final.pptx
```

### 8.3 Render Result Contract

支持两种输入：

#### Render Result JSON

```json
{
  "schema_version": "deck_render_result.v1",
  "run_id": "retail-demo",
  "tool": "ppt-master",
  "status": "completed",
  "artifact_path": "exports/retail-demo.pptx",
  "preview_dir": "exports/previews/",
  "page_count": 14,
  "errors": []
}
```

#### Direct Artifact

如果只传 `--artifact`，则 UAT 尝试使用现有 delivery validate / render gate 对 artifact 做最小检查。

### 8.4 检查项

| 检查项 | 级别 |
|---|---|
| render_result JSON 可读取 | error |
| run_id 匹配 | error |
| status 合法 | error |
| artifact_path 存在 | error |
| artifact_path 在 run_dir 内或显式 allow external | warning/error |
| page_count 与 approved queue 接近 | warning |
| preview_dir 存在 | warning |
| render gate 可运行 | warning/error |
| delivery validate 可运行 | warning/error |
| final_version_lineage 可生成 | warning |

### 8.5 输出指标

```json
{
  "artifact_exists": true,
  "page_count": 14,
  "expected_page_count": 12,
  "page_count_delta": 2,
  "render_gate_status": "pass",
  "delivery_validation_status": "pass"
}
```

### 8.6 验收

- 能校验 PPT Master render result。
- 能对 final artifact 跑最小 delivery validation。
- 能生成 `uat_reports/render_tool_uat.json` 和 `.md`。
- 不实现 PPT 渲染。

---

## 9. Package E：Real Workflow Smoke Runner

### 9.1 目标

提供一个标准 smoke 命令，用来验证真实工作流状态，不追求完全自动化。

### 9.2 新增命令

```bash
python3 scripts/deck_master.py smoke-real-workflow \
  --run-dir <run_dir>
```

或：

```bash
python3 scripts/deck_master.py smoke-real-workflow \
  --case retail-demo \
  --workspace <workspace> \
  --runs-dir <runs_dir>
```

### 9.3 Smoke 检查链路

基础检查：

```text
request.json exists
context_manifest.json exists
deck_brief.json exists
claim_map.json exists
narrative_plan.json exists
page_tasks.json exists
sourcing_plan.json exists
generation_tasks/index.json exists
preview_manifest.json exists
quality_reports/draft_gate.json or draft_v2_gate.json exists
```

Agentic contract 检查：

```text
advisor_tasks/narrative_advice_task.json exists or can prepare
advisor_results/narrative_advice.json optional
quality_review_tasks/* exists or can prepare
external_*_gate.json optional
generation_results/* optional
```

Review / Export 检查：

```text
review-summary API computable
claim-coverage computable
next-actions computable
export queue computable
run metrics computable
```

UAT 检查：

```text
ppt_library_uat exists or can run
generation_tool_uat exists or can run
render_tool_uat optional
```

### 9.4 输出

```text
uat_reports/real_workflow_smoke.json
uat_reports/real_workflow_smoke.md
```

示例：

```json
{
  "schema_version": "deck_real_workflow_smoke.v1",
  "run_id": "retail-demo",
  "status": "warning",
  "summary": {
    "required_checks": 18,
    "passed": 15,
    "warnings": 3,
    "failed": 0
  },
  "phases": {
    "run_artifacts": "pass",
    "agentic_contract": "warning",
    "review_export": "pass",
    "companion_uat": "warning"
  },
  "next_actions": [
    "Run uat-generation-tool after PPT Deck Pro Max result is available.",
    "Import external quality review before client export."
  ]
}
```

### 9.5 验收

- smoke 不要求所有外部工具产物存在。
- 缺 external result 时输出 warning 和 suggested next action。
- 缺核心 run artifact 时输出 fail。
- 输出 JSON 和 Markdown。
- 可被 v0.9.7 benchmark harness 读取。

---

## 10. Package F：Docs & UAT Playbooks

### 10.1 更新文档

新增或更新：

```text
docs/uat/ppt-library-contract-uat.md
docs/uat/ppt-deck-pro-max-contract-uat.md
docs/uat/ppt-master-contract-uat.md
docs/uat/real-workflow-smoke.md
skills/deck-master/playbooks/ppt-library-handoff.md
skills/deck-master/playbooks/ppt-deck-pro-max-handoff.md
skills/deck-master/playbooks/codex-run-solution-deck.md
```

### 10.2 文档必须回答

- Codex 如何调用 PPT Library。
- PPT Library selection 应输出什么字段。
- Deck Master 如何 validate selection。
- Codex 如何调用 PPT Deck Pro Max。
- PPT Deck Pro Max 应如何写 generation result。
- Deck Master 如何 refresh preview。
- PPT Master render result 如何进入 delivery validation。
- 真实 smoke 如何执行。

---

## 11. 测试要求

### 11.1 单元测试

新增：

```text
tests/test_uat_report.py
tests/test_uat_ppt_library.py
tests/test_uat_generation_tool.py
tests/test_uat_render_tool.py
tests/test_smoke_real_workflow.py
```

### 11.2 核心测试

```text
ppt library UAT: valid selection -> pass
ppt library UAT: missing screenshot -> warning or fail
ppt library UAT: run_id mismatch -> fail

generation UAT: task index tasks[] -> pass
generation UAT: completed result preview_path missing -> fail if require-preview
generation UAT: preview_path outside run -> fail
generation UAT: refresh preview updates manifest

render UAT: valid render_result -> pass
render UAT: missing artifact -> fail
render UAT: page_count delta -> warning

real workflow smoke: complete fixture run -> pass/warning
real workflow smoke: missing preview_manifest -> fail
```

### 11.3 回归命令

```bash
python3 -m unittest discover -s tests
git diff --check main...HEAD
```

---

## 12. Definition of Done

v0.9.6 完成条件：

- `uat-ppt-library` 可用。
- `uat-generation-tool` 可用。
- `uat-render-tool` 可用。
- `smoke-real-workflow` 可用。
- UAT reports 输出 JSON + Markdown。
- UAT reports 可被后续 benchmark 读取。
- 文档和 Skill Playbook 更新。
- 不引入 LLM provider。
- 不重做 companion tools。
- 单元测试通过。
- 至少一个 fixture run 的 real workflow smoke 通过。
- 至少一个真实本地 run 能输出 UAT reports，允许 warning。

---

## 13. Codex 执行提示模板

```text
你正在开发 MainQuestAI/Deck-Master。

请阅读：
- docs/deck-master-v0.9-agentic-integration-review-maturity-spec.md
- docs/specs/deck-master-v0.9.6-companion-tool-uat-spec.md
- docs/uat/ppt-library-contract-uat.md
- docs/uat/ppt-deck-pro-max-contract-uat.md
- docs/uat/ppt-master-contract-uat.md

本次只实现 v0.9.6 Companion Tool UAT & Real Workflow Smoke。

必须遵守：
- 不内置任何 LLM provider。
- 不实现 PPT Library / PPT Deck Pro Max / PPT Master 内部能力。
- 只做 contract validation、UAT report、real workflow smoke。
- 所有新增 artifact 必须有 schema_version。
- 所有 UAT 操作写 typed events。
- bad JSON 不覆盖旧 report。
- 保持现有测试套件通过。

完成后输出：
- 修改文件清单。
- 新增命令清单。
- UAT report 示例路径。
- 测试命令和结果。
- 已知限制。
```
