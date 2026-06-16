# Deck Master v0.9.12 Skill Suite Runtime Foundation Spec

> Current implementation source: this document is retained as the high-level background spec. After the 2026-06-16 autoplan review, implementation must use the split Stack Spec Pack under `docs/deck-master-v0.9.12-stack-spec-pack/`.
>
> If this file conflicts with the stack specs, the stack specs win, especially on pure-read status checks, companion source matrix, adapter-first imports, import log ownership, feedback CLI identity fields, and Review Cockpit minimum UI acceptance.

## Summary

本轮目标是把 Deck Master 从单一 skill 升级为可安装、可发现、可路由、可回收结果的 Skill Suite Runtime Foundation。

v0.9.12 只解决 companion skills 的安装、状态发现、能力路由、无副作用 readiness check、dry-run handoff 和 import contract。PPT Library 的资产智能、真实反馈写回、PPT Quality Gate 的深度质量治理、PPT Deck Pro Max 的深度生产算法和 PPT Master 的渲染实现留给后续版本。

完成后，用户安装 Deck Master 时，Agent 能看到完整 suite 状态；用户点名 Deck Master 时，Agent 会先执行无副作用 readiness check，再进入 Setup 引导或 run 续作；PPT Library、PPT Deck Pro Max、PPT Quality Gate 和 PPT Master 可以作为 standalone skill 使用，也可以在 active Deck Master run 内通过 Deck Master 契约接入。

## Positioning

v0.9.12 是横切 P2/P3/P4 的基础层：

| v0.9.12 能力 | 后续阶段价值 |
|---|---|
| Skill Suite Routing | 为 Narrative Engine、Asset Intelligence、Quality Governance 提供统一 Agent 入口 |
| Suite install/status | 为所有 companion skills 提供安装和可用性基础 |
| PPT Library read-only adapter | 为 P3 Asset Intelligence 提供可追踪 sourcing 前置 |
| Quality findings import schema | 为 P4 Quality Governance 提供外部审查接入前置 |
| PPT Deck Pro Max handoff/import | 为 P2/P4 的生产与审查链路提供状态机前置 |

本轮重点是基础契约，而非 companion skills 的业务深水区。

## Problems To Solve

当前主要问题集中在 skill 人机交互和 companion runtime 边界：

- Deck Master 只有一个大 skill 入口，无法清晰覆盖“完整方案流程、历史页检索、新 Deck 生产、质量审查、渲染输出”等不同用户任务。
- Setup 已有 CLI 能力，但 skill 层缺少正式的首次引导协议，Agent 可能把底层命令直接交给用户。
- 用户点名 Deck Master 时，Agent 仍可能先调用其他工具，绕过 Deck Master run state。
- PPT Library、PPT Deck Pro Max、PPT Quality Gate 和 PPT Master 目前更像外部工具描述，缺少统一 suite install、capability status 和 import contract。
- Companion readiness 只有 skill-level 判断，缺少 task-level readiness，无法支持“状态查看可继续、历史检索阻断、渲染能力可选”等真实场景。
- PPT Library selection 只保留 `beat_id` 不够，后续页面替换、候选反馈、截图校验、保密边界和资产复利会缺追踪字段。
- 真实反馈写回 PPT Library 涉及 usage semantics、deal lifecycle、幂等和数据污染风险，本轮需要先建立 event queue 和 dry-run。

## Non-Mutation Rule

v0.9.12 必须把无副作用检查作为第一原则。

无副作用命令：

- `setup-status --include-suite --output json`
- `suite-status --output json`
- `library-status --output json`
- `doctor` 的只读诊断部分

强约束：

- `setup-status` 和 `suite-status` 不得创建 run，不得修改 workspace，不得修复 skill 链接。
- setup 未达到 `production_ready=true` 前，`start` 不得创建或修改 production run。
- Companion skill 输出必须通过 Deck Master import 命令进入 run state。
- Import 必须写入 `imports/import_log.jsonl`。
- Bad JSON、schema mismatch、run_id mismatch 不得覆盖已有 artifact。
- 测试不得修改真实用户 workspace。

## Current Assets

### Deck Master

Path:

```text
/Users/dingcheng/Coding-Project/02-key-project/Deck-Master/skills/deck-master
```

Current role:

- 顶层 deck workflow runtime。
- Setup、workspace、production run guard。
- request、planning、sourcing、quality、review、export、benchmark state。
- external tool handoff / handback contract。

Current gap:

- Skill docs 提到 setup 命令，但缺少 Agent-led first-run ceremony。
- Companion skills 尚未纳入 Deck Master 安装和状态模型。
- Skill docs 缺少 task intent routing 和 active run import 规则。

### PPT Library

Installed skill:

```text
/Users/dingcheng/.codex/skills/ppt-library/SKILL.md
```

Repo:

```text
/Users/dingcheng/Coding-Project/02-key-project/PPT-Library
```

Current role:

- PPT source setup、indexing、search、slide selection、compose、profile、enrichment、feedback recording、diagnostics。
- CLI entry: `ppt-lib`。
- Commands include `search`、`select-slides`、`record-deal`、`record-usage`、`doctor`、`sources`、`index`、`status`。

v0.9.12 scope:

- Bundle curated skill docs or adopt valid external skill link。
- Validate external `ppt-lib` CLI and doctor status。
- Provide read-only adapter contract。
- Generate feedback event queue and dry-run writeback plan。

Out of this round:

- Rewriting PPT Library indexing internals。
- Silent broad indexing of Home、Downloads、cache、recycle folders。
- Default real `record-usage` / `record-deal` writeback。

### PPT Deck Pro Max

Installed skill:

```text
/Users/dingcheng/.codex/skills/ppt-deck-pro-max/SKILL.md
```

Current role:

- Product-grade deck production pipeline。
- Covers brief、narrative arc、content governance、expert interview、redaction、visual system、page copy、build、QA、rollback。

v0.9.12 scope:

- Bundle curated skill package or adopt valid external skill link。
- Add Deck Master generation handoff request schema。
- Add dry-run result import schema。
- Track generation session state。

Out of this round:

- Rewriting production algorithm。
- Deep execution of PPT Deck Pro Max pipeline inside Deck Master。

### PPT Quality Gate

Draft skill:

```text
/Users/dingcheng/Workspace/_internal/迈富时PPT工作坊/skill-drafts/ppt-quality-gate
```

Current role:

- Independent audit skill for Draft Gate、Render Gate、Delivery Gate。
- Checks narrative integrity、page job clarity、information density、evidence、screenshot integration、layout variety、consulting expression、visual readiness、delivery readiness。

v0.9.12 scope:

- Promote docs-first skill package。
- Add structured findings schema。
- Add Deck Master import path for structured findings。
- Map findings into existing external quality classes。

Out of this round:

- Rewriting Deck Master quality engine。
- Turning PPT Quality Gate into final gate decision owner。
- Complex visual or aesthetic scoring engine。

### PPT Master

Current role:

- Renderer / build execution layer for SVG、PPTX、HTML、PDF。

v0.9.12 scope:

- Optional external companion。
- Validate import-result contract only。

Out of this round:

- Renderer internals。
- Mandatory renderer dependency for planning, status or audit tasks。

## Product Model

### Skill Suite

Deck Master Suite contains:

| Skill | Install expectation | Task-level blocking | Standalone use | Main user intent |
|---|---|---|---:|---|
| `deck-master` | required | required for Deck Master run | yes | Full solution deck orchestration |
| `ppt-library` | required in suite install | only for library sourcing / asset feedback | yes | Search and reuse historical PPT assets |
| `ppt-deck-pro-max` | required in suite install | only for new generation route | yes | Produce new deck content and visual specs |
| `ppt-quality-gate` | required in suite install | only for audit route | yes | Audit PPT/HTML/PDF or deck draft |
| `ppt-master` | optional | only for selected render route | yes | Render or assemble slide artifacts |

Important distinction:

- `suite_install_ready` means links and manifest are valid enough for Agent routing.
- `task_capability_ready` means the current task can safely use the needed companion capability.
- `full_suite_ready` can be false while Deck Master status/read-only operations still work.

### Responsibility Split

Deck Master:

- Owns the production run.
- Owns setup, workspace, run state, review cockpit and final reporting.
- Decides reuse / adapt / generate / manual_placeholder.
- Calls companion skills through explicit contracts.
- Imports external results before those results affect run state.

PPT Library:

- Owns historical slide library setup, index, search and feedback data.
- Returns candidates and evidence for Deck Master sourcing.
- Receives dry-run feedback events in v0.9.12.

PPT Deck Pro Max:

- Owns new deck production expertise.
- Receives Deck Master generation handoff package.
- Returns page copy, visual spec, render task and QA notes through import contract.

PPT Quality Gate:

- Owns audit reasoning and repair instructions.
- Returns structured findings.
- Deck Master keeps final gate decision.

PPT Master:

- Owns rendering and assembly execution.
- Returns output files and render metadata.

## Routing Rules

### User Intent Routing

| User says | Primary skill | Deck Master role |
|---|---|---|
| "用 Deck Master 做一套客户方案" | `deck-master` | Own full workflow |
| "从这些客户资料出一套方案 Deck" | `deck-master` | Setup, context intake, plan, sourcing, generation, review |
| "检索历史 PPT 里有没有类似页面" | `ppt-library` | Attach to active run if one exists |
| "把这份 brief 做成高质量 PPT" | `ppt-deck-pro-max` | Register generation session if inside Deck Master run |
| "帮我审一下这个 PPT 能不能交付" | `ppt-quality-gate` | Import findings if run exists |
| "帮我把页面渲染成 PPTX / SVG" | `ppt-master` | Import render result if run exists |
| "继续上次 Deck Master run" | `deck-master` | Resolve run state first |

### Deck Master Named First Step

If the user explicitly names Deck Master:

1. Run `deck-master setup-status --include-suite --output json` first.
2. If setup is not `production_ready`, enter first-run setup ceremony and do not create or modify production run.
3. If the user says "continue", resolve active or last run first; create a new run only when the user asks for a new run.
4. If setup is `production_ready` and no active run applies, then call `deck-master start` or create the requested run.
5. If a companion skill is used inside an active Deck Master run, import its result through Deck Master before reporting completion.

This replaces any routing rule that starts with `deck-master start`.

## First-Run Setup Ceremony

The user experience is Agent-led:

1. Agent loads Deck Master skill.
2. Agent runs `setup-status --include-suite --output json`.
3. If `active_workspace` is missing, Agent asks the user which folder should be the active Deck workspace.
4. Agent runs setup with the confirmed workspace.
5. Agent validates companion skills and capability readiness.
6. Agent checks Review Cockpit health.
7. Agent reports a short readiness summary and next action.

Agent rule:

- Do not make a bare setup command the primary answer when the Agent can perform setup after user confirmation.
- Do not ask for unrelated companion setup when the current user task does not need that capability.

## Readiness Model

### Setup Status With Suite

Example:

```json
{
  "schema_version": "deck_master_setup_status.v2",
  "status": "degraded_ready",
  "install_ready": true,
  "workspace_ready": true,
  "production_ready": true,
  "suite_install_ready": true,
  "full_suite_ready": false,
  "capabilities": {
    "deck_master.run.v1": "ready",
    "ppt_library.search.v1": "blocked_cli_missing",
    "ppt_library.selection.v1": "blocked_cli_missing",
    "ppt_library.feedback_event.v1": "ready",
    "ppt_deck_pro_max.generation_handoff.v1": "ready",
    "ppt_quality_gate.audit_import.v1": "missing",
    "ppt_master.render_import.v1": "optional_missing"
  },
  "task_readiness": {
    "full_deck_workflow": "degraded_ready",
    "library_sourcing": "blocked",
    "new_generation": "ready",
    "standalone_audit": "blocked",
    "render_export": "optional_missing"
  },
  "next_agent_action": "Proceed with Deck Master run if library/audit/render capabilities are not required; guide suite repair when the task needs a blocked capability."
}
```

### Capability Status Enum

Allowed statuses:

```text
ready
missing
optional_missing
wrong_symlink
real_dir_conflict
external_adoptable
external_version_mismatch
cli_missing
doctor_failed
schema_incompatible
capability_missing
permission_denied
unsafe_source_config
blocked_cli_missing
blocked_schema_invalid
degraded_ready
```

## Installation Model

### Install Tree

Recommended installed tree:

```text
~/.deck-master/
  current -> releases/main-<sha>
  releases/main-<sha>/
    skills/
      deck-master/
      ppt-library/
      ppt-deck-pro-max/
      ppt-quality-gate/
      ppt-master/              # optional
    companion-manifest.json
    docs/
      contracts/
    scripts/
  bin/
    deck-master
```

Agent skill dirs contain only soft links:

```text
~/.codex/skills/deck-master -> ~/.deck-master/current/skills/deck-master
~/.codex/skills/ppt-library -> ~/.deck-master/current/skills/ppt-library
~/.codex/skills/ppt-deck-pro-max -> ~/.deck-master/current/skills/ppt-deck-pro-max
~/.codex/skills/ppt-quality-gate -> ~/.deck-master/current/skills/ppt-quality-gate
~/.claude/skills/<skill-name> -> ~/.deck-master/current/skills/<skill-name>
```

No development repo path can be used as the installed skill source.

### Companion Manifest v2

Add:

```text
~/.deck-master/current/companion-manifest.json
```

Example:

```json
{
  "schema_version": "deck_master_companion_manifest.v2",
  "suite_name": "deck-master",
  "suite_version": "0.9.12",
  "skills": [
    {
      "name": "ppt-library",
      "required_for": ["library_sourcing", "asset_feedback_event"],
      "install_source": "external_cli_with_bundled_skill_docs",
      "min_cli_version": "0.1.0",
      "cli": "ppt-lib",
      "required_capabilities": [
        "ppt_library.doctor.v1",
        "ppt_library.search.v1",
        "ppt_library.selection.v1"
      ],
      "optional_capabilities": [
        "ppt_library.feedback_writeback.v1"
      ],
      "schema_versions": {
        "query_input": "deck_master_ppt_library_query.v1",
        "selection_output": "deck_master_ppt_library_selection.v1",
        "feedback_event": "deck_master_ppt_library_feedback_event.v1"
      },
      "agent_targets": {
        "codex": "~/.codex/skills/ppt-library",
        "claude-code": "~/.claude/skills/ppt-library"
      },
      "adoption_policy": "adopt_valid_external_symlink_only",
      "conflict_policy": "never_overwrite_real_directory"
    }
  ]
}
```

### Adoption And Repair Rules

- Adopt valid external symlink only when it points to an approved companion source.
- Never overwrite a real directory in Agent skill dirs.
- `suite-repair` may replace a wrong symlink only with explicit `--force` or a non-interactive repair policy intended for tests.
- Real directory conflict returns `real_dir_conflict` with the path and manual repair instruction.
- External CLI version mismatch returns `external_version_mismatch`.
- Permission errors return `permission_denied`.

## Contract Freeze

Add contracts:

```text
docs/contracts/companion-manifest.v2.schema.json
docs/contracts/setup-status.v2.schema.json
docs/contracts/ppt-library-query.v1.schema.json
docs/contracts/ppt-library-selection.v1.schema.json
docs/contracts/ppt-library-feedback-event.v1.schema.json
docs/contracts/quality-findings.v1.schema.json
docs/contracts/generation-handoff.v1.schema.json
docs/contracts/generation-result.v1.schema.json
```

Contract invariants:

- All contracts include `schema_version`.
- Run-bound imports require matching `run_id`.
- Page-bound imports preserve `beat_id` and `page_task_id` when available.
- Artifacts that reference files use absolute paths.
- Imports write an audit record before changing derived state.
- Invalid import writes failure details to import log and leaves previous artifacts intact.

## PPT Library Foundation

### Readiness

Deck Master validates:

- `ppt-library` skill soft link.
- `ppt-lib` CLI availability.
- `ppt-lib doctor --output json`.
- Config path and database path readability.
- Search index existence or explicit setup gap.
- Source governance warnings for broad Home, Downloads, cache, recycle or dependency folders.
- Screenshot path absolute readiness when available.

Deck Master must not silently index broad or risky directories.

### Query Contract

Input:

```json
{
  "schema_version": "deck_master_ppt_library_query.v1",
  "run_id": "customer-run",
  "workspace": "/absolute/workspace",
  "request_id": "req_001",
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

Output:

```json
{
  "schema_version": "deck_master_ppt_library_selection.v1",
  "run_id": "customer-run",
  "request_id": "req_001",
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

Deck Master stores:

```text
runs/<run_id>/external/ppt_library/library_results.json
runs/<run_id>/imports/import_log.jsonl
```

Required preserved fields:

```text
run_id
request_id
beat_id
page_task_id
slot_id
candidate_id
canonical_slide_id
source_deck_id
screenshot_sha256
source_profile
query_trace_id
```

### Feedback Event Queue

v0.9.12 does not default to real PPT Library writeback.

Deck Master writes:

```text
runs/<run_id>/external/ppt_library/library_feedback_events.jsonl
```

Event schema:

```json
{
  "schema_version": "deck_master_ppt_library_feedback_event.v1",
  "run_id": "customer-run",
  "event_id": "lib_feedback_001",
  "candidate_id": "cand_001",
  "canonical_slide_id": "canonical_xxx",
  "page_task_id": "page_03",
  "beat_id": "beat_03_solution_map",
  "decision": "approved_for_adapt",
  "deal_outcome": "unknown",
  "dry_run_writeback_command": "ppt-lib record-usage ...",
  "created_at": "2026-06-16T00:00:00Z"
}
```

Real `record-usage` and `record-deal` writeback is a follow-up.

## PPT Quality Gate Foundation

### Scope

v0.9.12 promotes PPT Quality Gate as docs-first companion skill and structured findings producer.

Required output:

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
      "page_task_id": "page_03",
      "title": "Solution architecture claim needs stronger evidence.",
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

Quality finding classes should map into existing Deck Master external quality classes:

```text
external_semantic_alignment
external_visual_readiness
external_evidence_coverage
external_client_readiness
```

Deck Master keeps final gate decision.

## PPT Deck Pro Max Foundation

### Generation Session State Machine

Allowed states:

```text
created
claimed_by_companion
working
result_submitted
imported
rejected
expired
cancelled
```

### Handoff Request

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

### Handoff Result

```json
{
  "schema_version": "ppt_deck_pro_max_generation_result.v1",
  "run_id": "customer-run",
  "session_id": "gen_sess_001",
  "beat_id": "beat_03_solution_map",
  "page_task_id": "page_03",
  "status": "result_submitted",
  "outputs": {
    "page_copy_path": "/absolute/path/page_copy.md",
    "visual_spec_path": "/absolute/path/visual_spec.json",
    "render_task_path": "/absolute/path/render_task.json",
    "qa_notes_path": "/absolute/path/qa_notes.md"
  },
  "warnings": []
}
```

v0.9.12 only requires dry-run handoff generation and import validation.

## Proposed Public Interfaces

### New Or Updated CLI

```bash
deck-master setup-status --include-suite --output json
deck-master suite-status [--target codex] [--target claude-code] [--output json]
deck-master suite-install [--target codex] [--target claude-code] [--include-optional]
deck-master suite-repair [--target codex] [--target claude-code]
deck-master install-skill --suite --target codex --target claude-code
deck-master library-status [--workspace <path>] [--output json]
deck-master library-search --run-id <run_id> --beat-id <beat_id> --query <text> --dry-run
deck-master import-library-selection --run-id <run_id> --input <selection.json>
deck-master record-library-feedback --run-id <run_id> --dry-run
deck-master import-quality-findings --run-id <run_id> --input <findings.json>
deck-master generation-session handoff --run-id <run_id> --page-task-id <id> --route ppt-deck-pro-max --dry-run
deck-master generation-session import-result --run-id <run_id> --input <result.json>
```

## Skill Docs Updates

Deck Master skill:

- Add `First-Run Setup Protocol`.
- Add `Skill Suite Runtime Routing`.
- Add `Companion Capability Matrix`.
- Add `PPT Library Foundation`.
- Add rule: setup-status with suite first, then setup ceremony, then run mutation.
- Add rule: companion output affects run state only after import.

PPT Library skill:

- Add standalone vs Deck Master usage section.
- Add Deck Master query and selection contract.
- Add preserved field list.

PPT Quality Gate skill:

- Promote from draft into release skill tree.
- Keep independent skill name `ppt-quality-gate`.
- Add structured findings schema and Deck Master import notes.

PPT Deck Pro Max skill:

- Add standalone vs Deck Master generation session section.
- Add handoff request/result shape.

## Implementation Plan

### Phase 0: Contract Freeze And Non-Mutation Guard

Deliver:

```text
docs/specs/deck-master-v0.9.12-skill-suite-routing-spec.md
docs/contracts/companion-manifest.v2.schema.json
docs/contracts/setup-status.v2.schema.json
docs/contracts/ppt-library-query.v1.schema.json
docs/contracts/ppt-library-selection.v1.schema.json
docs/contracts/ppt-library-feedback-event.v1.schema.json
docs/contracts/quality-findings.v1.schema.json
docs/contracts/generation-handoff.v1.schema.json
docs/contracts/generation-result.v1.schema.json
```

Tests:

- `setup-status --include-suite` is non-mutating.
- `suite-status` is non-mutating.
- setup not production-ready prevents production run mutation.
- Invalid imports preserve previous artifacts.

### Phase 1: Suite Status And Install Foundation

- Add companion manifest loader and validator.
- Add `suite-status`.
- Add `suite-install`.
- Add `suite-repair`.
- Extend `install-skill --suite`.
- Support Codex and Claude Code soft links.
- Report task-level capability readiness.

Tests:

- Idempotent suite install.
- Wrong symlink.
- Real directory conflict.
- External adoptable symlink.
- External version mismatch.
- Permission denied.
- Missing CLI.
- Doctor failed.
- Healthy suite.

### Phase 2: First-Run Skill Guidance

- Update `skills/deck-master/SKILL.md`.
- Update `skills/deck-master/references/agent-instructions.md`.
- Add setup-first ceremony to production playbook.
- Ensure install output includes `suite_status`, `setup_status`, `next_agent_action`.

Tests:

- Skill docs contain required routing sections.
- Install output includes next Agent action.
- User-facing command examples start with non-mutating status.

### Phase 3: PPT Library Read-Only Adapter

- Add `library-status`.
- Add `library-search --dry-run`.
- Add `import-library-selection`.
- Store `external/ppt_library/library_results.json`.
- Store `external/ppt_library/library_feedback_events.jsonl`.
- Add `record-library-feedback --dry-run`.

Tests:

- Missing `ppt-lib` blocks library sourcing only.
- Multiple same-role beats preserve mapping.
- `beat_id`, `page_task_id`, `candidate_id`, `query_trace_id` survive import.
- Bad JSON import leaves old results intact.
- Feedback dry-run writes event queue only.

### Phase 4: PPT Quality Gate Promotion Light

- Promote docs-first skill package.
- Add `quality-findings.v1` schema.
- Add `import-quality-findings`.
- Map findings to existing external gate classes.

Tests:

- Skill package passes format checks.
- Structured findings import writes import log.
- Run-id mismatch is rejected.
- Existing quality engine remains owner of final status.

### Phase 5: PPT Deck Pro Max Dry-Run Route

- Add generation handoff schema.
- Add result schema.
- Add generation session state transitions for dry-run route.
- Import result into Deck Master run state.

Tests:

- Dry-run handoff creates expected request.
- Result import requires matching `run_id` and `session_id`.
- Rejected import preserves prior state.
- Session status moves through expected state sequence.

### Phase 6: QA And Release

- Full unit tests.
- Temporary HOME suite smoke.
- Local reinstall smoke.
- Review Cockpit setup banner check.
- Real-machine suite status check without modifying user workspace.

## Acceptance Criteria

Product acceptance:

- User installing Deck Master gets a clear suite status and task-level capability status.
- User naming Deck Master is routed through non-mutating readiness check before production mutation.
- User can still use PPT Library, PPT Deck Pro Max or PPT Quality Gate directly.
- Active Deck Master run only accepts companion output through import.
- PPT Library selection preserves enough IDs for later page replacement, evidence and feedback.
- PPT Quality Gate can produce structured findings that Deck Master imports.
- PPT Deck Pro Max can receive dry-run handoff and return importable result.

Engineering acceptance:

- `setup-status --include-suite` reports install/workspace/production/suite/capability status.
- `suite-status` is non-mutating.
- `suite-install` is idempotent.
- Codex and Claude skill links point into `~/.deck-master/current/skills`.
- No development repo path is used as installed skill source.
- Full suite missing does not block read-only Deck Master status.
- Task-required missing capability blocks only that task route.
- All v0.9.11 production guards remain active.
- Tests cover wrong symlink, real dir conflict, missing CLI, doctor failed, external adoption and healthy suite.

## Packaging Decisions

Recommended v0.9.12 packaging:

| Companion | Packaging | Reason |
|---|---|---|
| `ppt-library` | Bundle curated skill docs; call external `ppt-lib` CLI | It has its own repo, package and database lifecycle |
| `ppt-deck-pro-max` | Bundle curated skill package; keep source repo independent | It is primarily an Agent-facing production skill |
| `ppt-quality-gate` | Bundle docs-first promoted skill package | Draft is close to skill shape; scripts must exist or references must be removed |
| `ppt-master` | Optional external | Renderer choice can vary by user and project |

## Out Of Scope

- Rewriting PPT Library indexing internals.
- Silent broad source indexing.
- Real PPT Library feedback writeback by default.
- Deep PPT Deck Pro Max production execution.
- Rewriting Deck Master quality gate engine.
- Deep PPT Master renderer integration.
- Remote package manager.
- Built-in LLM provider calls.
- Multi-user hosted Deck Master deployment.

## Review Checklist

- Does the foundation scope look small enough for a single PR?
- Are `setup-status` and `suite-status` clearly non-mutating?
- Is task-level capability readiness sufficient for real routing?
- Should PPT Library feedback stay dry-run until v0.9.13?
- Are the preserved PPT Library fields enough for Asset Intelligence?
- Are Quality Gate findings mapped to the correct external gate classes?
- Is PPT Deck Pro Max dry-run handoff enough for v0.9.12?
- Are companion packaging decisions acceptable?
