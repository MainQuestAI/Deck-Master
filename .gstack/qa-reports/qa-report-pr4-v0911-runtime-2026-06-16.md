# QA Report: PR #4 v0.9.11 Runtime Realignment

Date: 2026-06-16
Branch: `codex/deck-master-v0911-runtime-realignment`
PR: https://github.com/MainQuestAI/Deck-Master/pull/4
Mode: diff-aware standard QA
Target: CLI runtime, Context Pack, generation state resolver, Review Cockpit Studio

## Summary

QA found 1 real issue in Review Cockpit Studio after the latest runtime fixes.
The issue was fixed and re-verified.

- Issues found: 1
- Fixes applied: 1 verified
- Deferred issues: 0
- Health score: 92 -> 100
- PR checks: GitHub Actions success

PR summary: QA found 1 issue, fixed 1, health score 92 -> 100.

## Coverage

- `deck-master start` without setup or context file
- `create-run-from-context-pack` workspace runtime fields
- `generation_session.status=quality_required` stale quality gate protection
- Review Cockpit `/api/setup-status`, `/api/runs`, `/api/run-state/<run_id>`
- Browser Studio flow for setup blocked and setup ready states
- Desktop and mobile smoke for Studio page

## Issue 001: Production Run Created In Setup Runs Dir Was Not Visible To Later Studio Requests

Severity: High
Category: Functional
Fix Status: verified

### What Broke

In a real HTTP server, each request gets a fresh handler instance. Production
`POST /api/runs` created the run in setup `default_runs_dir`, but later
`GET /api/run-state/<run_id>` looked under the server startup `--runs-dir`.
The result was a 404 for a run that had just been created.

### Evidence

Before fix:

- `POST /api/runs` returned `201`
- `GET /api/run-state/browser-ready` returned `404`
- Browser showed the run in the list, but Run State stayed empty

After fix:

- `GET /api/run-state/browser-ready` returns `200`
- Run state reports `stage=needs_context`
- `/api/runs` lists setup `default_runs_dir`
- Browser console has 0 errors
- Network no longer requests `/api/deck` for a pre-preview production run

Screenshots:

- `screenshots/pr4-studio-initial-2026-06-16.png`
- `screenshots/pr4-studio-after-fix-2026-06-16.png`
- `screenshots/pr4-studio-final-after-server-fix-2026-06-16.png`
- `screenshots/pr4-studio-final-mobile-2026-06-16.png`

### Fix

- `scripts/preview/server.py`
  - Added setup-aware Studio runs-dir resolution for real server handlers.
  - Kept fixed-run preview mode and mock tests isolated from local user setup.
  - Added regression coverage for production create followed by run-state from a new handler instance.

- `scripts/preview/static/app.js`
  - Avoids `/api/deck` calls when no run is selected.
  - For production runs with `0 pages`, shows run-state and next command instead of treating missing preview as a page error.
  - Shows production create response as a run-state creation when pages are not available.

## Verification

- `python3 -m unittest -q tests/test_preview_server.py tests/test_review_cockpit.py tests/test_review_workbench.py`: 58 tests OK
- `python3 -m unittest discover -s tests`: 679 tests OK
- `node --check scripts/preview/static/app.js`: OK
- `python3 -m compileall scripts tests`: OK
- `git diff --check origin/main...HEAD && git diff --check`: OK
- Browser QA:
  - `/api/setup-status`: ready after setup
  - `/api/run-state/browser-ready`: `stage=needs_context`
  - Console: 0 errors
  - Network: `setup-status`, `runs`, `run-state` only for pre-preview run
  - Mobile width check: `scrollWidth=390`, `innerWidth=390`

## Residual Risk

No merge-blocking QA issues remain from this pass. PR remains Draft by policy.
