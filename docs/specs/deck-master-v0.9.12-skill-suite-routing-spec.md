# Deck Master v0.9.12 Skill Suite Routing Spec

## Summary

本轮目标是把 Deck Master 从单一 skill 升级为一组可独立使用、也可被 Deck Master 统一编排的 Skill Suite。

Deck Master 继续作为顶层编排器，负责 Setup、workspace、run state、页面来源决策、Review Cockpit、质量门禁、外部工具 handoff/handback 和最终交付闭环。PPT Library、PPT Deck Pro Max、PPT Quality Gate、PPT Master 作为 companion skills，分别承担资料检索、Deck 生产、质量审查和渲染执行。

完成后，用户安装 Deck Master 时，应自动安装或校验整套 companion skills，并在 skill 层给出清晰的人机交互入口。用户也可以单独安装 PPT Library、PPT Deck Pro Max 或 PPT Quality Gate，用于独立场景。

## Background

v0.9.9 到 v0.9.11 已经把安装根目录、软链接结构、first-run setup、production guard、workspace-bound run、run-state resolver 和 Review Cockpit guard 基本打通。

当前主要问题已经转到 skill 人机交互层：

- Deck Master 只有一个大 skill 入口，无法清晰覆盖不同用户任务。
- Setup 已有 CLI 能力，但 skill 层缺少正式的首次引导协议。
- PPT Library、PPT Deck Pro Max、PPT Quality Gate 和 PPT Master 的关系停留在外部工具描述，缺少 suite install 与场景路由。
- 用户点名 Deck Master 时，Agent 仍可能直接使用其他生成或设计工具，绕过 Deck Master run。
- 用户只想审查已有 PPT 时，完整 Deck Master 流程过重；PPT Quality Gate 需要独立 skill 入口。
- 用户只想检索历史页时，PPT Library 需要独立入口；当 Deck Master 工作流需要历史页时，它也要被 Deck Master 统一调用和登记。

## Current Assets

### Deck Master

Path:

```text
/Users/dingcheng/Coding-Project/02-key-project/Deck-Master/skills/deck-master
```

Current role:

- Top-level deck workflow runtime.
- Setup and production run guard.
- Workspace, request, planning, sourcing, quality, review, export and benchmark state.
- External tool handoff and handback contracts.

Current gap:

- Skill docs mention setup commands, but do not define an Agent-led first-run ceremony.
- Companion skills are not managed as part of Deck Master installation.
- Skill docs do not provide a strong routing table for common user intents.

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

- PPT source setup, indexing, search, slide selection, compose, profile, enrichment, feedback recording and diagnostics.
- CLI entry is `ppt-lib`.
- Provides `search`, `select-slides`, `record-deal`, `record-usage`, `doctor`, `sources`, `index`, `status` and related commands.

Current gap:

- Deck Master sees PPT Library as a tool, but does not install or validate the PPT Library skill as a companion.
- Deck Master needs stable readiness checks for PPT Library config, index health, search health and source governance.
- Deck Master sourcing needs a stable page-level contract that preserves Deck Master `beat_id`.
- Approval and delivery feedback from Deck Master should write back to PPT Library usage and deal records.

### PPT Deck Pro Max

Installed skill:

```text
/Users/dingcheng/.codex/skills/ppt-deck-pro-max/SKILL.md
```

Current role:

- Product-grade deck production pipeline.
- Covers brief, narrative arc, content governance, expert interview, redaction, visual system, page copy, build, QA and rollback.

Current gap:

- It is currently installed as an independent Codex skill directory.
- Deck Master install should be able to place it under Deck Master suite install root and expose it through agent soft links.
- Deck Master generation sessions need a stronger route into PPT Deck Pro Max when a page or section is marked `generate` or `adapt`.

### PPT Quality Gate

Draft skill:

```text
/Users/dingcheng/Workspace/_internal/迈富时PPT工作坊/skill-drafts/ppt-quality-gate
```

Current role:

- Independent audit skill for Draft Gate, Render Gate and Delivery Gate.
- Checks narrative integrity, page job clarity, information density, evidence, screenshot integration, layout variety, consulting expression, visual readiness and delivery readiness.

Current gap:

- It is still a draft skill and is not part of the Deck Master install tree.
- Deck Master quality gates and this skill have overlapping concepts but no clear routing.
- It needs a formal output contract so Deck Master can import findings into run state.

### PPT Master

Current role:

- Renderer / build execution layer for SVG, PPTX, HTML, PDF or related artifacts.

Current gap:

- It should remain callable as an execution companion.
- Deck Master needs to validate output through import-result and quality gates before final reporting.

## Product Model

### Skill Suite

Deck Master Suite contains:

| Skill | Required by Deck Master install | Can be used independently | Main user intent |
|---|---:|---:|---|
| `deck-master` | yes | yes | Full solution deck workflow orchestration |
| `ppt-library` | yes | yes | Search, reuse and govern historical PPT assets |
| `ppt-deck-pro-max` | yes | yes | Produce new product-grade deck content and visuals |
| `ppt-quality-gate` | yes | yes | Audit existing PPT/HTML/PDF or Deck drafts |
| `ppt-master` | optional | yes | Render or assemble slide artifacts |

Deck Master install should install or validate the required companion skills by default. Optional companion skills can be reported as `optional_missing`, with a clear user-facing next action.

### Responsibility Split

Deck Master:

- Owns the production run.
- Decides whether a page should reuse, adapt, generate or remain manual.
- Calls PPT Library for candidate pages.
- Calls PPT Deck Pro Max for new content or page production.
- Calls PPT Quality Gate for audit findings.
- Calls PPT Master or other renderers for build output.
- Imports every external result before reporting completion.

PPT Library:

- Owns historical slide library setup, index, search and feedback data.
- Returns candidates and evidence for Deck Master sourcing decisions.
- Receives usage and win/loss feedback from Deck Master.

PPT Deck Pro Max:

- Owns new deck production pipeline.
- Produces page copy, visual system, generation tasks or full deck production artifacts.
- Can run inside Deck Master generation sessions or standalone.

PPT Quality Gate:

- Owns audit reasoning and repair instructions.
- Can audit standalone artifacts.
- Can return structured findings to Deck Master.

PPT Master:

- Owns rendering and assembly execution.
- Returns output files and render metadata to Deck Master.

## User Intent Routing

Deck Master skill should include a routing table like this:

| User says | Primary skill | Deck Master role |
|---|---|---|
| "用 Deck Master 做一套客户方案" | `deck-master` | Own full workflow |
| "从这些客户资料出一套方案 Deck" | `deck-master` | Setup, context intake, plan, sourcing, generation, review |
| "检索历史 PPT 里有没有类似页面" | `ppt-library` | Optional run attachment if inside active Deck run |
| "把这份 brief 做成高质量 PPT" | `ppt-deck-pro-max` | If user asked Deck Master, register generation session |
| "帮我审一下这个 PPT 能不能交付" | `ppt-quality-gate` | If run exists, import findings |
| "帮我把页面渲染成 PPTX / SVG" | `ppt-master` | If run exists, import render result |
| "继续上次 Deck Master run" | `deck-master` | Run-state first, then route |

Routing rule:

- If the user explicitly names Deck Master, start with `deck-master start` and `setup-status`.
- If setup is not production ready, Agent must guide first-run setup before changing a production run.
- If the task is a subtask inside an active Deck Master run, use companion skill output only through Deck Master import commands.
- If the user directly names a companion skill and no Deck Master run is active, the companion skill can run standalone.

## First-Run Setup Experience

The user experience should be Agent-led:

1. Agent loads Deck Master skill.
2. Agent runs installed setup status.
3. If `active_workspace` is missing, Agent asks the user which folder should be the active Deck workspace.
4. Agent runs setup with the confirmed workspace.
5. Agent validates companion skills.
6. Agent checks Review Cockpit health.
7. Agent reports a short readiness summary and the next action.

The user should not receive a bare CLI command as the primary answer when the skill can execute it.

### Setup Readiness Shape

Deck Master should report:

```json
{
  "status": "needs_workspace",
  "install_ready": true,
  "workspace_ready": false,
  "production_ready": false,
  "suite_ready": false,
  "companion_skills": {
    "deck-master": "ready",
    "ppt-library": "missing",
    "ppt-deck-pro-max": "ready",
    "ppt-quality-gate": "missing",
    "ppt-master": "optional_missing"
  },
  "next_agent_action": "Ask the user to confirm active workspace, then run Deck Master setup and suite install."
}
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
    scripts/
    docs/
  bin/
    deck-master
```

Agent skill dirs should contain only soft links:

```text
~/.codex/skills/deck-master -> ~/.deck-master/current/skills/deck-master
~/.codex/skills/ppt-library -> ~/.deck-master/current/skills/ppt-library
~/.codex/skills/ppt-deck-pro-max -> ~/.deck-master/current/skills/ppt-deck-pro-max
~/.codex/skills/ppt-quality-gate -> ~/.deck-master/current/skills/ppt-quality-gate
```

The same model applies to Claude Code:

```text
~/.claude/skills/<skill-name> -> ~/.deck-master/current/skills/<skill-name>
```

### Companion Manifest

Add:

```text
~/.deck-master/current/companion-manifest.json
```

Example:

```json
{
  "schema_version": "deck_master_companion_manifest.v1",
  "suite_name": "deck-master",
  "skills": [
    {
      "name": "deck-master",
      "required": true,
      "install_source": "bundled",
      "agent_targets": ["codex", "claude-code"]
    },
    {
      "name": "ppt-library",
      "required": true,
      "install_source": "bundled_or_external",
      "agent_targets": ["codex", "claude-code"],
      "cli": "ppt-lib"
    },
    {
      "name": "ppt-deck-pro-max",
      "required": true,
      "install_source": "bundled_or_external",
      "agent_targets": ["codex", "claude-code"]
    },
    {
      "name": "ppt-quality-gate",
      "required": true,
      "install_source": "bundled",
      "agent_targets": ["codex", "claude-code"]
    },
    {
      "name": "ppt-master",
      "required": false,
      "install_source": "external",
      "agent_targets": ["codex", "claude-code"]
    }
  ]
}
```

## PPT Library Coverage

Deck Master should cover PPT Library at four levels.

### 1. Install And Skill Readiness

Deck Master setup should validate:

- `ppt-library` skill is installed as a soft link.
- `ppt-lib` CLI is available.
- `ppt-lib doctor --output json` can run.
- PPT Library config path and database path are readable.
- Search index has at least one valid source or reports a clear setup gap.

### 2. Source Governance

Deck Master should surface PPT Library source readiness:

- Whether a formal library source exists.
- Whether high-risk directories are excluded.
- Whether `/Users/dingcheng/Workspace/_resources/方案库` or the user-selected library path is covered.
- Whether screenshots are available and absolute.
- Whether profile readiness is sufficient for AI summary features.

Deck Master should not silently index broad Home, Downloads, cache or recycle folders.

### 3. Sourcing Contract

Deck Master should call PPT Library through a stable contract:

Input:

```json
{
  "run_id": "customer-run",
  "workspace": "/absolute/workspace",
  "beats": [
    {
      "beat_id": "beat_03_solution_map",
      "role": "solution_overview",
      "brief": "Need a page showing the target solution architecture.",
      "industry": "pharma"
    }
  ],
  "top_k": 5
}
```

Output must preserve `beat_id`:

```json
{
  "schema_version": "deck_master_ppt_library_selection.v1",
  "run_id": "customer-run",
  "results": [
    {
      "beat_id": "beat_03_solution_map",
      "candidates": [
        {
          "slide_id": "slide_abc",
          "source_file": "/absolute/path/to/source.pptx",
          "page_number": 12,
          "screenshot_path": "/absolute/path/to/screenshot.png",
          "confidence": 0.82,
          "win_rate": 0.4,
          "title": "Solution architecture overview",
          "reuse_mode_recommendation": "adapt"
        }
      ]
    }
  ]
}
```

Deck Master should store this as `library_results.json` and convert it into `sourcing_plan.json`.

### 4. Feedback Writeback

Deck Master should write back:

- Page approved for reuse.
- Page adapted and delivered.
- Page rejected.
- Final deal outcome when known.

Suggested mapping:

| Deck Master event | PPT Library writeback |
|---|---|
| page source approved | `record-usage` |
| page source rejected | `record-usage` with negative outcome when supported |
| deck delivered | `record-deal` pending or delivered |
| deal won/lost | `record-deal` final outcome |

## Proposed Public Interfaces

### New Or Updated CLI

```bash
deck-master suite-status [--target codex] [--target claude-code] [--output json]
deck-master suite-install [--target codex] [--target claude-code] [--include-optional]
deck-master suite-repair [--target codex] [--target claude-code]
deck-master setup-status --include-suite
deck-master install-skill --suite --target codex --target claude-code
deck-master library-status [--workspace <path>] [--output json]
deck-master library-search --run-id <run_id> --beat-id <beat_id> --query <text>
deck-master import-library-selection --run-id <run_id> --input <selection.json>
deck-master record-library-feedback --run-id <run_id> [--outcome <value>]
```

### Updated Skill Docs

Update Deck Master skill:

- Add `First-Run Setup Protocol`.
- Add `Skill Suite Routing`.
- Add `Companion Skill Matrix`.
- Add `PPT Library Coverage`.
- Add rule: do not output bare setup commands when Agent can perform the setup after user confirms workspace.

Update PPT Library skill:

- Add "Used standalone vs used by Deck Master" section.
- Add JSON contract requirement for Deck Master selection.
- Add `beat_id` preservation rule.

Promote PPT Quality Gate draft:

- Move into Deck Master release skill tree.
- Keep independent skill name `ppt-quality-gate`.
- Add structured finding output compatible with Deck Master import.

Update PPT Deck Pro Max skill:

- Add "Used standalone vs used by Deck Master generation session" section.
- Add handoff result format expected by Deck Master.

## Implementation Plan

### Phase 1: Spec And Skill Inventory

- Add this spec.
- Add companion skill inventory document if needed.
- Decide whether `ppt-master` is bundled or optional external.
- Decide whether PPT Library source code is vendored into Deck Master release or referenced from installed external package.

Deliverable:

- Approved v0.9.12 spec.

### Phase 2: Suite Install Foundation

- Add companion manifest schema.
- Add `suite-status`.
- Add `suite-install`.
- Extend `install-skill` to support suite install.
- Ensure Codex and Claude skill dirs use only soft links.
- Preserve independent install for each companion skill.

Tests:

- Suite install creates required links.
- Re-running suite install is idempotent.
- Existing valid external companion skill can be adopted or reported clearly.
- Real directories are not overwritten.

### Phase 3: First-Run Skill Guidance

- Update `skills/deck-master/SKILL.md`.
- Update `references/agent-instructions.md`.
- Add first-run setup ceremony to playbook.
- Change install output to include setup and suite next agent action.

Tests:

- Skill docs contain required routing sections.
- Install output includes `suite_status`, `setup_status`, `next_agent_action`.

### Phase 4: PPT Library Coverage

- Add `library-status`.
- Add PPT Library adapter readiness checks.
- Preserve `beat_id` in Deck Master library result imports.
- Store `library_results.json`.
- Convert selected candidates into `sourcing_plan.json`.
- Add feedback writeback wrapper.

Tests:

- Missing `ppt-lib` reports blocked library status.
- Library search result with `beat_id` maps to correct page task.
- Multiple same-role beats do not lose mapping.
- Approved/rejected source decisions produce writeback calls in dry-run test mode.

### Phase 5: PPT Quality Gate Promotion

- Move draft `ppt-quality-gate` into release skill tree.
- Add structured result schema.
- Add Deck Master import for quality gate findings if missing.
- Link Draft Gate, Render Gate and Delivery Gate to Deck Master quality stages.

Tests:

- Skill package passes skill-creator format checks.
- Standalone audit docs load correctly.
- Deck Master can import structured findings.

### Phase 6: PPT Deck Pro Max Suite Integration

- Move or mirror `ppt-deck-pro-max` into Deck Master suite release tree.
- Add generation session route to companion skill.
- Ensure generation results import back to Deck Master.
- Keep standalone skill usage intact.

Tests:

- Suite install links PPT Deck Pro Max.
- Deck Master generation session reports companion availability.
- Dry-run generation produces a Deck Master-tracked handoff.

### Phase 7: QA And Release

- Full unit tests.
- Skill package validation.
- Local install and reinstall.
- Suite setup smoke on temporary HOME.
- Real-machine status check without mutating user workspace.
- Review Cockpit setup banner check.

## Acceptance Criteria

Product acceptance:

- A user installing Deck Master gets a complete skill suite, or a precise report of missing optional companions.
- A user naming Deck Master sees an Agent-led setup path before production work.
- A user can still name PPT Library, PPT Deck Pro Max or PPT Quality Gate directly for standalone work.
- Deck Master knows when to route to PPT Library, PPT Deck Pro Max, PPT Quality Gate and PPT Master.
- PPT Library selection keeps page/beat mapping stable.
- Deck Master approval and delivery decisions can feed back to PPT Library.

Engineering acceptance:

- `suite-status` reports companion skill, CLI and readiness status.
- `suite-install` is idempotent.
- Codex and Claude skill links point into `~/.deck-master/current/skills`.
- No development repo path is used as the installed skill source.
- `setup-status --include-suite` exposes suite gaps.
- All existing v0.9.11 production guards remain active.
- Tests cover missing companion skill, wrong symlink, missing CLI, and healthy suite.

## Risks And Open Questions

1. PPT Library packaging source:
   - Option A: bundle only the skill docs and call external `ppt-lib`.
   - Option B: bundle a pinned PPT Library release inside Deck Master.
   - Recommendation: start with Option A for v0.9.12, because PPT Library already has its own repo, package and database lifecycle.

2. PPT Deck Pro Max packaging:
   - It currently exists as a large independent skill directory.
   - Need decide whether Deck Master release copies it, vendors a trimmed skill package, or points to an installed external release.
   - Recommendation: bundle a curated skill package under Deck Master release, keep source repo independent.

3. PPT Quality Gate promotion:
   - Draft skill appears close to formal skill shape.
   - Need add scripts or remove script references if those scripts are not bundled.
   - Recommendation: promote docs first, add scripts only when available.

4. PPT Master optionality:
   - Users may have different renderer choices.
   - Recommendation: keep PPT Master optional in suite readiness, but require result import before Deck Master delivery.

5. Naming:
   - Deck Master is the suite owner.
   - Companion skills keep their public names to preserve standalone use.

## Out Of Scope

- Rewriting PPT Library indexing internals.
- Rewriting PPT Deck Pro Max production algorithm.
- Building a remote package manager.
- Adding LLM provider calls into Deck Master.
- Changing PPT Master rendering internals.
- Multi-user hosted Deck Master deployment.

## Review Checklist

- Does the suite model match the intended user experience?
- Should PPT Library be required or optional for Deck Master install?
- Should PPT Master be optional or required?
- Should PPT Quality Gate ship in v0.9.12 or wait for a separate release?
- Should Deck Master bundle companion skill docs only, or copy full companion repos?
- Is `beat_id` preservation sufficient for PPT Library integration?
- Is feedback writeback required in v0.9.12, or can it be a follow-up?
