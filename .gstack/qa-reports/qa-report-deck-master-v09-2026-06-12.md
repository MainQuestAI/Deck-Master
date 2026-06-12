# QA Report — Deck Master v0.9 Agentic Integration

**Date:** 2026-06-12  
**Branch:** `codex/deck-master-v09-agentic-iteration`  
**Tier:** Standard  
**Mode:** Full (API + CLI end-to-end)

---

## Summary

| Metric | Value |
|---|---|
| Unit tests | 569 (405 existing + 161 new + 3 regression) — **all passing** |
| Packages tested | 10 (A–I, F1–F3) |
| CLI commands verified | 18 new |
| HTTP APIs verified | 7 new |
| Issues found | 3 (1× P0, 2× P1) |
| Fixes applied | 3 (all verified) |
| Health score | **100/100** (after fixes) |

---

## Issues Found & Fixed

### ISSUE-001 [P0] External review trusted external summary, bypassing P1 export block

**File:** `scripts/quality/external_review.py:239`  
**Severity:** P0  
**Status:** Fixed (commit `ccb72b2`)

**Description:** `import_external_review` read `summary.status` and `summary.blocks_delivery` directly from the external Agent's JSON. An Agent could (or a buggy Agent would) send `"status": "pass", "blocks_delivery": false` while the findings array contained P1 items. The gate report would then record `status: pass`, and `has_client_export_quality_clearance()` would allow export despite unresolved P1 findings.

**Fix:** Status and `blocks_delivery` are now computed exclusively from the `findings` array. The external `summary` field is ignored for these two values.

**Regression test:** `test_p1_finding_blocks_even_if_summary_says_pass`

---

### ISSUE-002 [P1] `prepare-generation-handoff` incompatible with real `create-generation-tasks` output

**File:** `scripts/generation/handback.py:85`  
**Severity:** P1  
**Status:** Fixed (commit `ccb72b2`)

**Description:** `task_builder.py` writes `index.json` as `{"run_id": ..., "tasks": [task_dict, ...]}`. `handback.py` read `index_data.get("task_ids", [])` which does not exist in real output, returning `task_count: 0` for any real run.

**Fix:** `handback.py` now reads `tasks` first (extracting `task_id` from each dict), falling back to `task_ids` for forward compatibility.

**Regression test:** `test_prepare_handoff_real_task_builder_format`

---

### ISSUE-003 [P1] New `context_manifest.json` missing `schema_version`

**File:** `scripts/context_intake/context_pack.py:232`  
**Severity:** P1  
**Status:** Fixed (commit `ccb72b2`)

**Description:** When no prior `context_manifest.json` existed, the import created `{"sources": [], "summary": "", "constraints": []}` without a `schema_version`. Spec requires "新 artifact 必须有 schema_version".

**Fix:** New manifest now includes `"schema_version": "deck_context_manifest.v1"`.

**Regression test:** `test_new_manifest_has_schema_version`

---

## Phase 1: Unit Test Suite

```
Ran 569 tests in 0.667s
OK
```

All 569 tests pass. 405 pre-existing tests unmodified and still green.
161 new feature tests + 3 regression tests for issues found during QA.

| Package | Tests |
|---|---|
| A — Skill Packaging | 22 |
| B — Context Pack | 20 |
| C — Narrative Advisory | 17 |
| D — External Quality Review | 20 |
| E — Generation Handback | 17 |
| F1 — Review Cockpit (read-only) | 15 |
| F2/F3 — Workbench + Visibility | 15 |
| G — Workspace Learning | 8 |
| H — Companion Tool Validators | 23 |
| I — Metrics Hooks | 4 |

---

## Phase 2: Preview Server API Verification

Started `scripts/preview/server.py` on port 8765. Created sample run via
`autoplan` (12 pages, retail industry, fixture mode).

### F1 Read-only APIs

| Endpoint | Status | Notes |
|---|---|---|
| `GET /api/review-summary/<run_id>` | ✅ 200 | Readiness, counts correct |
| `GET /api/claim-coverage/<run_id>` | ✅ 200 | Claims returned with status |
| `GET /api/next-actions/<run_id>` | ✅ 200 | 5 actions, correct priority order |
| `GET /api/review-summary/nonexistent` | ✅ 404 | Correct error |

### F2 Page Workbench Actions

| Action | Status | Notes |
|---|---|---|
| `add_note` | ✅ | Note persisted to page_tasks |
| `lock_source` | ✅ | locked=true set |
| `convert_to_generate` | ✅ | decision_intent updated |
| `approve` (no P0) | ✅ | review_status=approved |
| Invalid action | ✅ 400 | Clear error with valid actions list |

### F3 External Result Visibility

| Endpoint | Status | Notes |
|---|---|---|
| `GET /api/external-results/<run_id>` | ✅ 200 | Returns narrative, reviews, gen results |

---

## Phase 3: CLI End-to-End Verification

### Package B — Context Pack

```bash
python3 scripts/deck_master.py import-context-pack \
  --run-id qa-test-run --input context_pack.json
```
- ✅ Imported, evidence_candidates preserved in context_manifest
- ✅ Duplicate source_id rejected without --merge
- ✅ Bad JSON rejected, existing manifest preserved

### Package C — Narrative Advisory

```bash
prepare-narrative-advice → import-narrative-advice → apply-narrative-advice
```
- ✅ Task artifact generated with correct inputs list
- ✅ Import validates schema, stores result
- ✅ Dry-run produces diff without modifying artifacts
- ✅ Real apply updates page_tasks (decision_intent, core_claim, evidence_need)
- ✅ Apply writes external_narrative_gate.json quality report
- ✅ Apply adds gaps to claim_evidence_graph.json

### Package D — External Quality Review

```bash
prepare-quality-review → import-quality-review
```
- ✅ Task files created per scope (semantic, visual)
- ✅ Import creates `external_semantic_codex_gate.json`
- ✅ P1 finding blocks delivery
- ✅ Multiple reviewer files coexist

### Package E — Generation Handoff

```bash
prepare-generation-handoff → import-generation-result → refresh-preview-from-generation
```
- ✅ Handoff enhances tasks with schema_version, workspace_refs, quality_requirements
- ✅ Import updates task status, writes result file
- ✅ Locked pages block overwrite without --force
- ✅ Preview refresh updates preview_manifest.json

### Package G — Workspace Learning

```bash
build-learning-pack → show-learning-pack
```
- ✅ Aggregates failure modes from quality reports
- ✅ Produces JSON + Markdown
- ✅ Agent guidance generated from failure modes

### Package H — Companion Tool Validators

```bash
validate-ppt-library-result → validate-generation-result → validate-render-result
```
- ✅ Valid candidate: valid=true
- ✅ Missing required fields: valid=false with specific errors
- ✅ Confidence out of range: valid=false
- ✅ Optional fields missing: warnings only
- ✅ Source file nonexistent: warning

### Package I — Metrics Hooks

```bash
summarize-run-metrics
```
- ✅ Correct page counts, source decision counts
- ✅ Quality finding counts aggregated from gate reports
- ✅ Durations computed from events; degrades to mtime when events missing

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

## Issues Found

None. All 10 packages function correctly via unit tests, HTTP API, and CLI.

---

## Verification Matrix

| v0.9 Spec Requirement | Status |
|---|---|
| Skill install/validate/uninstall via symlink | ✅ |
| Context Pack import with evidence_candidates | ✅ |
| Narrative advice prepare/import/apply with diff | ✅ |
| External review with P0/P1 export blocking | ✅ |
| Generation handoff/handback with locked page protection | ✅ |
| Review Cockpit readiness/coverage/next actions | ✅ |
| Page workbench actions with event logging | ✅ |
| P0 blocks approval (Quality Gate not bypassed) | ✅ |
| External result visibility (narrative, reviews, generation) | ✅ |
| Workspace learning pack (JSON + Markdown) | ✅ |
| Companion tool validators (library, generation, render) | ✅ |
| Run metrics from events with mtime fallback | ✅ |
| Bad JSON never overwrites existing artifacts | ✅ |
| All operations write typed events | ✅ |
| Zero built-in LLM provider | ✅ |
