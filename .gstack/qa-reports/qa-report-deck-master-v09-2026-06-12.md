# QA Report — Deck Master v0.9 Agentic Integration

- **Date:** 2026-06-12
- **Branch:** `codex/deck-master-v09-agentic-iteration`
- **Tier:** Standard
- **Mode:** Full (API + CLI end-to-end)

---

## Summary

| Metric | Value |
|---|---|
| Unit tests | 580 total — **all passing** |
| Packages tested | 10 (A–I, F1–F3) |
| CLI commands verified | 18 new |
| HTTP APIs verified | 7 new |
| Issues found | 10 total, including 3 PR #2 blocking follow-ups |
| Fixes applied | 10 (all verified) |
| Health score | **100/100** (after fixes) |

---

## PR #2 Review Follow-up Fixes

After ChatGPT review of the latest PR #2 head, 3 blocking contract gaps and 2 related state-source gaps were reproduced and fixed.

| Issue | Severity | Fix | Regression coverage |
|---|---|---|---|
| External result import accepted mismatched `run_id` | Blocking | Added shared `assert_external_result_matches_run()` and wired it into context pack import, narrative advice import/apply, external quality review import, and generation result import | 5 mismatch rejection tests |
| Review Workbench approve/reject only updated `page_tasks.json` | Blocking | `approve/reject` now update `preview_manifest.json` through `update_page_review()`; missing manifest returns a clear Workbench error | approve/reject manifest assertions and export queue assertions |
| Generation refresh wrote legacy preview fields only | Blocking | `refresh_preview_from_generation()` now validates formal manifest, requires run-relative preview assets, preserves `previous_preview_path`, and writes `preview_path`, `source_preview_asset`, `source_type`, `generation_status` | generation refresh regression tests |
| Readiness/metrics counted review status from auxiliary page tasks | State-source gap | approved/rejected/needs_review now use `preview_manifest.pages[]` when present | readiness and metrics runtime-source tests |
| Sourcing/generation summary missed real index formats | State-source gap | source decision counts use `sourcing_plan.decisions[]`; next actions/readiness support `generation_tasks/index.json.tasks[]` and `task_ids[]` | failed generation task next-action test |

Scope note: F1/F2/F3 backend APIs and Agentic contract are complete for PR #2. The full F.7 front-end cockpit UI remains a follow-up item and is not claimed as complete in this PR.

Architecture review of PR head `ec3c10bf83747481cdf3552b78d61729210ca2b2` found no remaining blocking issues for the backend contract scope. Merge readiness depends on accepting the explicit F.7 frontend scope note.

### Follow-up Verification

```
Ran 580 tests in 0.773s
OK
```

| Check | Result |
|---|---|
| Unit tests | 580 tests, all passing |
| `git diff --check main...HEAD` | clean |
| Built-in LLM provider scan | clean for SDK/provider imports |
| Real smoke | external review import -> generation refresh -> review approve -> export queue -> metrics passed |

---

## Issues Found & Fixed

### ISSUE-001 [P0] External review trusted external summary, bypassing P1 export block

- **File:** `scripts/quality/external_review.py:239`
- **Severity:** P0
- **Status:** Fixed (commit `ccb72b2`)

**Description:** `import_external_review` read `summary.status` and `summary.blocks_delivery` directly from the external Agent's JSON. An Agent could (or a buggy Agent would) send `"status": "pass", "blocks_delivery": false` while the findings array contained P1 items. The gate report would then record `status: pass`, and `has_client_export_quality_clearance()` would allow export despite unresolved P1 findings.

**Fix:** Status and `blocks_delivery` are now computed exclusively from the `findings` array. The external `summary` field is ignored for these two values.

**Regression test:** `test_p1_finding_blocks_even_if_summary_says_pass`

---

### ISSUE-002 [P1] `prepare-generation-handoff` incompatible with real `create-generation-tasks` output

- **File:** `scripts/generation/handback.py:85`
- **Severity:** P1
- **Status:** Fixed (commit `ccb72b2`, index sync added in follow-up)

**Description:** `task_builder.py` writes `index.json` as `{"run_id": ..., "tasks": [task_dict, ...]}`. `handback.py` read `index_data.get("task_ids", [])` which does not exist in real output, returning `task_count: 0` for any real run.

**Fix:** `handback.py` now reads `tasks` first (extracting `task_id` from each dict), falling back to `task_ids` for forward compatibility. Enhanced task data is also synced back to `index_data["tasks"]` so external tools reading the index see the same handoff fields.

**Regression tests:** `test_prepare_handoff_real_task_builder_format`, `test_prepare_handoff_syncs_index_tasks`

---

### ISSUE-003 [P1] New `context_manifest.json` missing `schema_version` (context_pack path)

- **File:** `scripts/context_intake/context_pack.py:232`
- **Severity:** P1
- **Status:** Fixed (commit `ccb72b2`)

**Description:** When no prior `context_manifest.json` existed, `import_context_pack` created `{"sources": [], "summary": "", "constraints": []}` without a `schema_version`. Spec requires "新 artifact 必须有 schema_version".

**Fix:** New manifest now includes `"schema_version": "deck_context_manifest.v1"`.

**Regression test:** `test_new_manifest_has_schema_version`

---

### ISSUE-004 [P1] `start-conversation` path also missing `schema_version` in context_manifest

- **File:** `scripts/context_intake/local_sources.py:67`
- **Severity:** P1
- **Status:** Fixed (this commit)

**Description:** `build_context_manifest()` (used by `start-conversation` and `autoplan`) also omitted `schema_version`. Same spec violation as ISSUE-003, different code path.

**Fix:** Added `"schema_version": "deck_context_manifest.v1"` to the returned dict.

**Regression tests:** assertion added to `test_context_manifest_records_local_source` and `test_conversation_cli` end-to-end flow.

---

### ISSUE-005 [P2] `prepare-generation-handoff` did not sync enhanced fields to `index.json`

- **File:** `scripts/generation/handback.py:112`
- **Severity:** P2
- **Status:** Fixed (this commit)

**Description:** After enhancing individual task files with handoff fields, the `tasks[]` entries in `index.json` still contained the old task data. External tools reading the index would see stale task entries without `schema_version`, `workspace_refs`, or `quality_requirements`.

**Fix:** After the enhancement loop, `index_data["tasks"]` is now updated with the enhanced task dicts before writing the index.

**Regression test:** `test_prepare_handoff_syncs_index_tasks`

---

## Phase 1: Unit Test Suite

```
Ran 580 tests in 0.773s
OK
```

All 580 tests pass. Existing coverage remains green.
15 regression tests cover the original QA issues and PR #2 review follow-up fixes.

| Package | Tests |
|---|---|
| A — Skill Packaging | 22 |
| B — Context Pack | 22 |
| C — Narrative Advisory | 19 |
| D — External Quality Review | 22 |
| E — Generation Handback | 22 |
| F1 — Review Cockpit (read-only) | 17 |
| F2/F3 — Workbench + Visibility | 17 |
| G — Workspace Learning | 8 |
| H — Companion Tool Validators | 23 |
| I — Metrics Hooks | 4 |
| Conversation (existing) | +2 assertions |

---

## Phase 2: Preview Server API Verification

Started `scripts/preview/server.py` on port 8765. Created sample run via `autoplan` (12 pages, retail industry, fixture mode).

### F1 Read-only APIs

| Endpoint | Status | Notes |
|---|---|---|
| `GET /api/review-summary/<run_id>` | 200 | Readiness, counts correct |
| `GET /api/claim-coverage/<run_id>` | 200 | Claims returned with status |
| `GET /api/next-actions/<run_id>` | 200 | 5 actions, correct priority order |
| `GET /api/review-summary/nonexistent` | 404 | Correct error |

### F2 Page Workbench Actions

| Action | Status | Notes |
|---|---|---|
| `add_note` | ok | Note persisted to page_tasks |
| `lock_source` | ok | locked=true set |
| `convert_to_generate` | ok | decision_intent updated |
| `approve` (no P0) | ok | review_status=approved |
| Invalid action | 400 | Clear error with valid actions list |

### F3 External Result Visibility

| Endpoint | Status | Notes |
|---|---|---|
| `GET /api/external-results/<run_id>` | 200 | Returns narrative, reviews, gen results |

---

## Phase 3: CLI End-to-End Verification

### Package B — Context Pack

- Imported, evidence_candidates preserved in context_manifest
- Duplicate source_id rejected without --merge
- Bad JSON rejected, existing manifest preserved

### Package C — Narrative Advisory

- Task artifact generated with correct inputs list
- Import validates schema, stores result
- Dry-run produces diff without modifying artifacts
- Real apply updates page_tasks (decision_intent, core_claim, evidence_need)
- Apply writes external_narrative_gate.json quality report
- Apply adds gaps to claim_evidence_graph.json

### Package D — External Quality Review

- Task files created per scope (semantic, visual)
- Import creates `external_semantic_codex_gate.json`
- P1 finding blocks delivery
- Multiple reviewer files coexist

### Package E — Generation Handoff

- Handoff enhances tasks with schema_version, workspace_refs, quality_requirements
- Index.json tasks[] synced with enhanced fields
- Import updates task status, writes result file
- Locked pages block overwrite without --force
- Preview refresh updates preview_manifest.json

### Package G — Workspace Learning

- Aggregates failure modes from quality reports
- Produces JSON + Markdown
- Agent guidance generated from failure modes

### Package H — Companion Tool Validators

- Valid candidate: valid=true
- Missing required fields: valid=false with specific errors
- Confidence out of range: valid=false
- Optional fields missing: warnings only
- Source file nonexistent: warning

### Package I — Metrics Hooks

- Correct page counts, source decision counts
- Quality finding counts aggregated from gate reports
- Durations computed from events; degrades to mtime when events missing

---

## Health Score

| Category | Score |
|---|---|
| Unit Tests | 100 |
| API Correctness | 100 |
| CLI Correctness | 100 |
| Error Handling | 100 |
| Data Integrity | 100 |
| **Overall** | **100** |

---

## Unresolved Issues

None for the PR #2 backend contract scope. Full F.7 front-end cockpit UI is a follow-up scope item.

---

## Verification Matrix

| v0.9 Spec Requirement | Status |
|---|---|
| Skill install/validate/uninstall via symlink | verified |
| Context Pack import with evidence_candidates | verified |
| Narrative advice prepare/import/apply with diff | verified |
| External review with P0/P1 export blocking | verified |
| Generation handoff/handback with locked page protection | verified |
| Review Cockpit readiness/coverage/next actions | verified |
| Page workbench actions with event logging | verified |
| Workbench approve/reject sync to preview_manifest | verified |
| Generation refresh writes formal preview_path runtime fields | verified |
| External result run_id binding | verified |
| P0 blocks approval (Quality Gate not bypassed) | verified |
| External result visibility (narrative, reviews, generation) | verified |
| Workspace learning pack (JSON + Markdown) | verified |
| Companion tool validators (library, generation, render) | verified |
| Run metrics from events with mtime fallback | verified |
| Bad JSON never overwrites existing artifacts | verified |
| All operations write typed events | verified |
| Zero built-in LLM provider | verified |
| All artifacts carry schema_version | verified |
