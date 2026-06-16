# Deck Master v0.9.12b Spec - Companion Workflow Contracts

## 1. 目标

在 v0.9.12a 的 suite runtime foundation 上，把 PPT Library、PPT Quality Gate、PPT Deck Pro Max 接入 Deck Master run。

本 Stack 重点是 contract、dry-run handoff、import 和 run-state 登记，不重写 companion skill 内部算法。

全局原则：companion output 只能作为 adapter input。Deck Master 内部继续以现有 canonical artifact 为状态源，不新增第二套 run state、quality gate、generation result 或 sourcing reader。

## 2. 非目标

- 不重写 PPT Library indexing/search internals。
- 不重写 PPT Deck Pro Max production algorithm。
- 不重写 Deck Master quality gate engine。
- 不做真实 PPT Library feedback writeback。
- 不做 PPT Master renderer 深集成。

## 3. 修改边界

允许修改：

```text
skills/deck-master/SKILL.md
skills/ppt-library/SKILL.md
skills/ppt-quality-gate/SKILL.md
skills/ppt-deck-pro-max/SKILL.md
scripts/deck_master.py
scripts/tools/ppt_library_client.py
scripts/planning/sourcing_decider.py
scripts/quality/*
scripts/generation/*
scripts/runtime/import_log.py
scripts/runtime/sourcing_import.py
docs/contracts/*
tests/*library* / tests/*quality* / tests/*generation* / tests/*import*
```

当前代码基线已确认存在 `scripts/tools`、`scripts/planning`、`scripts/quality`、`scripts/generation`、`scripts/runtime/sourcing_import.py`。本轮优先复用这些入口；不得新建平行 `scripts/integrations/*`，除非先证明现有模块无法承载并补兼容测试。

`skills/ppt-library/SKILL.md`、`skills/ppt-quality-gate/SKILL.md`、`skills/ppt-deck-pro-max/SKILL.md` 只有在 Stack A 的 Companion Skill Source Matrix 明确为 release bundle 且仓库内存在对应 package 时才允许修改。若 companion 是 external adopted skill，本 Stack 只更新 `skills/deck-master` 的 routing docs 和 contracts，不在仓库里临时创建 companion skill 目录。

## 4. Shared Import Log

新增共享 writer：

```text
scripts/runtime/import_log.py
runs/<run_id>/imports/import_log.jsonl
```

Log shape：

```json
{
  "schema_version": "deck_master_import_log.v1",
  "import_id": "imp_001",
  "run_id": "customer-run",
  "timestamp": "2026-06-16T00:00:00Z",
  "source_skill": "ppt-library",
  "source_artifact": "/absolute/path/selection.json",
  "artifact_sha256": "sha256...",
  "import_type": "library_selection",
  "status": "imported",
  "canonical_artifacts": [
    "external/ppt_library/library_results.json",
    "library_results/selection.json"
  ],
  "warnings": []
}
```

Rules:

- 新增 import 命令必须先校验 input，再原子写 canonical artifact，最后 append import log。
- rejected input 不得覆盖旧 artifact；可写 rejected log entry，但必须标记 `status: rejected` 并带 errors。
- `import_id` 可以由 timestamp + import_type + source hash 生成；测试只断言稳定字段和 idempotency 行为。
- Stack C 负责把既有旧 import 命令补齐 import log；Stack B 的新增 import 必须从第一版开始写 log。

## 5. PPT Library Read-Only Adapter

### 5.1 CLI

新增或扩展：

```bash
deck-master library-status [--workspace <path>] [--output json]
deck-master search-library --run-id <run_id> [existing options]
deck-master library-search --run-id <run_id> --beat-id <beat_id> --query <text> [--output json]
deck-master import-library-selection --run-id <run_id> --input <selection.json>
```

Compatibility rule:

- `search-library` 是现有主命令，必须保持可用。
- `library-search` 如新增，只能作为更细粒度 query alias，不能绕过 `search-library -> decide-sourcing` 现有链路。
- 若 adapter 写入新 contract，也必须能产出或同步更新现有 reader 使用的 `library_results/selection.json`。

### 5.2 Readiness Check

`library-status` 必须验证：

- `ppt-library` skill link status。
- `ppt-lib` CLI availability。
- `ppt-lib doctor --output json` 可运行。
- config path/database path readable。
- index/source readiness。
- high-risk directories 未被静默索引。
- screenshot paths are absolute when required。

### 5.3 Query Contract

新增：

```text
docs/contracts/ppt-library-query.v1.schema.json
```

建议输入：

```json
{
  "schema_version": "deck_master_ppt_library_query.v1",
  "run_id": "customer-run",
  "workspace": "/absolute/workspace",
  "request_id": "req_xxx",
  "beats": [
    {
      "beat_id": "beat_03_solution_map",
      "page_task_id": "page_03",
      "slot_id": "main_page",
      "role": "solution_overview",
      "brief": "Need a page showing the target solution architecture.",
      "industry": "pharma",
      "audience": "CIO / business sponsor",
      "evidence_need": ["architecture", "client_context"],
      "visual_need": "solution map",
      "reuse_modes_allowed": ["reuse", "adapt"],
      "source_policy": {
        "allow_confidential_sources": false,
        "allowed_source_profiles": ["formal_library"],
        "require_absolute_screenshot": true
      }
    }
  ],
  "top_k": 5
}
```

### 5.4 Selection Contract

新增：

```text
docs/contracts/ppt-library-selection.v1.schema.json
```

建议输出：

```json
{
  "schema_version": "deck_master_ppt_library_selection.v1",
  "run_id": "customer-run",
  "results": [
    {
      "beat_id": "beat_03_solution_map",
      "page_task_id": "page_03",
      "slot_id": "main_page",
      "query_trace_id": "lib_query_001",
      "candidates": [
        {
          "candidate_id": "cand_001",
          "slide_id": "slide_abc",
          "canonical_slide_id": "canonical_xxx",
          "source_deck_id": "deck_xxx",
          "source_file": "/absolute/path/to/source.pptx",
          "page_number": 12,
          "screenshot_path": "/absolute/path/to/screenshot.png",
          "screenshot_sha256": "sha256...",
          "title": "Solution architecture overview",
          "confidence": 0.82,
          "win_rate": 0.4,
          "reuse_mode_recommendation": "adapt",
          "retrieval_reason": "Matches architecture overview and pharma context.",
          "source_profile": "formal_library",
          "confidentiality": "internal_reuse_allowed",
          "risks": [],
          "evidence_refs": []
        }
      ],
      "warnings": []
    }
  ],
  "errors": []
}
```

### 5.5 Storage

```text
runs/<run_id>/external/ppt_library/library_results.json
runs/<run_id>/library_results/selection.json
runs/<run_id>/imports/import_log.jsonl
runs/<run_id>/sourcing_plan.json
```

要求：

- import 后才能影响 sourcing plan。
- bad JSON 不得覆盖已有 `external/ppt_library/library_results.json` 或 `library_results/selection.json`。
- 同 role 多 beats 必须按 `beat_id/page_task_id/slot_id` 保持映射。
- v0.9.12b 必须二选一：
  1. 同步写入兼容文件 `library_results/selection.json`，保留现有 `decide-sourcing` reader。
  2. 更新所有读取 `library_results/selection.json` 的代码，并补回归测试覆盖 autoplan / decide-sourcing / build-preview。
- 推荐选项 1，降低本轮 blast radius。

### 5.6 Canonical Adapter Mapping

Deck Master 的外部输入是 `deck_master_ppt_library_selection.v1`，内部 canonical compatibility file 仍是现有 `library_results/selection.json`。

Import 后必须同时写：

```json
{
  "source": "ppt_library",
  "schema_version": "deck_master_ppt_library_selection_compat.v1",
  "by_beat": {
    "beat_03_solution_map": [
      {
        "candidate_id": "cand_001",
        "slide_id": "slide_abc",
        "canonical_slide_id": "canonical_xxx",
        "beat_id": "beat_03_solution_map",
        "page_task_id": "page_03",
        "slot_id": "main_page",
        "query_trace_id": "lib_query_001",
        "role": "solution_overview",
        "title": "Solution architecture overview",
        "source_file": "/absolute/path/to/source.pptx",
        "page_number": 12,
        "screenshot_path": "/absolute/path/to/screenshot.png",
        "confidence": 0.82,
        "score": 0.82,
        "win_rate": 0.4,
        "reuse_mode_recommendation": "adapt",
        "retrieval_reason": "Matches architecture overview and pharma context.",
        "source_profile": "formal_library",
        "confidentiality": "internal_reuse_allowed",
        "risks": [],
        "evidence_refs": []
      }
    ]
  }
}
```

字段映射：

| External selection field | Compatibility target | Required |
|---|---|---:|
| `results[].beat_id` | `by_beat.<beat_id>[]` key and candidate `beat_id` | yes |
| `results[].page_task_id` | candidate `page_task_id` | yes |
| `results[].slot_id` | candidate `slot_id` | yes |
| `results[].query_trace_id` | candidate `query_trace_id` | yes |
| `results[].candidates[].candidate_id` | candidate `candidate_id` | yes |
| `confidence` | candidate `confidence` and fallback `score` | yes |
| `retrieval_reason` | candidate `retrieval_reason`; may also populate `importance_reason` for old readers | recommended |

Rules:

- `beat_id/page_task_id/slot_id` is the identity boundary; same role beats must not be merged.
- `decide-sourcing` output must retain `page_task_id`、`slot_id`、`query_trace_id` on decisions and selected candidates when present.
- Import must reject a selection where `run_id` does not match the target run.
- Import must reject duplicate `(beat_id, page_task_id, slot_id, candidate_id)` entries unless they are byte-identical idempotent repeats.

## 6. PPT Quality Gate Structured Import

### 6.1 Skill Promotion

将 `ppt-quality-gate` 从 draft 晋升为 release skill package。若脚本不存在，则删除或标注 script references，不得引用不存在脚本。

### 6.2 Output Contract

新增：

```text
docs/contracts/quality-findings.v1.schema.json
```

建议输出：

```json
{
  "schema_version": "deck_master_quality_findings.v1",
  "run_id": "customer-run",
  "source": {
    "skill": "ppt-quality-gate",
    "skill_version": "0.9.12"
  },
  "stage": "draft_gate",
  "artifact": {
    "type": "pptx",
    "path": "/absolute/path/to/deck.pptx",
    "sha256": "sha256..."
  },
  "findings": [
    {
      "finding_id": "qg_001",
      "gate_class": "external_semantic_alignment",
      "severity": "blocking",
      "page_number": 3,
      "beat_id": "beat_03_solution_map",
      "title": "Solution architecture claim is not supported by evidence.",
      "evidence": [],
      "repair_instruction": "Add client-specific system boundary and supporting evidence.",
      "import_action": "create_quality_finding"
    }
  ],
  "summary": {
    "blocking_count": 1,
    "warning_count": 3,
    "delivery_ready": false
  }
}
```

`gate_class` 固定映射到 Deck Master 现有 external quality review gate classes：

| PPT Quality Gate class | Deck Master gate file / class | 用途 |
|---|---|---|
| `external_semantic_alignment` | `external_semantic_*_gate.json` | 叙事、页级主张、客户语义一致性 |
| `external_visual_readiness` | `external_visual_*_gate.json` | 视觉密度、版式、截图可读性 |
| `external_evidence_coverage` | `external_evidence_*_gate.json` | 证据、截图、来源、主张支撑 |
| `external_client_readiness` | `external_client_readiness_*_gate.json` | 对外交付语言、内部痕迹、最终交付风险 |

Unsupported `gate_class` 必须 rejected 或 normalized with warning；不得静默写入未知 gate。

### 6.3 Canonical Adapter Mapping

`deck_master_quality_findings.v1` 是外部输入格式。Deck Master import 后必须归一化为现有 external review / quality report 链路：

| Input field | Canonical target |
|---|---|
| `schema_version=deck_master_quality_findings.v1` | adapter input only |
| `source.skill` | canonical `reviewer` |
| `stage` | canonical `scope` fallback / report metadata |
| `gate_class=external_semantic_alignment` | `scope=semantic`, `gate=external_semantic` |
| `gate_class=external_visual_readiness` | `scope=visual`, `gate=external_visual` |
| `gate_class=external_evidence_coverage` | `scope=evidence`, `gate=external_evidence` |
| `gate_class=external_client_readiness` | `scope=client-readiness`, `gate=external_client_readiness` |
| `severity=blocking` | `severity=P1` by default; may upgrade to `P0` only when adapter rule says delivery cannot be repaired in-page |
| `severity=warning` | `severity=P2` |
| `title` | canonical finding `message` |
| `repair_instruction` | canonical finding `repair_instruction` |
| `beat_id` / `page_number` | canonical finding refs / metadata |

Rules:

- Canonical output must be `deck_quality_report.v1` under `quality_reports/external_*_gate.json` or the existing external review writer's equivalent output.
- `summary.delivery_ready` must not be trusted as ground truth; Deck Master recomputes `blocks_delivery` from canonical severities.
- Unsupported `gate_class` must be rejected unless explicit normalized-with-warning mapping is implemented and tested.
- Import must write `imports/import_log.jsonl` with `import_type=quality_findings`.

### 6.4 CLI

```bash
deck-master import-quality-findings --run-id <run_id> --input <findings.json>
```

要求：

- Deck Master 继续拥有最终 gate decision。
- PPT Quality Gate 只返回 findings / repair instructions。
- blocking findings 必须进入 run state 和 Review Cockpit 数据源。
- Existing `import-quality-review` must remain available and continue to accept `deck_external_quality_review.v1`.

## 7. PPT Deck Pro Max Generation Handoff

### 7.1 State Machine

Deck Master 当前已有 generation session 状态机，v0.9.12b 必须优先扩展或映射现有状态，不得替换。当前兼容状态包括：

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

Companion handoff 概念状态映射：

| Companion concept | Existing generation session status |
|---|---|
| `created` | `created` |
| `claimed_by_companion` | `dispatched` |
| `working` | `running` |
| `result_submitted` | `completed` or `partial` |
| `imported` | `results_imported` |
| `rejected` | `failed` |
| `expired` | `failed` with timeout reason |
| `cancelled` | `failed` with cancelled reason |

如需新增状态，必须同时更新 resolver、next-step、generation-session status、run-state tests 和 Review Cockpit 展示。

### 7.2 Handoff Request Contract

新增：

```text
docs/contracts/generation-handoff.v1.schema.json
```

建议 request：

```json
{
  "schema_version": "deck_master_generation_handoff.v1",
  "run_id": "customer-run",
  "session_id": "gen_sess_001",
  "beat_id": "beat_03_solution_map",
  "page_task_id": "page_03",
  "route": "ppt-deck-pro-max",
  "mode": "adapt",
  "inputs": {
    "brief_path": "/absolute/run/deck_brief.json",
    "page_task_path": "/absolute/run/page_tasks/page_03.json",
    "library_candidate_path": "/absolute/run/external/ppt_library/candidate_cand_001.json"
  },
  "expected_outputs": [
    "page_copy",
    "visual_spec",
    "render_task",
    "qa_notes"
  ]
}
```

### 7.3 Handoff Result Contract

新增：

```text
docs/contracts/generation-result.v1.schema.json
```

建议 result：

```json
{
  "schema_version": "ppt_deck_pro_max_generation_result.v1",
  "run_id": "customer-run",
  "session_id": "gen_sess_001",
  "beat_id": "beat_03_solution_map",
  "page_task_id": "page_03",
  "status": "result_submitted",
  "outputs": {
    "artifact_path": "generation_artifacts/page_03/page.html",
    "preview_path": "generation_artifacts/page_03/preview.png",
    "page_copy_path": "/absolute/path/page_copy.md",
    "visual_spec_path": "/absolute/path/visual_spec.json",
    "render_task_path": "/absolute/path/render_task.json",
    "qa_notes_path": "/absolute/path/qa_notes.md"
  },
  "warnings": []
}
```

Rules:

- `artifact_path` and `preview_path` for Deck Master canonical import must be run-relative paths inside the run directory.
- Absolute companion paths such as `page_copy_path`、`visual_spec_path`、`render_task_path`、`qa_notes_path` are external evidence refs; they must be copied, normalized, or referenced according to adapter policy before they affect run state.
- If the companion cannot provide a run-relative `artifact_path` and required `preview_path`, import must be rejected or recorded as `failed`; it must not create a fake completed result.

### 7.4 Canonical Adapter Mapping

`ppt_deck_pro_max_generation_result.v1` is adapter input. Deck Master canonical import remains `deck_generation_result.v1`.

Adapter output shape:

```json
{
  "schema_version": "deck_generation_result.v1",
  "run_id": "customer-run",
  "tool": "ppt-deck-pro-max",
  "task_id": "page_03",
  "beat_id": "beat_03_solution_map",
  "page_id": "beat_03_solution_map",
  "status": "completed",
  "artifact_path": "generation_artifacts/page_03/page.html",
  "preview_path": "generation_artifacts/page_03/preview.png",
  "generation_notes": "Imported from ppt_deck_pro_max_generation_result.v1",
  "metadata": {
    "session_id": "gen_sess_001",
    "page_task_id": "page_03",
    "adapter_input_schema": "ppt_deck_pro_max_generation_result.v1",
    "external_output_refs": {
      "page_copy_path": "/absolute/path/page_copy.md",
      "visual_spec_path": "/absolute/path/visual_spec.json",
      "render_task_path": "/absolute/path/render_task.json",
      "qa_notes_path": "/absolute/path/qa_notes.md"
    }
  }
}
```

Mapping:

| Companion input | Canonical target |
|---|---|
| `run_id` | `run_id`; must match target run |
| `session_id` | validate against current generation session; store in metadata |
| `beat_id` | `beat_id` and fallback `page_id` |
| `page_task_id` | `task_id` and metadata |
| `status=result_submitted` | `completed` when required canonical artifacts exist; `partial` only when adapter rules and canonical validator allow required paths; `failed` for rejected/invalid companion output |
| `outputs.artifact_path` | canonical `artifact_path`, run-relative |
| `outputs.preview_path` | canonical `preview_path`, run-relative |
| `outputs.*_path` absolute refs | metadata or copied run artifacts; never direct canonical completion evidence |

State flow decision for v0.9.12b:

- Preserve the current `generation-session import-results` behavior: it may refresh preview immediately after canonical import.
- If preview refresh succeeds, session may end in `quality_required`.
- If preview refresh does not run or cannot refresh, session remains `results_imported`.
- Tests must assert both accepted terminal states by scenario, and must assert `quality_required` blocks export until a fresh quality gate passes.

### 7.5 CLI

```bash
deck-master prepare-generation-handoff --run-id <run_id>
deck-master generation-session create --run-id <run_id> --tool ppt-deck-pro-max
deck-master generation-session import-results --run-id <run_id> --input <generation-result.json>
deck-master import-generation-result --run-id <run_id> --input <generation-result.json>
```

Compatibility rule:

- `prepare-generation-handoff`、`generation-session create`、`generation-session import-results`、`import-generation-result` 是现有主链路，必须保持可用。
- `create-generation-handoff` 如新增，只能作为 alias 或更细粒度 helper；不得形成第二套 generation handoff 流程。

要求：

- handoff 创建后写 run event。
- result import 通过 adapter 转换为 `deck_generation_result.v1` 后才改变 generation session status。
- import must validate `run_id + session_id` before writing canonical artifacts。
- bad result 不得覆盖现有 page artifact。
- import must write `imports/import_log.jsonl` with `import_type=generation_result`。

## 8. Skill Docs 更新

更新：

- `ppt-library`：增加 standalone vs used by Deck Master。
- `ppt-quality-gate`：增加 standalone audit vs Deck Master import。
- `ppt-deck-pro-max`：增加 standalone production vs Deck Master generation session。
- `deck-master`：增加 companion routing import requirement。

## 9. 测试

必须覆盖：

- missing `ppt-lib` reports blocked library sourcing。
- `ppt-lib doctor` failed reports doctor_failed。
- Library selection import preserves beat/page/slot mapping。
- Multiple same-role beats do not collapse。
- bad selection JSON rejected without overwriting previous results。
- Quality findings import creates Deck Master quality records。
- unsupported gate_class rejected or normalized with warning。
- Generation handoff creates session with correct state。
- Generation result adapter writes canonical `deck_generation_result.v1`。
- Generation result import preserves current status mapping: `results_imported` when preview refresh is unavailable, `quality_required` when preview refresh succeeds。
- `quality_required` blocks export until a fresh quality gate passes。
- Result with mismatched run_id/session_id rejected。
- Result with absolute canonical `artifact_path` or `preview_path` rejected unless copied into run-relative paths first。
- Existing `generation-session create/status/import-results` tests continue to pass。

## 10. 验收标准

- Deck Master 可以在 active run 中调用/导入 PPT Library selection。
- Deck Master 可以导入 PPT Quality Gate structured findings。
- Deck Master 可以创建 PPT Deck Pro Max handoff 并导入 result。
- Companion output 全部先 adapter 归一化，再写现有 canonical artifacts。
- 所有 companion outputs 都通过 import log 记录。
- Standalone companion usage 保持文档可用。
- 不破坏 Stack A 的 setup/status/install guard。
- 不破坏现有 `search-library`、`decide-sourcing`、`generation-session`、`import-generation-result` 命令。

## 11. 给 Codex 的执行提示

```text
你正在开发 MainQuestAI/Deck-Master v0.9.12b：Companion Workflow Contracts。

前提：v0.9.12a 已完成。

目标：实现 PPT Library read-only adapter、PPT Quality Gate structured import、PPT Deck Pro Max generation handoff/import。

禁止：
- 不重写 PPT Library 内部索引。
- 不重写 PPT Deck Pro Max 生产算法。
- 不重写 Deck Master 主质量引擎。
- 不做真实 feedback writeback。
- 不新增第二套 selection reader、quality gate engine 或 generation result state。
- companion output 必须先 adapter 成现有 canonical artifact。

完成后输出：
- 修改文件清单。
- 新增 CLI。
- 新增 JSON schema。
- run artifact 路径。
- 测试命令和结果。
- 已知限制。
```
