# Deck Master v0.9.12 Suite Runtime QA Report

Date: 2026-06-16
Target: `http://127.0.0.1:5072/?run=qa-suite-runtime`
Scope: `codex/deck-master-v0912-suite-runtime`
Mode: Standard full QA
Result: PASS

## Summary

- Baseline score: 84
- Final score: 100
- Issues found: 1
- Issues fixed: 1
- Deferred code issues: 0
- Browser console errors after fix: 0
- Mobile overflow after fix: 0
- Regression tests after fix: 701 passed

PR summary: QA found 1 blocking Review Cockpit issue, fixed it, and verified the suite runtime path end to end.

## Environment

- Repo branch: `codex/deck-master-v0912-suite-runtime`
- QA head after fixes: `ce1643c`
- Browse tool: `/Users/dingcheng/.gstack/repos/gstack/browse/dist/browse`
- QA server: direct Preview mode with temporary run directory
- Test run: `qa-suite-runtime`
- Run directory: `/tmp/deck-master-v0912-qa-runs.hfsRBc/qa-suite-runtime`

## Automated Checks

- `python3 -m unittest discover -s tests`: 701 tests OK
- `python3 -m unittest tests.test_preview_server tests.test_review_workbench`: 41 tests OK
- `git diff --check HEAD`: OK
- `deck-master setup-status --include-suite --output json` in temporary HOME: no new files written
- `deck-master suite-status --output json`: OK
- `deck-master library-status --output json`: OK

## Browser Coverage

- Direct Preview page loaded at `/?run=qa-suite-runtime`.
- Runtime readiness API returned suite readiness data for the active run.
- External results API returned import log, generation result, blocking quality summary, and pending feedback summary.
- Quality governance API returned delivery blocked when seeded P1/P2 findings existed.
- Console after fix: no messages.
- Mobile viewport: 390 x 844, no horizontal overflow.

## Evidence

- Initial desktop before fix: `.gstack/qa-reports/screenshots/v0912-suite-runtime-preview-2026-06-16.png`
- After first runtime fix: `.gstack/qa-reports/screenshots/v0912-suite-runtime-after-issue-001-2026-06-16.png`
- Final desktop after fix: `.gstack/qa-reports/screenshots/v0912-suite-runtime-after-issue-001-final-2026-06-16.png`
- Final mobile after fix: `.gstack/qa-reports/screenshots/v0912-suite-runtime-mobile-2026-06-16.png`

## ISSUE-001

Title: Direct Preview mode did not resolve runtime side-panel APIs against the active run directory
Severity: High
Category: Functional / Review Cockpit
Status: Fixed and verified

### Repro

1. Start Review Cockpit in direct Preview mode with a run directory outside the configured setup runs directory.
2. Open `http://127.0.0.1:5072?run=qa-suite-runtime`.
3. Inspect browser console and runtime side-panel APIs.

Observed before fix:

- The deck itself loaded.
- New runtime visibility APIs returned 404 when the run lived outside the configured setup runs directory.
- Console recorded repeated 404s for runtime readiness, external results, run state, narrative, quality governance, asset signals, export queue, and metrics.

Expected:

- Direct Preview mode should resolve active-run APIs against the explicit `run_dir`.
- Studio mode should continue using the configured runs directory.
- Invalid or unknown run ids should still return 400/404.

### Fix

Commits:

- `0fc671a fix(qa): ISSUE-001 - direct preview runtime APIs`
- `ce1643c fix(qa): ISSUE-001 - direct preview side panel APIs`

Files changed:

- `scripts/preview/server.py`
- `tests/test_preview_server.py`

Fix details:

- Routed direct Preview runtime APIs through the active run resolver.
- Extended the resolver so direct mode allows only the active run id or active run directory name.
- Moved narrative, asset signals, and quality governance APIs to the same resolver.
- Added regression coverage for external results, runtime readiness, narrative, asset signals, and quality governance in direct Preview mode.

### Verification

- Browser console after fix: 0 messages.
- `/api/runtime-readiness/qa-suite-runtime`: 200.
- `/api/external-results/qa-suite-runtime`: 200.
- `/api/quality-governance/qa-suite-runtime`: 200.
- `/api/narrative/qa-suite-runtime`: covered by regression test.
- `/api/asset-signals/qa-suite-runtime`: covered by regression test.
- Invalid direct run id path traversal remains rejected by regression test.

## Observations

- The real installed machine state currently reports `suite-status: degraded_ready` because several companion skills are missing or point at real directories instead of managed symlinks.
- This is a valid environment signal from the new suite inspector, not a code failure in this QA branch.
- Next setup action after deploying this branch should be `deck-master suite-repair --target codex`, followed by setup-status verification.
- The top-center Review Cockpit cards are readable but sparse when a run lacks richer readiness/export/metrics detail. This is low priority and does not block v0.9.12.

## Final Readiness

The v0.9.12 suite runtime branch is QA-passed at `ce1643c`.

The branch is ready for the next step: push or local reinstall/deploy, then run suite repair/setup against the real installed Deck Master path.
