# Real Workflow Smoke

## 目标

Real workflow smoke 用来确认一个 Deck Master run 是否已经具备进入真实 companion tool 验收和后续 benchmark 的基础条件。它只检查 Deck Master 侧的交接产物、关键状态和 UAT 报告，不调用 PPT Library、PPT Deck Pro Max 或 PPT Master 的内部能力。

## 预期入口

```bash
python3 scripts/deck_master.py smoke-real-workflow --run-dir runs/<run_id>
```

预期 Python 接口：

```python
from scripts.uat.real_workflow_smoke import run_real_workflow_smoke

report = run_real_workflow_smoke(run_dir=Path("runs/retail-demo"))
```

## 必检产物

核心 run 产物缺失时应返回 `fail`：

- `request.json`
- `context_manifest.json`
- `deck_brief.json`
- `claim_map.json`
- `narrative_plan.json`
- `page_tasks.json`
- `sourcing_plan.json`
- `generation_tasks/index.json`
- `preview_manifest.json`
- `quality_reports/draft_gate.json` 或 `quality_reports/draft_v2_gate.json`

外部工具产物缺失时优先返回 `warning`，并在 `next_actions` 里说明下一步：

- `uat_reports/ppt_library_uat.json`
- `uat_reports/generation_tool_uat.json`
- `uat_reports/render_tool_uat.json`
- `generation_results/*.json`
- `advisor_results/narrative_advice.json`
- `quality_review_tasks/*.json`

独立运行 smoke 时，`warning` 仍用于定位缺失证据。进入 full-tier RC 时，
`pass` 是唯一放行状态；任一 phase 为 `warning` 或 `fail` 都会阻断 RC。

## 输出

smoke 应写出：

```text
runs/<run_id>/uat_reports/real_workflow_smoke.json
runs/<run_id>/uat_reports/real_workflow_smoke.md
```

JSON 报告使用独立 schema：

```json
{
  "schema_version": "deck_real_workflow_smoke.v1",
  "run_id": "uat-8b66f8a97e8a96ac",
  "status": "warning",
  "summary": {
    "required_checks": 10,
    "passed": 9,
    "warnings": 2,
    "failed": 0
  },
  "phases": {
    "run_artifacts": "pass",
    "agentic_contract": "warning",
    "review_export": "pass",
    "companion_uat": "warning"
  },
  "findings": [],
  "next_actions": [
    "Run uat-generation-tool after PPT Deck Pro Max result is available."
  ]
}
```

## 单元测试覆盖

- 完整 fixture run 返回 `pass` 或 `warning`。
- 缺少 `preview_manifest.json` 返回 `fail`。
- `companion_uat` 在必需 UAT 报告存在时返回 `pass`。
- 输出结构可被 v0.9.7 benchmark harness 读取。

## 边界

- 不生成 Deck 内容。
- 不渲染 PPT。
- 不修改 companion tool 输出。
- 不引入任何内置 LLM provider。
- 真实 UAT 只读取 run 副本，不修改原始 run。
- UAT 报告默认将原始 `run_id` 替换为稳定的 `uat-<sha256-prefix>`，并递归清理
  metrics、findings 和 recommendations 中的原始 ID。
- JSON/Markdown evidence 会在写出后扫描绝对路径、原始 source 字段和
  `DECK_MASTER_EVIDENCE_FORBIDDEN_MARKERS` 指定的私有标识；命中后删除输出并失败。

## RC 入口

CI tier 只运行 fresh clone 可复现检查，不要求真实 run：

```bash
python3 scripts/deck_master.py rc-gate --tier ci --output-dir <output_dir> --skip-browser-smoke
```

full tier 必须显式传入系统 temp 根下的隔离 UAT 副本，并可重复传入私有标识扫描项。
HOME、仓库/worktree、`~/.deck-master/runs`、非 temp 目录、带软链接的副本路径，
以及副本内部任意文件或目录软链接都会被拒绝。扫描不会跟随软链接目标：

```bash
python3 scripts/deck_master.py rc-gate \
  --tier full \
  --benchmark-dir <benchmark_dir> \
  --uat-run-dir <read_only_run_copy> \
  --evidence-forbidden-marker <private_marker> \
  --output-dir <output_dir>
```

full tier 会直接读取副本中的真实产物：

- PPT Library selection：优先读取 `external/ppt_library/library_results.v2.json`，
  兼容 `library_results/selection.json`、`ppt-library-selection.json` 和
  `ppt_library_selection.json`。
- Sourcing：读取 `sourcing_plan.json`。
- 两者必须为 v2；selection 必须具备逐页 identity chain 且没有绝对路径和 raw
  source 字段；sourcing 必须使用 `pages[]`、一页一决策且 selected `asset_key`
  全局无重复。
- 每个 sourcing selected source 必须按 `page_task_id + query_trace_id + asset_key`
  命中同页 selection candidate；可选的 `candidate_id`、`source_asset_id` 和
  `slide_id` 若存在也必须一致。generate/gap 页允许 `selected_sources=[]`。

artifact 缺失、v1、schema 无效或安全扫描失败都会阻断 full RC。CI tier 继续只运行
仓库内 synthetic contract checks，不读取本机 UAT、PPT Library 或 benchmark evidence。
