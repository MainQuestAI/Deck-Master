# Exact 601 CI terminal diagnosis — 2026-10-23

Investigated head: `601f5ec68ae994fb42d933f672f0f495eb6d557b`.
No workflow was rerun or cancelled. No production/model calls were made.

## Remote evidence

- PR run https://github.com/MainQuestAI/Deck-Master/actions/runs/39924041444:
  success, terminal 09:05:40 UTC. Four unit jobs each 3882 passed/2 skipped;
  renderer 138 passed/1 skipped; browser 613 passed; installed recovery 336 passed.
  PR checkout b32266f80e8a855a0ae1c094b2a87f270024f30d differs from head only
  in five baseline issue-sync documentation files, not runtime/tests.
- Push run https://github.com/MainQuestAI/Deck-Master/actions/runs/39924035401:
  failure, terminal 10:15:00 UTC. Three unit jobs passed; Python 3.12/Node 22
  job 120315932253 failed Q2 at its unchanged 180-second subprocess limit
  (69/70 child cases complete; 3881 passed/2 skipped in the outer suite).
  Renderer passed (138 passed/1 skipped).
  Browser job 120315931774: 1 failed/612 passed, 2192.70 seconds;
  installed checks were skipped because their browser prerequisite failed.
  PR success does not replace either push failure.

## Browser synchronization: reproduced and corrected locally

Failure was `test_method_preparation_browser.py::test_speech_clipboard_and_no_phase_catalog`
with Studio/deck-review/speech. Line 56 split clipboard content on a JSON fence
and raised IndexError. The failed log did not retain clipboard content.

Playwright's installed wait_for_function implementation tests the truthiness of
its predicate before resolving a returned Promise. A real Chromium probe with
`Promise.resolve(false)` returned false in 0.038 seconds instead of waiting.
The test's asynchronous clipboard predicate therefore did not guarantee that
copyText's real write had completed.

At unchanged 601, the four browser cases initially passed (12.48 seconds).
Adding a 750 ms delay around Chromium's actual clipboard write, after clearing
its actual clipboard, reproduced the same Studio/Review IndexError (1 failed,
2.93 seconds). No handoff bytes or receipt were mocked. This establishes a
concrete synchronization defect consistent with CI; the failed runner's exact
clipboard bytes remain unknown.

Fix: wait for copyText's existing success notification (emitted only after
writeText resolves), then read the real clipboard and explicitly assert the
schema marker before the original JSON, role, phase, units, preview digest,
resource hash/body, document immutability and page-error checks. Retain the
slow-write regression for both routes and both roles. Product code unchanged.

Validation on the changed test at 10:20 UTC:

- `.venv/bin/python -m pytest -q --require-browser tests/rebuild/test_method_preparation_browser.py`
  — 4 passed, 15.45 seconds; real /usr/bin/chromium.
- `.venv/bin/python -m pytest -q tests/rebuild/test_method_preparation_handoff.py`
  — 4 passed, 0.33 seconds.
- `git diff --check` — passed.

## Q2: root cause remains unknown

Earlier same-host serial comparisons, preserving all 70 cases and the 180-second
limit, matched all 25 installed distribution versions between fdb8fca9 and 601.
All four runs passed all cases:

| Revision | Sample | Wall seconds | User CPU | System CPU |
|---|---:|---:|---:|---:|
| 601 | 1 | 94.0313 | 74.0823 | 20.7134 |
| fdb8 | 1 | 109.7683 | 95.7266 | 14.5577 |
| 601 | 2 | 96.0415 | 75.3585 | 21.3744 |
| fdb8 | 2 | 113.2177 | 97.9133 | 15.8384 |

The last-active case separately passed in 3.32 seconds. The Q2 carrier/wrapper
and campaign tools were unchanged across these revisions. These observations
do not reproduce an incremental slowdown, but cannot prove runner contention.
Local Python was 3.12.14 versus CI 3.12.15. These were not cold-disk benchmarks.
An initial unmatched-package baseline sample was excluded. Failed CI retained
only a bounded child-output tail, not complete per-case timing or host telemetry.

The environment disconnected and subsequently resumed; actual shell execution,
clean 601 checkout and remote 601 were reconfirmed in this turn. Earlier /tmp
comparison artifacts are absent after resumption, so the table preserves the
prior recorded observations, not a newly rerun comparison or recoverable raw
artifact. No timeout/security check was weakened and no speculative Q2 fix made.

The local browser correction requires parent confirmation of push scope and a
new exact-head CI run. It has not been pushed by this diagnosis task.
