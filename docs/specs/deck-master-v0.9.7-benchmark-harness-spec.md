# Deck Master v0.9.7 Benchmark Harness Spec

日期：2026-06-12
状态：开发主控 Spec v0.1
适用范围：Deck Master v0.9.7
优先级：P0
核心定位：建立可复用的 Benchmark Harness，为用户真实工作流验证与 v1.0.0 RC 10x Readiness 做准备

---

## 0. Executive Summary

v0.9.7 的目标是建立 benchmark 的机制，不直接宣称 Deck Master 已经达到 10x。

v0.9.7 完成后，用户可以定义 benchmark case，用 Deck Master 按标准流程创建 run、导入 context、记录外部 Agent 和 companion tool 产物、收集 metrics、汇总 UAT / quality / export / review 结果，并输出 benchmark report。

v0.9.7 是用户开始结合真实工作流使用 Deck Master 的前置版本。用户使用反馈和真实 benchmark 数据将决定 v1.0.0 RC 是否达标。

---

## 1. 背景与当前基线

### 1.1 已有基础

当前 Deck Master 已有：

- `summarize-run-metrics`
- `run_metrics.json`
- Context Pack Contract。
- Narrative Advice Contract。
- External Quality Review Contract。
- Generation Handoff / Handback。
- Review Cockpit backend APIs。
- Export Queue。
- Workspace Learning Pack。
- v0.9.6 计划中的 UAT reports。

### 1.2 为什么现在可以做 benchmark

在 v0.9.5 和 v0.9.6 完成后，Deck Master 将具备：

1. 可用 Review Cockpit。
2. 可验证 companion tool handoff / handback。
3. 可读 run metrics。
4. 可输出 UAT reports。
5. 可记录 external Agent 产物。
6. 可执行质量门禁和 export blocking。

因此 v0.9.7 可以开始建立 benchmark harness，将真实使用过程结构化。

---

## 2. 产品目标

### 2.1 用户故事

作为 Deck Master 的主要用户，我希望可以定义一个 benchmark case，然后在我的实际工作流中执行：

- 创建 run。
- 导入 Context Pack。
- 跑 narrative_v2。
- 导入 Narrative Advice。
- 导入 External Quality Review。
- 接收 PPT Library / PPT Deck Pro Max / PPT Master 结果。
- 在 Review Cockpit 中完成审查。
- 导出 approved queue。
- 生成 benchmark report。

最终，我需要知道：

- 这次 run 到可审查草案花了多久。
- 页面通过率是多少。
- 证据缺口在哪里。
- 历史页复用是否有效。
- 生成结果是否可用。
- 外部审查是否发现关键质量问题。
- 是否接近 12 小时到 2 小时的目标。

### 2.2 成功标准

v0.9.7 完成后：

- 可以创建 benchmark case。
- 可以执行 benchmark-run。
- 可以从已有 run 生成 benchmark report。
- 可以读取 run_metrics、UAT reports、quality_reports、export queue、review outcomes。
- 可以输出 JSON + Markdown benchmark report。
- 可以作为 v1.0.0 RC 的真实验证基础。
- 不要求本版本跑出 10x 结论。
- 不引入任何 LLM provider。
- 不做 Web dashboard。

---

## 3. Non-goals

v0.9.7 不做：

- 不宣称 v1.0.0 正式达标。
- 不做复杂 benchmark dashboard。
- 不做统计学实验平台。
- 不自动调用 LLM。
- 不自动调用所有 companion tools。
- 不替代 Codex / Claude Code 的推理。
- 不强制所有 benchmark 全自动。
- 不做团队协作或远程数据上报。
- 不将 benchmark 数据上传到外部服务。

---

## 4. Benchmark 目录结构

新增：

```text
benchmarks/
  README.md
  cases/
    retail_fixture/
      benchmark_case.json
      context_pack.json
      expected_outcomes.md
    real_case_template/
      benchmark_case.json
      README.md
  results/
    <case_id>/
      <run_id>/
        benchmark_report.json
        benchmark_report.md
        run_metrics.json
        uat_summary.json
        artifact_index.json
```

也支持在外部 workspace 中指定 benchmark 目录：

```bash
--benchmark-dir /path/to/benchmarks
```

---

## 5. Benchmark Case Schema

### 5.1 文件

```text
benchmarks/cases/<case_id>/benchmark_case.json
```

### 5.2 Schema

```json
{
  "schema_version": "deck_benchmark_case.v1",
  "case_id": "retail_inventory_visibility",
  "case_name": "零售全渠道库存可视化方案",
  "description": "验证 Deck Master 是否能从客户上下文生成可审查 Solution Deck 草案。",
  "industry": "retail",
  "audience": "client",
  "target_pages": 15,
  "workspace": "benchmarks/workspaces/retail",
  "runs_dir": "benchmark_runs",
  "inputs": {
    "context_pack": "context_pack.json",
    "baseline_manual_hours": 12,
    "baseline_notes": "历史上同类方案从思路确认到草案约 12 小时。",
    "expected_output_type": "solution_deck_draft"
  },
  "workflow": {
    "planning_mode": "narrative_v2",
    "library_mode": "fixture",
    "requires_narrative_advice": true,
    "requires_external_quality_review": true,
    "requires_generation_result": false,
    "requires_render_result": false,
    "manual_review_required": true
  },
  "success_targets": {
    "context_to_preview_minutes": 45,
    "context_to_review_ready_minutes": 90,
    "context_to_approved_queue_minutes": 120,
    "page_acceptance_rate_min": 0.5,
    "reuse_adapt_rate_min": 0.3,
    "p0_count_max": 0,
    "evidence_gap_visible": true,
    "quality_gate_required": true
  },
  "scoring": {
    "weights": {
      "efficiency": 0.35,
      "page_acceptance": 0.20,
      "evidence_readiness": 0.15,
      "asset_reuse": 0.15,
      "quality_governance": 0.15
    }
  }
}
```

### 5.3 校验规则

| 字段 | 规则 |
|---|---|
| schema_version | 必须等于 `deck_benchmark_case.v1` |
| case_id | 必填，文件名安全 |
| case_name | 必填 |
| target_pages | 可选，若填写必须为正整数 |
| inputs.context_pack | 可选，但推荐 |
| baseline_manual_hours | 必填，允许小数 |
| workflow.planning_mode | `classic` 或 `narrative_v2` |
| success_targets | 至少包含一个目标 |
| scoring.weights | 可选，若存在总和建议约等于 1 |

---

## 6. Benchmark Run 模式

### 6.1 Semi-automated Mode

默认模式：

```bash
python3 scripts/deck_master.py benchmark-run \
  --case benchmarks/cases/retail_fixture/benchmark_case.json \
  --benchmark-dir benchmarks \
  --mode semi-auto
```

行为：

1. 创建或复用 run。
2. 导入 context pack。
3. build brief。
4. build claim map。
5. autoplan narrative_v2。
6. quality-gate draft_v2。
7. summarize-run-metrics。
8. 收集已有 UAT reports。
9. 生成 benchmark report。

如果需要 Narrative Advice / External Review / Generation Result，但相关 artifact 不存在，report 中输出 `pending_external_agent`，并给出 suggested next actions。

### 6.2 From Existing Run Mode

用于用户真实工作流后补 benchmark：

```bash
python3 scripts/deck_master.py benchmark-report \
  --case benchmarks/cases/real_customer_case/benchmark_case.json \
  --run-dir runs/<run_id>
```

行为：

- 不改变 run。
- 只读取 artifacts。
- 生成 benchmark report。
- 适合真实项目复盘。

### 6.3 Manual Checkpoint Mode

用于记录用户人工审查时间：

```bash
python3 scripts/deck_master.py benchmark-checkpoint \
  --run-dir runs/<run_id> \
  --checkpoint human_review_started

python3 scripts/deck_master.py benchmark-checkpoint \
  --run-dir runs/<run_id> \
  --checkpoint human_review_completed
```

支持 checkpoint：

```text
context_ready
preview_ready
human_review_started
human_review_completed
approved_queue_ready
final_delivery_ready
```

写入：

```text
runs/<run_id>/benchmark_checkpoints.json
```

---

## 7. Benchmark Report

### 7.1 输出文件

```text
benchmarks/results/<case_id>/<run_id>/benchmark_report.json
benchmarks/results/<case_id>/<run_id>/benchmark_report.md
```

### 7.2 JSON Report

```json
{
  "schema_version": "deck_benchmark_report.v1",
  "case_id": "retail_inventory_visibility",
  "run_id": "retail-demo",
  "created_at": "2026-06-12T00:00:00Z",
  "status": "completed",
  "readiness": {
    "overall": "needs_review",
    "export_ready": false,
    "quality_blocked": true
  },
  "efficiency_metrics": {
    "baseline_manual_hours": 12,
    "created_to_preview_minutes": 35.2,
    "preview_to_first_quality_gate_minutes": 4.3,
    "context_to_approved_queue_minutes": null,
    "human_review_minutes": null,
    "estimated_time_saved_hours": null
  },
  "page_metrics": {
    "pages": 14,
    "approved": 5,
    "rejected": 2,
    "needs_review": 7,
    "page_acceptance_rate": 0.36
  },
  "source_metrics": {
    "reuse": 3,
    "adapt": 4,
    "generate": 5,
    "manual_placeholder": 2,
    "reuse_adapt_rate": 0.5
  },
  "quality_metrics": {
    "p0": 0,
    "p1": 3,
    "p2": 8,
    "evidence_gap_count": 4,
    "external_review_findings": 6
  },
  "generation_metrics": {
    "task_count": 8,
    "completed": 4,
    "failed": 1,
    "partial": 0,
    "generation_success_rate": 0.5
  },
  "uat_summary": {
    "ppt_library": "pass",
    "generation_tool": "warning",
    "render_tool": "not_applicable",
    "real_workflow_smoke": "warning"
  },
  "target_evaluation": {
    "context_to_preview": "pass",
    "context_to_approved_queue": "pending",
    "page_acceptance_rate": "fail",
    "reuse_adapt_rate": "pass",
    "p0_count": "pass"
  },
  "score": {
    "overall": 0.62,
    "efficiency": 0.8,
    "page_acceptance": 0.4,
    "evidence_readiness": 0.5,
    "asset_reuse": 0.9,
    "quality_governance": 0.6
  },
  "recommendations": [
    "补齐 ROI 页面证据后再进行第二轮 benchmark。",
    "将 beat_009 从 generate 改为 manual_placeholder 或降低 claim 强度。"
  ]
}
```

### 7.3 Markdown Report

Markdown 应包含：

1. Case summary。
2. Run summary。
3. Efficiency metrics。
4. Page metrics。
5. Source metrics。
6. Quality metrics。
7. Generation metrics。
8. UAT summary。
9. Target evaluation。
10. Recommendations。
11. Artifact index。

---

## 8. 指标定义

### 8.1 Efficiency Metrics

| 指标 | 来源 | 含义 |
|---|---|---|
| baseline_manual_hours | benchmark_case | 手工基线 |
| created_to_preview_minutes | run_metrics | run 创建到 preview |
| preview_to_first_quality_gate_minutes | run_metrics | preview 到第一轮 quality gate |
| context_to_approved_queue_minutes | events/checkpoints | 到 approved queue |
| human_review_minutes | checkpoints | 人工审查耗时 |
| estimated_time_saved_hours | 计算 | baseline - actual |

### 8.2 Page Metrics

| 指标 | 来源 |
|---|---|
| pages | preview_manifest |
| approved | preview_manifest |
| rejected | preview_manifest |
| needs_review | preview_manifest |
| page_acceptance_rate | approved / pages |

### 8.3 Source Metrics

| 指标 | 来源 |
|---|---|
| reuse | sourcing_plan |
| adapt | sourcing_plan |
| generate | sourcing_plan |
| manual_placeholder | sourcing_plan |
| reuse_adapt_rate | (reuse + adapt) / pages |

### 8.4 Quality Metrics

| 指标 | 来源 |
|---|---|
| p0 | quality_reports |
| p1 | quality_reports |
| p2 | quality_reports |
| evidence_gap_count | claim_evidence_graph.gaps + quality findings |
| external_review_findings | external_*_gate.json |
| export_blocked_count | export queue blocked_pages |

### 8.5 Generation Metrics

| 指标 | 来源 |
|---|---|
| task_count | generation_tasks |
| completed | generation_results |
| failed | generation_results |
| partial | generation_results |
| generation_success_rate | completed / task_count |

### 8.6 UAT Metrics

| 指标 | 来源 |
|---|---|
| ppt_library | uat_reports/ppt_library_uat.json |
| generation_tool | uat_reports/generation_tool_uat.json |
| render_tool | uat_reports/render_tool_uat.json |
| real_workflow_smoke | uat_reports/real_workflow_smoke.json |

---

## 9. Target Evaluation

### 9.1 状态

| 状态 | 含义 |
|---|---|
| pass | 达成目标 |
| warning | 接近目标或有条件达成 |
| fail | 未达成 |
| pending | 数据缺失，尚不可判断 |
| not_applicable | 本 case 不适用 |

### 9.2 示例规则

```text
context_to_preview_minutes <= target => pass
context_to_preview_minutes <= target * 1.25 => warning
else fail

page_acceptance_rate >= target => pass
page_acceptance_rate >= target * 0.8 => warning
else fail

p0_count <= p0_count_max => pass
else fail
```

---

## 10. Benchmark Commands

### 10.1 validate-benchmark-case

```bash
python3 scripts/deck_master.py validate-benchmark-case \
  --case benchmarks/cases/retail_fixture/benchmark_case.json
```

输出：

```json
{
  "valid": true,
  "errors": [],
  "warnings": []
}
```

### 10.2 benchmark-run

```bash
python3 scripts/deck_master.py benchmark-run \
  --case benchmarks/cases/retail_fixture/benchmark_case.json \
  --benchmark-dir benchmarks \
  --mode semi-auto
```

输出：

```json
{
  "status": "completed",
  "case_id": "retail_fixture",
  "run_id": "bench-retail-fixture-001",
  "run_dir": "benchmark_runs/bench-retail-fixture-001",
  "report": "benchmarks/results/retail_fixture/bench-retail-fixture-001/benchmark_report.json"
}
```

### 10.3 benchmark-report

```bash
python3 scripts/deck_master.py benchmark-report \
  --case benchmarks/cases/retail_fixture/benchmark_case.json \
  --run-dir runs/<run_id>
```

### 10.4 benchmark-checkpoint

```bash
python3 scripts/deck_master.py benchmark-checkpoint \
  --run-dir runs/<run_id> \
  --checkpoint human_review_started
```

可选：

```bash
--timestamp 2026-06-12T10:00:00+08:00
--note "开始人工审查第一页"
```

### 10.5 benchmark-list

```bash
python3 scripts/deck_master.py benchmark-list \
  --benchmark-dir benchmarks
```

列出 cases 和 results。

---

## 11. 实现模块

建议新增：

```text
scripts/benchmark/__init__.py
scripts/benchmark/case.py
scripts/benchmark/checkpoints.py
scripts/benchmark/runner.py
scripts/benchmark/report.py
scripts/benchmark/scoring.py
scripts/benchmark/markdown.py
```

### 11.1 case.py

职责：

- 读取 benchmark_case.json。
- validate schema。
- resolve relative paths。
- 不创建 run。

### 11.2 checkpoints.py

职责：

- 记录 benchmark checkpoints。
- 读取 checkpoint timestamps。
- 计算 human_review_minutes。
- 写 typed event。

### 11.3 runner.py

职责：

- semi-auto benchmark-run。
- 调用已有 CLI 内部函数。
- 不调用 LLM。
- 遇到 external Agent step 缺失时记录 pending，不失败。

### 11.4 report.py

职责：

- 从 run_dir 收集 metrics。
- 读取 UAT reports。
- 读取 export queue。
- 读取 quality reports。
- 读取 claim graph。
- 生成 benchmark_report.json。

### 11.5 scoring.py

职责：

- target evaluation。
- score 计算。
- 支持 case-level weights。

### 11.6 markdown.py

职责：

- 输出 benchmark_report.md。
- 可读、适合放进 release report。

---

## 12. Artifact Index

Benchmark report 应生成 artifact index：

```json
{
  "artifact_index": {
    "request": "runs/<run_id>/request.json",
    "context_manifest": "runs/<run_id>/context_manifest.json",
    "deck_brief": "runs/<run_id>/deck_brief.json",
    "claim_graph": "runs/<run_id>/claim_evidence_graph.json",
    "preview_manifest": "runs/<run_id>/preview_manifest.json",
    "quality_reports": "runs/<run_id>/quality_reports/",
    "uat_reports": "runs/<run_id>/uat_reports/",
    "run_metrics": "runs/<run_id>/run_metrics.json"
  }
}
```

要求：

- 所有路径相对 benchmark root 或 repo root。
- 不包含客户敏感正文，只记录路径和摘要。
- 不上传外部系统。

---

## 13. 样例 Benchmark Case

### 13.1 retail_fixture

新增：

```text
benchmarks/cases/retail_fixture/
  benchmark_case.json
  context_pack.json
  expected_outcomes.md
```

目标：

- 使用 fixture library。
- 不要求真实 generation result。
- 验证 benchmark harness 可跑。
- 输出 benchmark report。

### 13.2 real_case_template

新增：

```text
benchmarks/cases/real_case_template/
  benchmark_case.json
  README.md
```

说明：

- 如何放置 context_pack。
- 如何在 Codex 中生成 narrative advice。
- 如何导入 external review。
- 如何导入 generation result。
- 如何记录 human review checkpoints。

---

## 14. Benchmark 与 v1.0.0 RC 的关系

v0.9.7 只建立 harness，不要求真实达标。

v1.0.0 RC 要求：

- 至少 3 个真实 case。
- 每个 case 至少 1 次完整 run。
- 至少 1 个 case 进行第二轮 learning pack 后复跑。
- 输出 `docs/releases/v1.0.0-rc-10x-readiness-report.md`。
- 判断是否达到“约 12 小时到约 2 小时可审查草案”。

建议 v1.0.0 RC 目标：

| 指标 | 目标 |
|---|---:|
| context_to_preview_minutes | <= 45 |
| context_to_first_quality_gate_minutes | <= 75 |
| context_to_approved_queue_minutes | <= 120 |
| page_acceptance_rate | >= 0.50 |
| reuse_adapt_rate | >= 0.30 |
| p0_count | 0 |
| generation preview refresh success | 100% for completed results |
| external review import success | 100% |
| user perceived usefulness | positive |

---

## 15. 测试要求

### 15.1 单元测试

新增：

```text
tests/test_benchmark_case.py
tests/test_benchmark_checkpoints.py
tests/test_benchmark_report.py
tests/test_benchmark_runner.py
tests/test_benchmark_scoring.py
```

### 15.2 核心用例

```text
validate valid benchmark case -> valid
validate missing baseline_manual_hours -> invalid
benchmark checkpoint writes file and event
benchmark report from existing run -> report json/md
benchmark report includes run_metrics
benchmark report includes uat summary
target evaluation pass/warning/fail/pending
semi-auto benchmark run with retail_fixture -> report generated
bad case JSON does not overwrite previous report
```

### 15.3 回归命令

```bash
python3 -m unittest discover -s tests
git diff --check main...HEAD
```

LLM provider scan 保持 clean。

---

## 16. Definition of Done

v0.9.7 完成条件：

- `validate-benchmark-case` 可用。
- `benchmark-run` 可用。
- `benchmark-report` 可用。
- `benchmark-checkpoint` 可用。
- `benchmark-list` 可用。
- benchmark case schema 落地。
- retail_fixture benchmark case 落地。
- real_case_template 落地。
- benchmark report JSON + Markdown 可生成。
- report 包含 efficiency / page / source / quality / generation / UAT / target evaluation。
- 不引入 LLM provider。
- 不做外部上传。
- 测试通过。
- 文档更新。
- 用户可以基于自己的真实 workflow 开始跑 benchmark。

---

## 17. Codex 执行提示模板

```text
你正在开发 MainQuestAI/Deck-Master。

请阅读：
- docs/deck-master-v0.9-agentic-integration-review-maturity-spec.md
- docs/specs/deck-master-v0.9.7-benchmark-harness-spec.md
- docs/specs/deck-master-v0.9.6-companion-tool-uat-spec.md

本次只实现 v0.9.7 Benchmark Harness。

必须遵守：
- v0.9.7 只建立 benchmark harness，不宣称 10x 达标。
- 不内置 LLM provider。
- 不自动调用外部 LLM。
- 不实现 PPT Library / PPT Deck Pro Max / PPT Master。
- Benchmark 可以 semi-auto，外部 Agent 缺失时记录 pending。
- 所有 benchmark artifacts 必须有 schema_version。
- 不覆盖旧 benchmark report，除非显式 --force。
- 写 typed events。
- 保持 python3 -m unittest discover -s tests 通过。

完成后输出：
- 修改文件清单。
- 新增命令清单。
- sample benchmark report 路径。
- 测试命令和结果。
- 当前 benchmark 能力边界。
```
