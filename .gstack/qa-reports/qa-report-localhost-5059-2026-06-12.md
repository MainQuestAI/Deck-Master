# QA Report: Deck Master Preview Workbench

Date: 2026-06-12
Target: http://127.0.0.1:5059
Branch: codex/v095-v097-development
Mode: Standard QA, diff-aware
Run: benchmarks/benchmark_runs/qa-retail-fixture

## Summary

QA found 4 medium issues and fixed all 4.

Health score: 92 -> 100

PR summary: QA found 4 issues, fixed 4, health score 92 -> 100.

## Evidence

- Initial preview visible after fix: .gstack/qa-reports/screenshots/final-initial-preview-ui.png
- Request evidence state after fix: .gstack/qa-reports/screenshots/final-request-evidence-state.png
- Convert to generate state after fix: .gstack/qa-reports/screenshots/final-convert-generate-state.png
- Mobile layout after fix: .gstack/qa-reports/screenshots/final-mobile-preview-ui.png

## Issues Fixed

### ISSUE-001: Preview image was pushed below the first viewport

Severity: Medium
Category: Visual / UX
Fix status: verified
Commit: 653b7d6
Files changed: scripts/preview/static/style.css

Impact: users landed on a mostly blank preview frame and had to scroll before seeing the page image.

Fix: made the preview frame start at the top of its grid area.

Verification: final browser metrics showed frameY=168, imageY=250.5625, imageVisible=true.

### ISSUE-002: Request evidence did not persist review state

Severity: Medium
Category: Functional
Fix status: verified
Commit: f6d7824
Files changed: scripts/review/workbench.py, scripts/preview/manifest.py, docs/schemas/preview_manifest.schema.json, tests/test_preview_manifest.py, tests/test_review_workbench.py

Impact: the UI displayed "request_evidence applied", but the page stayed at needs_review, so reviewers could not trust the workbench state.

Fix: request_evidence now updates preview_manifest.json and page_tasks.json with review_status=needs_evidence and action_intent=request_evidence.

Verification: browser API state returned review_status=needs_evidence and action_intent=request_evidence.

### ISSUE-003: Convert to generate did not show the new sourcing intent

Severity: Medium
Category: Functional
Fix status: verified
Commit: f6d7824
Files changed: scripts/review/workbench.py, scripts/preview/manifest.py, tests/test_preview_manifest.py, tests/test_review_workbench.py

Impact: the UI displayed "convert_to_generate applied", but the page details still showed source_decision=reuse.

Fix: convert_to_generate now updates preview_manifest.json with source_decision=generate and action_intent=generate, while keeping review_status=needs_review.

Verification: browser API state returned source_decision=generate and page details showed "Sourcing decision: generate".

### ISSUE-004: Mobile layout had horizontal overflow

Severity: Medium
Category: UX
Fix status: verified
Commit: b30719a
Files changed: scripts/preview/static/style.css

Impact: on 390px mobile viewport, the page width expanded to 485px and created horizontal scrolling.

Fix: tightened responsive layout rules so the three-column workbench becomes a single viewport-safe column on small screens.

Verification: final mobile metrics showed document width 390px, body width 390px, overflow=false, offenders=[].

## Final Verification

- Browser route: http://127.0.0.1:5059
- Console errors: 0
- Page errors: 0
- 4xx/5xx responses during final browser pass: 0
- Full test suite: 617 tests OK
- Syntax checks: Python py_compile OK, app.js node --check OK
- Diff whitespace check: OK

## Notes

The benchmark run still reports pending external agent steps for narrative_advice and external_quality_review. That is expected for semi-auto mode and did not block preview workbench QA.
